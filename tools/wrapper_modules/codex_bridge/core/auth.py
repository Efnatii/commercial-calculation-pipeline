from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso_now() -> str:
    return utc_now().isoformat().replace("+00:00", "Z")


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def token_hash(token: str) -> str:
    return "sha256:" + hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class TokenRecord:
    id: str
    name: str
    hash: str
    scopes: tuple[str, ...]
    workspaces: tuple[str, ...]
    created_at: str
    expires_at: str | None
    last_used_at: str | None
    disabled: bool

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TokenRecord":
        return cls(
            id=str(value.get("id") or ""),
            name=str(value.get("name") or ""),
            hash=str(value.get("hash") or ""),
            scopes=tuple(str(item) for item in value.get("scopes") or []),
            workspaces=tuple(str(item) for item in value.get("workspaces") or ["*"]),
            created_at=str(value.get("created_at") or ""),
            expires_at=value.get("expires_at"),
            last_used_at=value.get("last_used_at"),
            disabled=bool(value.get("disabled", False)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "hash": self.hash,
            "scopes": list(self.scopes),
            "workspaces": list(self.workspaces),
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "last_used_at": self.last_used_at,
            "disabled": self.disabled,
        }

    def public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "scopes": list(self.scopes),
            "workspaces": list(self.workspaces),
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "last_used_at": self.last_used_at,
            "disabled": self.disabled,
        }

    def has_scope(self, scope: str) -> bool:
        return "admin" in self.scopes or scope in self.scopes

    def has_workspace(self, workspace_id: str) -> bool:
        return "*" in self.workspaces or workspace_id in self.workspaces

    def is_expired(self) -> bool:
        expiry = parse_iso(self.expires_at)
        return bool(expiry and utc_now() >= expiry)


class TokenStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data = self._load()

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"version": 1, "tokens": []}
        with self.path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            raise ValueError(f"Token store root must be an object: {self.path}")
        data.setdefault("version", 1)
        data.setdefault("tokens", [])
        return data

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as fh:
            json.dump(self._data, fh, ensure_ascii=False, indent=2)
            fh.write("\n")

    def records(self) -> tuple[TokenRecord, ...]:
        return tuple(TokenRecord.from_dict(item) for item in self._data.get("tokens") or [])

    def create_token(
        self,
        name: str,
        scopes: list[str] | tuple[str, ...],
        workspaces: list[str] | tuple[str, ...] | None = None,
        ttl_days: int | None = None,
    ) -> tuple[str, TokenRecord]:
        token_id = uuid.uuid4().hex[:12]
        secret = secrets.token_urlsafe(32)
        token = f"cxb_{token_id}_{secret}"
        expires_at = None
        if ttl_days:
            expires_at = (utc_now() + timedelta(days=max(1, int(ttl_days)))).isoformat().replace("+00:00", "Z")
        record = TokenRecord(
            id=token_id,
            name=name.strip() or token_id,
            hash=token_hash(token),
            scopes=tuple(sorted(set(scopes or ["read"]))),
            workspaces=tuple(workspaces or ["*"]),
            created_at=iso_now(),
            expires_at=expires_at,
            last_used_at=None,
            disabled=False,
        )
        tokens = [item for item in self._data.get("tokens", []) if item.get("id") != token_id]
        tokens.append(record.to_dict())
        self._data["tokens"] = tokens
        self._save()
        return token, record

    def ensure_bootstrap_admin(self, bootstrap_file: Path) -> str | None:
        active_admin = [
            record
            for record in self.records()
            if not record.disabled and not record.is_expired() and record.has_scope("admin")
        ]
        if active_admin:
            return None
        token, _record = self.create_token("Стартовый админ", ["admin", "read", "run"], ["*"])
        bootstrap_file.parent.mkdir(parents=True, exist_ok=True)
        bootstrap_file.write_text(token + "\n", encoding="utf-8")
        return token

    def rotate_bootstrap_admin(self, bootstrap_file: Path) -> str:
        for item in self._data.get("tokens") or []:
            record = TokenRecord.from_dict(item)
            if record.name == "Стартовый админ" and not record.disabled:
                item["disabled"] = True
        token, _record = self.create_token("Стартовый админ", ["admin", "read", "run"], ["*"])
        bootstrap_file.parent.mkdir(parents=True, exist_ok=True)
        bootstrap_file.write_text(token + "\n", encoding="utf-8")
        return token

    def ensure_plaintext_token(
        self,
        token_file: Path,
        name: str,
        scopes: list[str] | tuple[str, ...],
        workspaces: list[str] | tuple[str, ...] | None = None,
    ) -> tuple[str, TokenRecord, bool]:
        required_workspaces = tuple(workspaces or ["*"])
        if token_file.exists():
            token = token_file.read_text(encoding="utf-8").strip()
            record = self.authenticate(token)
            if (
                record
                and all(record.has_scope(scope) for scope in scopes)
                and all(record.has_workspace(workspace) for workspace in required_workspaces)
            ):
                return token, record, False

        token, record = self.create_token(name, scopes, required_workspaces)
        token_file.parent.mkdir(parents=True, exist_ok=True)
        token_file.write_text(token + "\n", encoding="utf-8")
        return token, record, True

    def authenticate(self, token: str | None) -> TokenRecord | None:
        if not token:
            return None
        hashed = token_hash(token.strip())
        for index, item in enumerate(self._data.get("tokens") or []):
            record = TokenRecord.from_dict(item)
            if hmac.compare_digest(record.hash, hashed):
                if record.disabled or record.is_expired():
                    return None
                item["last_used_at"] = iso_now()
                self._data["tokens"][index] = item
                self._save()
                return TokenRecord.from_dict(item)
        return None

    def require(self, record: TokenRecord | None, scope: str, workspace_id: str | None = None) -> None:
        if record is None:
            raise PermissionError("Authentication required.")
        if not record.has_scope(scope):
            raise PermissionError(f"Missing token scope: {scope}")
        if workspace_id and not record.has_workspace(workspace_id):
            raise PermissionError(f"Token is not allowed for workspace: {workspace_id}")

    def revoke(self, token_id: str) -> bool:
        changed = False
        for item in self._data.get("tokens") or []:
            if item.get("id") == token_id and not item.get("disabled", False):
                item["disabled"] = True
                changed = True
        if changed:
            self._save()
        return changed
