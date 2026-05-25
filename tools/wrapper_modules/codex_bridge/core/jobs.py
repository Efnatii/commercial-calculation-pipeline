from __future__ import annotations

import json
import os
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from wrapper_modules.codex_bridge.core.auth import TokenRecord, iso_now
from wrapper_modules.codex_bridge.core.codex import CodexCommandBuilder
from wrapper_modules.codex_bridge.core.config import BridgeConfig, WorkspaceConfig, sanitize_id


TERMINAL_STATES = {"completed", "failed", "cancelled"}


@dataclass
class JobState:
    id: str
    mode: str
    workspace_id: str
    status: str
    command: list[str]
    created_at: str
    created_by: str
    created_by_name: str
    chat_id: str | None = None
    chat_name: str | None = None
    started_at: str | None = None
    ended_at: str | None = None
    exit_code: int | None = None
    error: str | None = None
    log_path: str | None = None
    last_message: str | None = None
    events: list[dict[str, Any]] = field(default_factory=list)
    process: subprocess.Popen[str] | None = field(default=None, repr=False, compare=False)

    def public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "mode": self.mode,
            "workspace_id": self.workspace_id,
            "status": self.status,
            "created_at": self.created_at,
            "created_by": self.created_by,
            "created_by_name": self.created_by_name,
            "chat_id": self.chat_id,
            "chat_name": self.chat_name,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "exit_code": self.exit_code,
            "error": self.error,
            "log_path": self.log_path,
            "last_message": self.last_message,
            "event_count": len(self.events),
            "command_preview": redact_command(self.command),
        }


def redact_command(command: list[str]) -> list[str]:
    redacted: list[str] = []
    redact_next = False
    for item in command:
        if redact_next:
            redacted.append("<redacted>")
            redact_next = False
            continue
        redacted.append(item)
        if item in {"--ws-token-file", "--ws-shared-secret-file", "--remote-auth-token-env"}:
            redact_next = True
    return redacted


def normalize_user_name(value: str) -> str:
    return " ".join(str(value or "").split()).casefold()


class JobManager:
    def __init__(self, config: BridgeConfig):
        self.config = config
        self.jobs_dir = config.state_dir / "jobs"
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self.chats_path = config.state_dir / "chats.json"
        self._lock = threading.RLock()
        self._jobs: dict[str, JobState] = {}
        self._builder = CodexCommandBuilder(config)

    def list_jobs(self) -> tuple[JobState, ...]:
        with self._lock:
            return tuple(sorted(self._jobs.values(), key=lambda job: job.created_at, reverse=True))

    def get_job(self, job_id: str) -> JobState | None:
        with self._lock:
            return self._jobs.get(job_id)

    def active_count(self) -> int:
        with self._lock:
            return sum(1 for job in self._jobs.values() if job.status not in TERMINAL_STATES)

    def create_job(
        self,
        workspace: WorkspaceConfig,
        mode: str,
        payload: dict[str, Any],
        actor: TokenRecord,
        actor_name: str,
    ) -> JobState:
        with self._lock:
            if self.active_count() >= self.config.max_concurrent_jobs:
                raise RuntimeError("Maximum concurrent Codex jobs reached.")
            chat = self._payload_chat(workspace.id, payload, actor_name)
            command, stdin_text = self._builder.build(workspace, mode, payload)
            job_id = uuid.uuid4().hex[:12]
            job_dir = self.jobs_dir / job_id
            job_dir.mkdir(parents=True, exist_ok=True)
            log_path = job_dir / "events.jsonl"
            job = JobState(
                id=job_id,
                mode=mode,
                workspace_id=workspace.id,
                status="queued",
                command=command,
                created_at=iso_now(),
                created_by=actor.id,
                created_by_name=actor_name,
                chat_id=chat.get("id") if chat else None,
                chat_name=chat.get("name") if chat else None,
                log_path=str(log_path),
            )
            self._jobs[job_id] = job
            self._write_meta(job)
            thread = threading.Thread(
                target=self._run_job,
                args=(job, workspace, stdin_text, int(payload.get("timeout_seconds") or self.config.default_timeout_seconds)),
                daemon=True,
                name=f"codex-bridge-job-{job_id}",
            )
            thread.start()
            return job

    def _run_job(self, job: JobState, workspace: WorkspaceConfig, stdin_text: str, timeout_seconds: int) -> None:
        env = os.environ.copy()
        env.update(workspace.env)
        env["CODEX_HOME"] = str(workspace.codex_home)
        env["CODEX_BRIDGE_WORKSPACE_ID"] = workspace.id
        env.setdefault("NO_COLOR", "1")
        workspace.codex_home.mkdir(parents=True, exist_ok=True)

        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        try:
            self._update_job(job.id, status="running", started_at=iso_now())
            process = subprocess.Popen(
                job.command,
                cwd=str(workspace.path),
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=creationflags,
            )
            self._set_process(job.id, process)
            if process.stdin:
                process.stdin.write(stdin_text)
                if stdin_text and not stdin_text.endswith("\n"):
                    process.stdin.write("\n")
                process.stdin.close()

            deadline = time.monotonic() + max(30, timeout_seconds)
            assert process.stdout is not None
            reader = threading.Thread(
                target=self._read_output,
                args=(job.id, process.stdout),
                daemon=True,
                name=f"codex-bridge-reader-{job.id}",
            )
            reader.start()
            remaining = max(1, deadline - time.monotonic())
            try:
                exit_code = process.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                self._append_event(job.id, "system", "Job timeout reached; terminating process.")
                process.terminate()
                self._update_job(job.id, status="failed", error="timeout")
                try:
                    exit_code = process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    exit_code = process.wait(timeout=5)
            reader.join(timeout=2)
            with self._lock:
                current = self._jobs[job.id]
                if current.status == "cancelled":
                    current.exit_code = exit_code
                elif current.status == "failed" and current.error == "timeout":
                    current.exit_code = exit_code
                    current.ended_at = iso_now()
                elif exit_code == 0:
                    current.status = "completed"
                    current.exit_code = exit_code
                    current.ended_at = iso_now()
                else:
                    current.status = "failed"
                    current.exit_code = exit_code
                    current.ended_at = iso_now()
                current.process = None
                self._write_meta(current)
        except Exception as exc:  # noqa: BLE001 - keep worker errors visible in API.
            self._append_event(job.id, "system", f"{type(exc).__name__}: {exc}")
            self._update_job(job.id, status="failed", error=str(exc), ended_at=iso_now())

    def _read_output(self, job_id: str, stream: Any) -> None:
        try:
            for line in stream:
                self._append_event(job_id, "stdout", str(line).rstrip("\n"))
        finally:
            try:
                stream.close()
            except Exception:
                pass

    def cancel_job(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.status in TERMINAL_STATES:
                return False
            process = job.process
            job.status = "cancelled"
            job.ended_at = iso_now()
            self._write_meta(job)
        if process and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        self._append_event(job_id, "system", "Job cancelled.")
        return True

    def events(self, job_id: str, since: int = 0) -> list[dict[str, Any]]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return []
            return list(job.events[max(0, since) :])

    def audit_entries(self, limit: int = 100) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        for path in sorted(self.jobs_dir.glob("*/job.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            try:
                entries.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
            if len(entries) >= max(1, limit):
                break
        return entries

    def list_chats(
        self,
        workspace_id: str | None = None,
        user_name: str | None = None,
        include_all: bool = False,
    ) -> list[dict[str, Any]]:
        with self._lock:
            chats = list(self._load_chats().get("chats") or [])
        target_workspace = sanitize_id(workspace_id or "") if workspace_id else ""
        target_user = normalize_user_name(user_name or "")
        result: list[dict[str, Any]] = []
        for item in chats:
            if not isinstance(item, dict):
                continue
            if target_workspace and item.get("workspace_id") != target_workspace:
                continue
            owner = normalize_user_name(str(item.get("owner") or ""))
            if not include_all and owner and target_user and owner != target_user:
                continue
            if not include_all and owner and not target_user:
                continue
            result.append(dict(item))
        return sorted(result, key=lambda item: (str(item.get("workspace_id") or ""), str(item.get("name") or "")))

    def upsert_chat(
        self,
        workspace_id: str,
        chat_id: str | None,
        name: str | None,
        owner: str,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            data = self._load_chats()
            chat = self._upsert_chat(data, workspace_id, chat_id, name, owner, session_id)
            self._save_chats(data)
            return dict(chat)

    def chat_session_id(self, workspace_id: str, chat_id: str | None, owner: str | None = None) -> str:
        if not chat_id:
            return ""
        target = sanitize_id(str(chat_id))
        target_owner = normalize_user_name(owner or "")
        with self._lock:
            for item in self._load_chats().get("chats") or []:
                if not isinstance(item, dict):
                    continue
                if item.get("workspace_id") != workspace_id or item.get("id") != target:
                    continue
                item_owner = normalize_user_name(str(item.get("owner") or ""))
                if item_owner and target_owner and item_owner != target_owner:
                    continue
                return str(item.get("session_id") or "")
        return ""

    def _payload_chat(self, workspace_id: str, payload: dict[str, Any], actor_name: str) -> dict[str, Any] | None:
        chat_id = str(payload.get("chat_id") or "").strip()
        chat_name = str(payload.get("chat_name") or chat_id).strip()
        if not chat_id and not chat_name:
            return None
        data = self._load_chats()
        chat = self._upsert_chat(
            data,
            workspace_id,
            chat_id,
            chat_name,
            actor_name,
            str(payload.get("session_id") or "").strip(),
        )
        self._save_chats(data)
        return chat

    def _load_chats(self) -> dict[str, Any]:
        if not self.chats_path.exists():
            return {"version": 1, "chats": []}
        try:
            data = json.loads(self.chats_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"version": 1, "chats": []}
        if not isinstance(data, dict):
            return {"version": 1, "chats": []}
        data.setdefault("version", 1)
        data.setdefault("chats", [])
        return data

    def _save_chats(self, data: dict[str, Any]) -> None:
        self.chats_path.parent.mkdir(parents=True, exist_ok=True)
        self.chats_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _upsert_chat(
        self,
        data: dict[str, Any],
        workspace_id: str,
        chat_id: str | None,
        name: str | None,
        owner: str,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        chats = [item for item in data.get("chats") or [] if isinstance(item, dict)]
        normalized_workspace = sanitize_id(workspace_id)
        display_name = str(name or chat_id or "Новый чат").strip() or "Новый чат"
        normalized_chat_id = sanitize_id(str(chat_id or display_name))
        now = iso_now()
        for item in chats:
            if item.get("workspace_id") == normalized_workspace and item.get("id") == normalized_chat_id:
                item["name"] = display_name
                item["owner"] = owner.strip()
                item["updated_at"] = now
                if session_id:
                    item["session_id"] = session_id
                data["chats"] = chats
                return item
        chat = {
            "id": normalized_chat_id,
            "name": display_name,
            "workspace_id": normalized_workspace,
            "owner": owner.strip(),
            "session_id": session_id or "",
            "created_at": now,
            "updated_at": now,
        }
        chats.append(chat)
        data["chats"] = chats
        return chat

    def _set_process(self, job_id: str, process: subprocess.Popen[str]) -> None:
        with self._lock:
            self._jobs[job_id].process = process

    def _update_job(self, job_id: str, **updates: Any) -> None:
        with self._lock:
            job = self._jobs[job_id]
            for key, value in updates.items():
                setattr(job, key, value)
            self._write_meta(job)

    def _append_event(self, job_id: str, stream: str, text: str) -> None:
        event = {"index": 0, "ts": iso_now(), "stream": stream, "text": text}
        with self._lock:
            job = self._jobs[job_id]
            event["index"] = len(job.events)
            job.events.append(event)
            if len(job.events) > 2000:
                job.events = job.events[-2000:]
            if text.strip():
                job.last_message = text[-1000:]
            self._write_event(job, event)

    def _write_event(self, job: JobState, event: dict[str, Any]) -> None:
        if not job.log_path:
            return
        path = Path(job.log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            json.dump(event, fh, ensure_ascii=False)
            fh.write("\n")

    def _write_meta(self, job: JobState) -> None:
        if not job.log_path:
            return
        path = Path(job.log_path).with_name("job.json")
        data = job.public_dict()
        data["command"] = redact_command(job.command)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
