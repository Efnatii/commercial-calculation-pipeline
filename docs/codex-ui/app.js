const state = {
  bridgeUrl: localStorage.getItem("codexBridge.url") || defaultBridgeUrl(),
  token: localStorage.getItem("codexBridge.token") || "",
  userName: localStorage.getItem("codexBridge.userName") || "Локальный админ",
  localMachineToken: "",
  workspaces: [],
  jobs: [],
  chats: [],
  tokens: [],
  auditEntries: [],
  capabilities: {},
  status: null,
  connected: false,
  serverOnline: false,
  activeJobId: null,
  jobFilter: "all",
  jobUserTabs: [],
  activeJobUser: "",
  tokenSort: "active",
  auditSort: "ended_desc",
  eventCursor: 0,
  pollTimer: null,
  healthTimer: null,
  workspaceConfigSaveTimer: null,
  workspaceConfigLoadSeq: 0,
  workspaceConfigDirty: false,
  workspaceConfigWorkspaceId: "",
};

const $ = (id) => document.getElementById(id);

const SHELLS = ["bash", "elvish", "fish", "powershell", "zsh"];
const SANDBOXES = ["workspace-write", "read-only", "danger-full-access"];
const APPROVALS = ["never", "on-request", "untrusted"];
const MODEL_CHOICES = [
  "",
  "gpt-5",
  "gpt-5-codex",
  "gpt-5-mini",
  "gpt-4.1",
  "o4-mini",
];
const HELP_TOPICS = [
  "codex",
  "exec",
  "exec-resume",
  "review",
  "doctor",
  "apply",
  "update",
  "completion",
  "debug",
  "debug-app-server",
  "cloud",
  "sandbox",
  "exec-server",
  "mcp-server",
  "app",
  "login",
  "mcp",
  "plugin",
  "features",
  "app-server",
  "app-server-proxy",
  "app-daemon",
  "remote-control",
];

const FIELD_META = {
  mode: {
    label: "Режим",
    type: "select",
    tooltip:
      "Обязательный режим Codex CLI. Список берется из /api/capabilities и совпадает с backend-командами Bridge.",
  },
  workspace_id: {
    label: "Среда",
    type: "workspace",
    tooltip:
      "ID рабочей среды Bridge. Сервер запускает Codex внутри этой среды и ее CODEX_HOME.",
  },
  chat_id: {
    label: "Чат",
    type: "chat",
    tooltip:
      "Чат внутри выбранной среды. Можно выбрать существующий чат из списка или вписать новое имя; сервер закрепит его за текущим пользователем.",
  },
  prompt: {
    label: "Текст задачи",
    type: "textarea",
    wide: true,
    tooltip:
      "Текст задачи, stdin или prompt. Для exec обязателен; для review/exec-resume передается через stdin при непустом значении.",
  },
  sandbox: {
    label: "Песочница",
    type: "select",
    options: SANDBOXES,
    default: "workspace-write",
    tooltip:
      "Уровень доступа Codex к файлам: read-only, workspace-write или danger-full-access, если он разрешен конфигом сервера.",
  },
  approval_policy: {
    label: "Подтверждения",
    type: "select",
    options: APPROVALS,
    default: "never",
    tooltip:
      "Политика запросов подтверждения Codex: never, on-request или untrusted.",
  },
  model: {
    label: "Модель",
    type: "model",
    tooltip:
      "Модель Codex. Пустое значение использует модель из рабочей среды или глобального конфига.",
  },
  profile: {
    label: "Профиль",
    type: "text",
    tooltip: "Значение --profile для Codex CLI.",
  },
  profile_v2: {
    label: "Профиль v2",
    type: "text",
    tooltip: "Значение --profile-v2 для Codex CLI.",
  },
  search: {
    label: "Поиск",
    type: "flag",
    default: false,
    tooltip: "Добавляет флаг --search для режимов, где Codex его поддерживает.",
  },
  no_alt_screen: {
    label: "Без alt-screen",
    type: "flag",
    default: true,
    tooltip: "Добавляет --no-alt-screen для интерактивных режимов resume/fork.",
  },
  images: {
    label: "Изображения",
    type: "list",
    wide: true,
    tooltip:
      "Пути к изображениям через точку с запятой. Относительные пути считаются от выбранной рабочей среды.",
  },
  add_dirs: {
    label: "Доп. папки",
    type: "list",
    wide: true,
    tooltip:
      "Дополнительные allowlisted папки через точку с запятой для exec (--add-dir).",
  },
  ephemeral: {
    label: "Временно",
    type: "flag",
    default: false,
    tooltip: "Добавляет --ephemeral для exec/exec-resume.",
  },
  skip_git_repo_check: {
    label: "Без git-проверки",
    type: "flag",
    default: false,
    tooltip: "Добавляет --skip-git-repo-check для exec/exec-resume.",
  },
  timeout_seconds: {
    label: "Таймаут, сек",
    type: "number",
    tooltip:
      "Ограничение времени выполнения задачи на сервере Bridge. Пусто означает default_timeout_seconds из конфига.",
  },
  session_id: {
    label: "Session ID",
    type: "text",
    tooltip: "ID Codex-сессии для resume/fork/exec-resume.",
  },
  last: {
    label: "Последняя",
    type: "flag",
    default: false,
    tooltip: "Добавляет --last вместо явного session_id.",
  },
  all: {
    label: "Все",
    type: "flag",
    default: false,
    tooltip: "Добавляет --all для resume/fork/exec-resume.",
  },
  include_non_interactive: {
    label: "Включить non-interactive",
    type: "flag",
    default: false,
    tooltip: "Добавляет --include-non-interactive для resume.",
  },
  uncommitted: {
    label: "Незакоммичено",
    type: "flag",
    default: true,
    tooltip: "Добавляет --uncommitted для review.",
  },
  base: {
    label: "Base",
    type: "text",
    tooltip: "Аргумент --base для review.",
  },
  commit: {
    label: "Commit",
    type: "text",
    tooltip: "Аргумент --commit для review.",
  },
  title: {
    label: "Заголовок",
    type: "text",
    tooltip: "Аргумент --title для review.",
  },
  summary: {
    label: "Summary",
    type: "flag",
    default: false,
    tooltip: "Добавляет --summary для doctor.",
  },
  task_id: {
    label: "Task ID",
    type: "text",
    tooltip: "ID локальной или cloud-задачи Codex для apply/status/diff.",
  },
  shell: {
    label: "Shell",
    type: "select",
    options: SHELLS,
    default: "powershell",
    tooltip: "Shell для генерации completion.",
  },
  bundled: {
    label: "Bundled",
    type: "flag",
    default: true,
    tooltip: "Добавляет --bundled для debug-models.",
  },
  message: {
    label: "Message",
    type: "textarea",
    wide: true,
    tooltip: "Сообщение для debug app-server send-message-v2.",
  },
  env_id: {
    label: "Environment ID",
    type: "text",
    tooltip: "ID Codex Cloud environment.",
  },
  limit: {
    label: "Limit",
    type: "number",
    tooltip: "Лимит строк для cloud-list.",
  },
  cursor: {
    label: "Cursor",
    type: "text",
    tooltip: "Cursor пагинации для cloud-list.",
  },
  attempt: {
    label: "Attempt",
    type: "number",
    tooltip: "Номер попытки для cloud diff/apply.",
  },
  attempts: {
    label: "Attempts",
    type: "number",
    tooltip: "Количество попыток для cloud-exec.",
  },
  branch: {
    label: "Branch",
    type: "text",
    tooltip: "Ветка для cloud-exec.",
  },
  command: {
    label: "Command",
    type: "shell",
    wide: true,
    tooltip:
      "Команда как строка shell; UI преобразует ее в JSON-массив argv для sandbox или stdio mcp-add.",
  },
  permissions_profile: {
    label: "Профиль прав",
    type: "text",
    tooltip: "Значение --permissions-profile для sandbox.",
  },
  include_managed_config: {
    label: "Managed config",
    type: "flag",
    default: false,
    tooltip: "Добавляет --include-managed-config для sandbox.",
  },
  allow_unix_sockets: {
    label: "Unix sockets",
    type: "list",
    wide: true,
    tooltip: "Список --allow-unix-socket для sandbox-macos.",
  },
  log_denials: {
    label: "Log denials",
    type: "flag",
    default: false,
    tooltip: "Добавляет --log-denials для sandbox-macos.",
  },
  listen: {
    label: "Listen",
    type: "text",
    default: "ws://127.0.0.1:0",
    tooltip: "Адрес прослушивания для exec-server/app-server.",
  },
  remote: {
    label: "Remote",
    type: "text",
    tooltip: "Remote endpoint для exec-server.",
  },
  environment_id: {
    label: "Environment ID",
    type: "text",
    tooltip: "Environment ID для exec-server.",
  },
  name: {
    label: "Name",
    type: "text",
    tooltip: "Имя MCP/server/exec-server объекта.",
  },
  use_agent_identity_auth: {
    label: "Agent identity auth",
    type: "flag",
    default: false,
    tooltip: "Добавляет --use-agent-identity-auth для exec-server.",
  },
  path: {
    label: "Path",
    type: "text",
    tooltip: "Путь для app-open. Пусто означает путь рабочей среды.",
  },
  download_url: {
    label: "Download URL",
    type: "text",
    tooltip: "URL установщика для app-open.",
  },
  ws_auth: {
    label: "WS auth",
    type: "select",
    options: ["", "capability-token", "signed-bearer-token"],
    tooltip: "Режим WebSocket auth для app-server.",
  },
  analytics_default_enabled: {
    label: "Analytics default",
    type: "flag",
    default: false,
    tooltip: "Добавляет --analytics-default-enabled для app-server.",
  },
  ws_token_file: {
    label: "WS token file",
    type: "text",
    tooltip: "Аргумент --ws-token-file.",
  },
  ws_token_sha256: {
    label: "WS token SHA256",
    type: "text",
    tooltip: "Аргумент --ws-token-sha256.",
  },
  ws_shared_secret_file: {
    label: "WS secret file",
    type: "text",
    tooltip: "Аргумент --ws-shared-secret-file.",
  },
  ws_issuer: {
    label: "WS issuer",
    type: "text",
    tooltip: "Аргумент --ws-issuer.",
  },
  ws_audience: {
    label: "WS audience",
    type: "text",
    tooltip: "Аргумент --ws-audience.",
  },
  ws_max_clock_skew_seconds: {
    label: "Clock skew, сек",
    type: "number",
    tooltip: "Аргумент --ws-max-clock-skew-seconds.",
  },
  sock: {
    label: "Socket",
    type: "text",
    tooltip: "Socket path для app-server proxy.",
  },
  out_dir: {
    label: "Out dir",
    type: "text",
    tooltip: "Папка вывода для app-server generate-*.",
  },
  prettier: {
    label: "Prettier",
    type: "text",
    tooltip: "Путь или команда prettier для generate-ts.",
  },
  experimental: {
    label: "Experimental",
    type: "flag",
    default: false,
    tooltip: "Добавляет --experimental для app-server generate-*.",
  },
  secret: {
    label: "Секрет",
    type: "secret",
    tooltip:
      "API key/access token. Значение отправляется как stdin и не должно храниться в истории.",
  },
  env: {
    label: "ENV JSON",
    type: "json",
    wide: true,
    default: {},
    tooltip: "JSON-объект переменных окружения для mcp-add.",
  },
  url: {
    label: "URL",
    type: "text",
    tooltip: "URL MCP-сервера для mcp-add.",
  },
  bearer_token_env_var: {
    label: "Bearer env",
    type: "text",
    tooltip: "Имя env-переменной с bearer token для MCP URL.",
  },
  scopes: {
    label: "Scopes",
    type: "text",
    tooltip: "OAuth scopes для mcp-login.",
  },
  marketplace: {
    label: "Marketplace",
    type: "text",
    tooltip: "Имя marketplace для plugin-команд.",
  },
  plugin: {
    label: "Plugin",
    type: "text",
    tooltip: "Имя плагина для plugin add/remove.",
  },
  source: {
    label: "Source",
    type: "text",
    tooltip: "Источник marketplace, например owner/repo.",
  },
  ref: {
    label: "Ref",
    type: "text",
    tooltip: "Git ref для plugin marketplace add.",
  },
  sparse: {
    label: "Sparse paths",
    type: "list",
    wide: true,
    tooltip: "Sparse пути через точку с запятой для plugin marketplace add.",
  },
  feature: {
    label: "Feature",
    type: "text",
    tooltip: "Имя функции для features enable/disable.",
  },
  remote_control: {
    label: "Remote control",
    type: "flag",
    default: false,
    tooltip: "Добавляет --remote-control для app-daemon-bootstrap.",
  },
  topic: {
    label: "Topic",
    type: "select",
    options: HELP_TOPICS,
    default: "codex",
    tooltip: "Whitelist topic для режима help.",
  },
  args: {
    label: "Raw args",
    type: "shell",
    wide: true,
    tooltip:
      "Raw Codex argv. Работает только если raw разрешен security-конфигом.",
  },
  stdin: {
    label: "STDIN",
    type: "textarea",
    wide: true,
    tooltip: "STDIN для raw-режима.",
  },
  extra_config: {
    label: "Extra config JSON",
    type: "json",
    wide: true,
    default: {},
    tooltip: "JSON-объект дополнительных -c key=value параметров Codex.",
  },
};

const MODE_FIELDS = {
  exec: [
    "prompt",
    "sandbox",
    "approval_policy",
    "model",
    "profile",
    "profile_v2",
    "search",
    "images",
    "add_dirs",
    "ephemeral",
    "skip_git_repo_check",
    "extra_config",
  ],
  "exec-resume": [
    "prompt",
    "session_id",
    "last",
    "all",
    "model",
    "images",
    "ephemeral",
    "skip_git_repo_check",
    "extra_config",
  ],
  resume: [
    "prompt",
    "session_id",
    "last",
    "all",
    "include_non_interactive",
    "sandbox",
    "approval_policy",
    "model",
    "profile",
    "profile_v2",
    "search",
    "no_alt_screen",
    "images",
    "extra_config",
  ],
  fork: [
    "prompt",
    "session_id",
    "last",
    "all",
    "sandbox",
    "approval_policy",
    "model",
    "profile",
    "profile_v2",
    "search",
    "no_alt_screen",
    "images",
    "extra_config",
  ],
  review: ["prompt", "uncommitted", "base", "commit", "title", "extra_config"],
  doctor: ["summary"],
  apply: ["task_id", "extra_config"],
  update: ["extra_config"],
  completion: ["shell", "extra_config"],
  "debug-models": ["bundled", "extra_config"],
  "debug-app-server-send-message-v2": ["message", "extra_config"],
  "debug-prompt-input": ["prompt", "images", "extra_config"],
  "cloud-list": ["env_id", "limit", "cursor", "extra_config"],
  "cloud-status": ["task_id", "extra_config"],
  "cloud-diff": ["task_id", "attempt", "extra_config"],
  "cloud-apply": ["task_id", "attempt", "extra_config"],
  "cloud-exec": ["env_id", "attempts", "branch", "prompt", "extra_config"],
  "sandbox-linux": [
    "command",
    "permissions_profile",
    "include_managed_config",
    "extra_config",
  ],
  "sandbox-macos": [
    "command",
    "permissions_profile",
    "include_managed_config",
    "allow_unix_sockets",
    "log_denials",
    "extra_config",
  ],
  "sandbox-windows": [
    "command",
    "permissions_profile",
    "include_managed_config",
    "extra_config",
  ],
  "exec-server-start": [
    "listen",
    "remote",
    "environment_id",
    "name",
    "use_agent_identity_auth",
    "extra_config",
  ],
  "mcp-server": ["extra_config"],
  "app-open": ["path", "download_url", "extra_config"],
  "app-server-start": [
    "listen",
    "analytics_default_enabled",
    "ws_auth",
    "ws_token_file",
    "ws_token_sha256",
    "ws_shared_secret_file",
    "ws_issuer",
    "ws_audience",
    "ws_max_clock_skew_seconds",
    "extra_config",
  ],
  "app-server-proxy": ["sock", "extra_config"],
  "app-server-generate-ts": [
    "out_dir",
    "prettier",
    "experimental",
    "extra_config",
  ],
  "app-server-generate-json-schema": [
    "out_dir",
    "experimental",
    "extra_config",
  ],
  "login-status": ["extra_config"],
  "login-api-key": ["secret", "extra_config"],
  "login-access-token": ["secret", "extra_config"],
  "login-device-auth": ["extra_config"],
  logout: ["extra_config"],
  "mcp-list": ["extra_config"],
  "mcp-get": ["name", "extra_config"],
  "mcp-add": [
    "name",
    "url",
    "command",
    "env",
    "bearer_token_env_var",
    "extra_config",
  ],
  "mcp-remove": ["name", "extra_config"],
  "mcp-login": ["name", "scopes", "extra_config"],
  "mcp-logout": ["name", "extra_config"],
  "plugin-list": ["marketplace", "extra_config"],
  "plugin-add": ["plugin", "marketplace", "extra_config"],
  "plugin-remove": ["plugin", "marketplace", "extra_config"],
  "plugin-marketplace-list": ["extra_config"],
  "plugin-marketplace-add": ["source", "ref", "sparse", "extra_config"],
  "plugin-marketplace-remove": ["marketplace", "extra_config"],
  "plugin-marketplace-upgrade": ["marketplace", "extra_config"],
  "features-list": ["extra_config"],
  "features-enable": ["feature", "extra_config"],
  "features-disable": ["feature", "extra_config"],
  "app-daemon-version": ["extra_config"],
  "app-daemon-bootstrap": ["remote_control", "extra_config"],
  "app-daemon-start": ["extra_config"],
  "app-daemon-restart": ["extra_config"],
  "app-daemon-stop": ["extra_config"],
  "app-daemon-enable-remote": ["extra_config"],
  "app-daemon-disable-remote": ["extra_config"],
  "remote-start": [],
  "remote-stop": [],
  help: ["topic"],
  raw: ["args", "stdin"],
};

function setText(id, value) {
  const el = $(id);
  if (el) el.textContent = value;
}

function statusClass(value) {
  return String(value || "pending")
    .toLowerCase()
    .replace(/[^a-z0-9-]/g, "-");
}

function statusLabel(value) {
  const labels = {
    pending: "ожидает",
    queued: "в очереди",
    running: "выполняется",
    completed: "завершена",
    failed: "ошибка",
    cancelled: "отменена",
    active: "активен",
    disabled: "отключен",
    revoked: "отозван",
  };
  const key = String(value || "pending").toLowerCase();
  return labels[key] || value || "";
}

function enabledLabel(value) {
  return value ? "включено" : "отключено";
}

function defaultBridgeUrl() {
  if (["127.0.0.1", "localhost"].includes(window.location.hostname)) {
    return window.location.origin;
  }
  return "http://127.0.0.1:8765";
}

function normalizeUrl(value) {
  return (value || "").trim().replace(/\/+$/, "");
}

function isLoopbackUrl(value) {
  try {
    const host = new URL(normalizeUrl(value)).hostname.toLowerCase();
    return host === "localhost" || host === "::1" || host.startsWith("127.");
  } catch {
    return false;
  }
}

function setBridgeTokenVisible(visible) {
  const input = $("bridgeToken");
  const button = $("toggleBridgeTokenVisibility");
  if (!input || !button) return;
  input.type = visible ? "text" : "password";
  button.setAttribute("aria-pressed", String(visible));
  button.setAttribute(
    "aria-label",
    visible ? "Скрыть токен" : "Показать токен",
  );
  button.title = visible ? "Скрыть токен" : "Показать токен";
}

function showToast(message) {
  const toast = $("toast");
  toast.textContent = message;
  toast.classList.add("is-visible");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(
    () => toast.classList.remove("is-visible"),
    2600,
  );
}

function setButtonLabel(id, label) {
  const button = $(id);
  if (!button) return;
  const textNode = button.querySelector("span:last-child") || button;
  textNode.textContent = label;
}

function updateConnectionControls() {
  setButtonLabel(
    "connectButton",
    state.connected ? "Переподключить" : "Подключить",
  );
  setButtonLabel(
    "serverPowerButton",
    state.serverOnline ? "Остановить" : "Запустить",
  );
  $("serverPowerButton")?.classList.toggle("is-danger", state.serverOnline);
}

function setStatus(online, label) {
  const el = $("serverStatus");
  state.serverOnline = Boolean(online);
  if (!online) state.connected = false;
  el.classList.toggle("is-online", online);
  el.querySelector("span:last-child").textContent = label;
  updateConnectionControls();
}

async function checkBridgeHealth() {
  state.bridgeUrl = normalizeUrl($("bridgeUrl")?.value || state.bridgeUrl);
  if (!state.bridgeUrl) {
    setStatus(false, "нет связи");
    return false;
  }
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), 1400);
  try {
    const response = await fetch(`${state.bridgeUrl}/health`, {
      cache: "no-store",
      signal: controller.signal,
    });
    if (!response.ok) throw new Error(`${response.status}`);
    const data = await response.json().catch(() => ({}));
    if (data.ok === false) throw new Error("health=false");
    setStatus(true, state.connected ? "онлайн" : "доступен");
    return true;
  } catch {
    setStatus(false, "нет связи");
    return false;
  } finally {
    window.clearTimeout(timer);
  }
}

function startHealthPolling() {
  window.clearInterval(state.healthTimer);
  checkBridgeHealth();
  state.healthTimer = window.setInterval(checkBridgeHealth, 3000);
}

async function api(path, options = {}) {
  const { skipAuth = false, ...fetchOptions } = options;
  const headers = new Headers(fetchOptions.headers || {});
  const userName = $("userNameInput")?.value.trim() || state.userName;
  if (userName)
    headers.set("X-Codex-Bridge-User", encodeURIComponent(userName));
  if (state.token && !skipAuth)
    headers.set("Authorization", `Bearer ${state.token}`);
  if (fetchOptions.body && !headers.has("Content-Type"))
    headers.set("Content-Type", "application/json");
  const response = await fetch(`${state.bridgeUrl}${path}`, {
    ...fetchOptions,
    headers,
    body: fetchOptions.body ? JSON.stringify(fetchOptions.body) : undefined,
  });
  const text = await response.text();
  const data = text ? JSON.parse(text) : {};
  if (!response.ok || data.ok === false) {
    throw new Error(data.error || `${response.status} ${response.statusText}`);
  }
  return data;
}

async function connect() {
  state.bridgeUrl = normalizeUrl($("bridgeUrl").value);
  state.userName = $("userNameInput").value.trim() || "Локальный админ";
  const enteredToken = $("bridgeToken").value.trim();
  state.token = enteredToken;
  localStorage.setItem("codexBridge.url", state.bridgeUrl);
  localStorage.setItem("codexBridge.userName", state.userName);
  if (state.token) {
    localStorage.setItem("codexBridge.token", state.token);
  } else {
    localStorage.removeItem("codexBridge.token");
  }

  try {
    const status = await api("/api/status");
    const capabilities = await api("/api/capabilities");
    state.status = status;
    state.workspaces = status.workspaces || [];
    state.jobs = status.jobs || [];
    state.capabilities = capabilities || {};
    state.connected = true;
    renderStatus(status);
    renderWorkspaces();
    renderWorkspaceSelect();
    await refreshChats();
    syncWorkspaceConfigFromAdminSelection({ fillMissingForm: true });
    renderJobs();
    renderModeSelect();
    renderModeHelp();
    syncCommandJsonFromControls();
    refreshTokens().catch(() => {});
    setStatus(true, "онлайн");
  } catch (error) {
    state.connected = false;
    setStatus(false, "нет связи");
    showToast(error.message);
  }
}

async function loadCurrentMachineToken() {
  state.bridgeUrl = normalizeUrl($("bridgeUrl").value);
  if (!isLoopbackUrl(state.bridgeUrl)) return;
  localStorage.setItem("codexBridge.url", state.bridgeUrl);
  const data = await api("/api/local-user-token", { skipAuth: true });
  state.localMachineToken = String(data.token || "").trim();
  if (state.localMachineToken) {
    $("bridgeToken").value = state.localMachineToken;
  }
}

function renderStatus(status) {
  const facts = $("serverFacts");
  const config = status.config || {};
  const server = config.server || {};
  const runtime = config.runtime || {};
  const lan = status.lan || {};
  renderHostMetrics(status, config, lan);
  facts.innerHTML = "";
  [
    ["Codex", status.codex_version || ""],
    ["Репозиторий", config.repo_root || ""],
    ["Состояние", config.state_dir || ""],
    ["Слушает", `${server.host || ""}:${server.port || ""}`],
    [
      "CORS",
      [
        ...(server.allowed_origins || []),
        ...(server.allowed_origin_patterns || []),
      ].join(", "),
    ],
    ["Макс. задач", runtime.max_concurrent_jobs || ""],
    ["Опасный режим", enabledLabel(config.security?.allow_danger_full_access)],
    ["Raw-аргументы", enabledLabel(config.security?.allow_raw_codex_args)],
    [
      "LAN без токена",
      config.security?.allow_lan_without_token
        ? (config.security?.no_auth_scopes || []).join(", ") || "включено"
        : "отключено",
    ],
    ["Прямой LAN UI", enabledLabel(config.security?.allow_lan_static_ui)],
    ["LAN health", enabledLabel(config.security?.allow_lan_health)],
    [
      "Локальный админ",
      enabledLabel(config.security?.allow_loopback_admin_without_token),
    ],
    ["LAN-хост", lan.hostname || ""],
    ["LAN Bridge", (lan.bridge_urls || []).join(", ") || ""],
    [
      "LAN UI на Bridge",
      lan.direct_static_ui_enabled
        ? (lan.ui_urls || []).join(", ")
        : "отключено",
    ],
    ["Локальный UI", lan.loopback_ui_url || ""],
  ].forEach(([key, value]) => {
    const dt = document.createElement("dt");
    const dd = document.createElement("dd");
    dt.textContent = key;
    dd.textContent = value;
    facts.append(dt, dd);
  });
}

function renderHostMetrics(status, config, lan) {
  const metrics = $("hostMetrics");
  if (!metrics) return;
  const server = config.server || {};
  const bridgeUrl =
    (lan.bridge_urls || [state.bridgeUrl])[0] || state.bridgeUrl;
  const activeJobs = (status.jobs || []).filter((job) =>
    ["queued", "running"].includes(String(job.status || "").toLowerCase()),
  ).length;
  metrics.innerHTML = [
    ["Состояние сервера", "РАБОТАЕТ"],
    [
      "Адрес",
      bridgeUrl.replace(/^https?:\/\//, "") ||
        `${server.host || ""}:${server.port || ""}`,
    ],
    ["Активные задачи", String(activeJobs)],
    ["Среды", String((status.workspaces || []).length)],
  ]
    .map(
      ([label, value]) => `
        <div class="metric">
          <span>${escapeHtml(label)}</span>
          <strong>${escapeHtml(value)}</strong>
        </div>`,
    )
    .join("");
  setText(
    "hostCaption",
    `${status.codex_version || "Codex CLI"} на ${lan.hostname || "локальном хосте"}`,
  );
}

function renderWorkspaceSelect() {
  const select = $("workspaceSelect");
  const formWorkspaceId = $("workspaceIdInput")?.value.trim();
  const previous = select.value || formWorkspaceId;
  select.innerHTML = "";
  if (!state.workspaces.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "Нет среды";
    select.appendChild(option);
    return;
  }
  state.workspaces.forEach((workspace) => {
    const option = document.createElement("option");
    option.value = workspace.id;
    option.textContent = workspace.name || workspace.id;
    select.appendChild(option);
  });
  const selected = state.workspaces.some(
    (workspace) => workspace.id === previous,
  )
    ? previous
    : state.workspaces[0]?.id || "";
  if (selected) select.value = selected;
  syncCommandJsonFromControls();
}

function renderWorkspaces() {
  const list = $("workspaceCards");
  list.innerHTML = "";
  state.workspaces.forEach((workspace) => {
    const item = document.createElement("div");
    item.className = "item-row";
    item.innerHTML = `
      <strong>${escapeHtml(workspace.name || workspace.id)}</strong>
      <code>владелец=${escapeHtml(workspace.owner || "общая")}</code>
      <code>${escapeHtml(workspace.path || "")}</code>
      <code>CODEX_HOME=${escapeHtml(workspace.codex_home || "")}</code>
      <code>${escapeHtml(workspace.default_model || "модель по умолчанию")} / ${escapeHtml(workspace.default_sandbox || "")}</code>
      <div class="item-actions">
        <button class="button ghost" data-edit-workspace="${escapeHtml(workspace.id)}">Изменить</button>
        <button class="button ghost" data-delete-workspace="${escapeHtml(workspace.id)}">Удалить</button>
      </div>
    `;
    list.appendChild(item);
  });
  list
    .querySelectorAll("[data-edit-workspace]")
    .forEach((button) =>
      button.addEventListener("click", () =>
        fillWorkspaceForm(button.dataset.editWorkspace),
      ),
    );
  list
    .querySelectorAll("[data-delete-workspace]")
    .forEach((button) =>
      button.addEventListener("click", () =>
        deleteWorkspace(button.dataset.deleteWorkspace).catch((error) =>
          showToast(error.message),
        ),
      ),
    );
  renderWorkspaceMiniList();
}

function renderWorkspaceMiniList() {
  const list = $("workspaceMiniList");
  if (!list) return;
  if (!state.workspaces.length) {
    list.innerHTML = `<div class="mini-item"><strong>Сред нет</strong><span>Подключитесь к Bridge</span></div>`;
    return;
  }
  list.innerHTML = state.workspaces
    .slice(0, 4)
    .map(
      (workspace) => `
        <div class="mini-item">
          <div>
            <strong>${escapeHtml(workspace.name || workspace.id)}</strong>
            <span>${escapeHtml(workspace.default_sandbox || "workspace-write")}</span>
          </div>
          <span class="status-tag">активна</span>
        </div>`,
    )
    .join("");
}

function isActiveJob(job) {
  return ["pending", "queued", "running"].includes(
    String(job.status || "").toLowerCase(),
  );
}

function isErrorJob(job) {
  const status = String(job.status || "").toLowerCase();
  return (
    status === "failed" ||
    status === "cancelled" ||
    Number(job.exit_code || 0) !== 0
  );
}

function visibleJobs() {
  if (!state.activeJobUser) return [];
  return state.jobs.filter((job) => jobUserName(job) === state.activeJobUser);
}

function jobUserName(job) {
  return job.created_by_name || job.created_by || "без имени";
}

function availableJobUsers() {
  return [...new Set(state.jobs.map(jobUserName))].sort((a, b) =>
    a.localeCompare(b, "ru"),
  );
}

function addJobUserTab(userName) {
  const name = String(userName || "").trim();
  if (
    !name ||
    state.jobUserTabs.includes(name) ||
    state.jobUserTabs.length >= 6
  )
    return;
  state.jobUserTabs.push(name);
  state.activeJobUser = name;
  renderJobs();
}

function removeJobUserTab(userName) {
  state.jobUserTabs = state.jobUserTabs.filter((item) => item !== userName);
  if (state.activeJobUser === userName) {
    state.activeJobUser = state.jobUserTabs[0] || "";
  }
  renderJobs();
}

function renderJobUserTabs() {
  const tabs = $("jobUserTabs");
  const picker = $("jobUserSelect");
  const plus = $("addJobUserTabButton");
  if (!tabs || !picker || !plus) return;
  state.jobUserTabs = state.jobUserTabs.filter((name) =>
    availableJobUsers().includes(name),
  );
  if (state.activeJobUser && !state.jobUserTabs.includes(state.activeJobUser)) {
    state.activeJobUser = state.jobUserTabs[0] || "";
  }
  tabs.innerHTML = state.jobUserTabs
    .map(
      (name) => `
        <span class="job-user-tab ${name === state.activeJobUser ? "is-active" : ""}">
          <button type="button" data-job-user-tab="${escapeHtml(name)}">${escapeHtml(name)}</button>
          <button type="button" data-job-user-close="${escapeHtml(name)}" title="Закрыть вкладку">×</button>
        </span>`,
    )
    .join("");
  tabs.querySelectorAll("[data-job-user-tab]").forEach((button) =>
    button.addEventListener("click", () => {
      state.activeJobUser = button.dataset.jobUserTab || "";
      renderJobs();
    }),
  );
  tabs
    .querySelectorAll("[data-job-user-close]")
    .forEach((button) =>
      button.addEventListener("click", () =>
        removeJobUserTab(button.dataset.jobUserClose || ""),
      ),
    );
  const remaining = availableJobUsers().filter(
    (name) => !state.jobUserTabs.includes(name),
  );
  picker.innerHTML = [
    `<option value="">${remaining.length ? "Выбрать пользователя" : "Нет пользователей в истории"}</option>`,
    ...remaining.map(
      (name) =>
        `<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`,
    ),
  ].join("");
  plus.disabled = state.jobUserTabs.length >= 6 || !remaining.length;
}

function renderJobs() {
  const body = $("jobsTable");
  const list = $("jobsHistoryList");
  renderJobUserTabs();
  const jobs = visibleJobs();
  if (body) body.innerHTML = "";
  if (body) {
    jobs.forEach((job) => {
      const row = document.createElement("tr");
      const cssClass = statusClass(job.status);
      row.innerHTML = `
        <td>${escapeHtml(job.id)}</td>
        <td>${escapeHtml(job.mode)}</td>
        <td>${escapeHtml(job.workspace_id)}</td>
        <td><span class="status-tag ${cssClass}">${escapeHtml(statusLabel(job.status))}</span></td>
        <td>${job.exit_code ?? ""}</td>
        <td>${escapeHtml(job.created_at || "")}</td>
      `;
      row.addEventListener("click", () => selectJob(job.id));
      body.appendChild(row);
    });
  }
  if (list) {
    if (!state.jobUserTabs.length) {
      list.innerHTML = `<div class="job-empty">Нажмите + и выберите пользователя</div>`;
    } else if (!state.activeJobUser) {
      list.innerHTML = `<div class="job-empty">Выберите вкладку пользователя</div>`;
    } else if (!jobs.length) {
      list.innerHTML = `<div class="job-empty">У пользователя ${escapeHtml(state.activeJobUser)} задач нет</div>`;
    } else {
      list.innerHTML = jobs
        .map((job) => {
          const cssClass = statusClass(job.status);
          const activeClass = job.id === state.activeJobId ? " is-active" : "";
          const exitCode = job.exit_code ?? "—";
          return `
            <button class="job-card${activeClass}" data-job-id="${escapeHtml(job.id)}" type="button">
              <div class="job-main">
                <strong>${escapeHtml(job.mode || "задача")}</strong>
                <code>${escapeHtml(job.id || "")}</code>
              </div>
              <div class="job-meta">
                <span>Среда: ${escapeHtml(job.workspace_id || "main")}</span>
                <span>Чат: ${escapeHtml(job.chat_name || job.chat_id || "без чата")}</span>
                <span>Код: ${escapeHtml(exitCode)}</span>
              </div>
              <div class="job-time">
                <span>${escapeHtml(job.created_at || "")}</span>
                <span>${escapeHtml(job.completed_at || "")}</span>
              </div>
              <span class="status-tag ${cssClass}">${escapeHtml(statusLabel(job.status))}</span>
            </button>`;
        })
        .join("");
      list
        .querySelectorAll("[data-job-id]")
        .forEach((item) =>
          item.addEventListener("click", () => selectJob(item.dataset.jobId)),
        );
    }
  }
  renderCurrentJobsPreview();
  if (state.status)
    renderHostMetrics(
      state.status,
      state.status.config || {},
      state.status.lan || {},
    );
}

function renderCurrentJobsPreview() {
  const list = $("currentJobsPreview");
  if (!list) return;
  const jobs = state.jobs.slice(0, 5);
  if (!jobs.length) {
    list.innerHTML = `<div class="mini-item"><strong>Задач пока нет</strong><span>Очередь свободна</span></div>`;
    return;
  }
  list.innerHTML = jobs
    .map(
      (job) => `
        <div class="mini-item">
          <div>
            <strong>${escapeHtml(job.mode || "задача")}</strong>
            <span>${escapeHtml(job.id || "")} / ${escapeHtml(job.workspace_id || "")}</span>
          </div>
          <span class="status-tag ${statusClass(job.status)}">${escapeHtml(statusLabel(job.status || "pending"))}</span>
        </div>`,
    )
    .join("");
}

function renderActivityTimeline() {
  const timeline = $("activityTimeline");
  if (!timeline) return;
  const jobs = state.jobs.slice(0, 6);
  if (!jobs.length) {
    timeline.innerHTML = "";
    return;
  }
  timeline.innerHTML = jobs
    .map(
      (job) => `
        <div class="timeline-node ${statusClass(job.status)}">
          <strong>${escapeHtml(statusLabel(job.status || "pending"))}</strong>
          <span>${escapeHtml(job.mode || "")}</span>
          <span>${escapeHtml(job.workspace_id || "")}</span>
        </div>`,
    )
    .join("");
}

async function refreshJobs() {
  const data = await api("/api/jobs");
  state.jobs = data.jobs || [];
  renderJobs();
}

async function refreshWorkspaces() {
  const data = await api("/api/workspaces");
  state.workspaces = data.workspaces || [];
  renderWorkspaceSelect();
  renderWorkspaces();
  await refreshChats();
  syncWorkspaceConfigFromAdminSelection({ fillMissingForm: true });
}

async function refreshChats(workspaceId = "") {
  const query = workspaceId
    ? `?workspace_id=${encodeURIComponent(workspaceId)}`
    : "";
  const data = await api(`/api/chats${query}`);
  const incoming = data.chats || [];
  if (workspaceId) {
    state.chats = [
      ...state.chats.filter((chat) => chat.workspace_id !== workspaceId),
      ...incoming,
    ];
  } else {
    state.chats = incoming;
  }
  renderChatOptions();
  try {
    renderCommandParameterEditor(readCommandBody({ silent: true }));
  } catch {
    // Keep chat refresh independent from a temporarily invalid JSON draft.
  }
}

function renderChatOptions() {
  const list = $("chatOptions");
  if (!list) return;
  list.innerHTML = state.chats
    .map(
      (chat) =>
        `<option value="${escapeHtml(chat.id)}" label="${escapeHtml(chat.name || chat.id)}"></option>`,
    )
    .join("");
}

async function refreshTokens() {
  const data = await api("/api/tokens");
  state.tokens = data.tokens || [];
  renderTokensList();
}

function sortedTokens() {
  const tokens = [...state.tokens];
  const byText = (a, b, key) =>
    String(a[key] || "").localeCompare(String(b[key] || ""), "ru");
  if (state.tokenSort === "name")
    return tokens.sort((a, b) => byText(a, b, "name"));
  if (state.tokenSort === "created_asc")
    return tokens.sort((a, b) =>
      String(a.created_at || "").localeCompare(String(b.created_at || "")),
    );
  if (state.tokenSort === "created_desc")
    return tokens.sort((a, b) =>
      String(b.created_at || "").localeCompare(String(a.created_at || "")),
    );
  return tokens.sort(
    (a, b) =>
      Number(Boolean(a.disabled)) - Number(Boolean(b.disabled)) ||
      byText(a, b, "name"),
  );
}

function renderTokensList() {
  const list = $("tokensList");
  list.innerHTML = "";
  sortedTokens().forEach((token) => {
    const item = document.createElement("div");
    item.className = "item-row";
    const disabled = token.disabled ? "отключен" : "активен";
    item.innerHTML = `
      <strong>${escapeHtml(token.name)} <span class="status-tag ${token.disabled ? "revoked" : ""}">${escapeHtml(disabled)}</span></strong>
      <code>${escapeHtml(token.id)} / ${escapeHtml((token.scopes || []).join(","))}</code>
      <code>${escapeHtml((token.workspaces || []).join(","))}</code>
      <div class="item-actions">
        <button class="button ghost" data-revoke-token="${escapeHtml(token.id)}" ${token.disabled ? "disabled" : ""}>Отозвать</button>
      </div>
    `;
    list.appendChild(item);
  });
  list
    .querySelectorAll("[data-revoke-token]")
    .forEach((button) =>
      button.addEventListener("click", () =>
        revokeToken(button.dataset.revokeToken).catch((error) =>
          showToast(error.message),
        ),
      ),
    );
}

async function refreshAudit() {
  const data = await api("/api/audit?limit=100");
  state.auditEntries = data.entries || [];
  renderAuditTable();
}

function sortedAuditEntries() {
  const entries = [...state.auditEntries];
  const byText = (a, b, key) =>
    String(a[key] || "").localeCompare(String(b[key] || ""), "ru");
  if (state.auditSort === "ended_asc")
    return entries.sort((a, b) =>
      String(a.ended_at || "").localeCompare(String(b.ended_at || "")),
    );
  if (state.auditSort === "mode")
    return entries.sort((a, b) => byText(a, b, "mode"));
  if (state.auditSort === "status")
    return entries.sort((a, b) => byText(a, b, "status"));
  if (state.auditSort === "user")
    return entries.sort(
      (a, b) => byText(a, b, "created_by_name") || byText(a, b, "created_by"),
    );
  return entries.sort((a, b) =>
    String(b.ended_at || "").localeCompare(String(a.ended_at || "")),
  );
}

function renderAuditTable() {
  const body = $("auditTable");
  body.innerHTML = "";
  sortedAuditEntries().forEach((entry) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${escapeHtml(entry.id || "")}</td>
      <td>${escapeHtml(entry.mode || "")}</td>
      <td>${escapeHtml(entry.workspace_id || "")}</td>
      <td>${escapeHtml(entry.status || "")}</td>
      <td>${escapeHtml(entry.created_by_name || entry.created_by || "")}</td>
      <td>${escapeHtml(entry.ended_at || "")}</td>
    `;
    body.appendChild(row);
  });
}

async function createToken() {
  const scopes = [...document.querySelectorAll(".scope-row input:checked")].map(
    (node) => node.value,
  );
  const workspaces = $("tokenWorkspaces")
    .value.split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  const ttl = Number($("tokenTtl").value);
  const data = await api("/api/tokens", {
    method: "POST",
    body: {
      name: $("tokenName").value,
      scopes,
      workspaces: workspaces.length ? workspaces : ["*"],
      ttl_days: ttl || undefined,
    },
  });
  $("createdToken").textContent = data.token;
  await refreshTokens();
}

async function revokeToken(tokenId) {
  await api(`/api/tokens/${encodeURIComponent(tokenId)}`, { method: "DELETE" });
  await refreshTokens();
}

function setWorkspaceConfigStatus(message, stateName = "") {
  const status = $("workspaceConfigStatus");
  if (!status) return;
  status.textContent = message || "";
  status.classList.toggle("is-saving", stateName === "saving");
  status.classList.toggle("is-error", stateName === "error");
}

function workspaceById(workspaceId) {
  return state.workspaces.find((workspace) => workspace.id === workspaceId);
}

function selectedWorkspaceIdForAdmin() {
  return $("workspaceIdInput").value.trim() || $("workspaceSelect").value;
}

function clearWorkspaceConfig(message) {
  window.clearTimeout(state.workspaceConfigSaveTimer);
  state.workspaceConfigSaveTimer = null;
  state.workspaceConfigDirty = false;
  state.workspaceConfigWorkspaceId = "";
  state.workspaceConfigLoadSeq += 1;
  $("workspaceConfigInput").value = "";
  $("workspaceConfigInput").disabled = true;
  setWorkspaceConfigStatus(message);
}

function syncWorkspaceConfigFromAdminSelection(options = {}) {
  const formWorkspaceId = $("workspaceIdInput").value.trim();
  if (formWorkspaceId && !workspaceById(formWorkspaceId)) {
    clearWorkspaceConfig("Сначала сохраните среду");
    return;
  }
  const selectedWorkspaceId = formWorkspaceId || $("workspaceSelect").value;
  const workspace = workspaceById(selectedWorkspaceId) || state.workspaces[0];
  if (!workspace) {
    clearWorkspaceConfig("Нет сохраненной среды");
    return;
  }
  if (options.fillMissingForm && !formWorkspaceId) {
    fillWorkspaceForm(workspace.id, { loadConfig: false });
  }
  loadWorkspaceConfig(workspace.id).catch((error) => {
    setWorkspaceConfigStatus(error.message, "error");
    showToast(error.message);
  });
}

function fillWorkspaceForm(workspaceId, options = {}) {
  const workspace = state.workspaces.find((item) => item.id === workspaceId);
  if (!workspace) return;
  $("workspaceIdInput").value = workspace.id || "";
  $("workspaceNameInput").value = workspace.name || "";
  $("workspaceOwnerInput").value = workspace.owner || state.userName || "";
  $("workspacePathInput").value = workspace.path || "";
  $("workspaceCodexHomeInput").value = workspace.codex_home || "";
  $("workspaceModelInput").value = workspace.default_model || "";
  $("workspaceProfileInput").value = workspace.default_profile || "";
  $("workspaceProfileV2Input").value = workspace.default_profile_v2 || "";
  $("workspaceSandboxInput").value =
    workspace.default_sandbox || "workspace-write";
  $("workspaceApprovalInput").value = workspace.approval_policy || "never";
  $("workspaceDirsInput").value = (
    workspace.allowed_additional_dirs || []
  ).join("; ");
  $("workspaceEnvInput").value = "{}";
  $("workspaceSelect").value = workspace.id;
  if (options.loadConfig !== false) {
    loadWorkspaceConfig(workspace.id).catch((error) => {
      setWorkspaceConfigStatus(error.message, "error");
      showToast(error.message);
    });
  }
}

async function saveWorkspace() {
  let env = {};
  const rawEnv = $("workspaceEnvInput").value.trim();
  if (rawEnv) {
    env = JSON.parse(rawEnv);
  }
  const dirs = $("workspaceDirsInput")
    .value.split(";")
    .map((item) => item.trim())
    .filter(Boolean);
  await api("/api/workspaces", {
    method: "POST",
    body: {
      id: $("workspaceIdInput").value,
      name: $("workspaceNameInput").value,
      owner: $("workspaceOwnerInput").value.trim() || state.userName,
      path: $("workspacePathInput").value || ".",
      codex_home: $("workspaceCodexHomeInput").value || undefined,
      default_model: $("workspaceModelInput").value,
      default_profile: $("workspaceProfileInput").value,
      default_profile_v2: $("workspaceProfileV2Input").value,
      default_sandbox: $("workspaceSandboxInput").value,
      approval_policy: $("workspaceApprovalInput").value,
      allowed_additional_dirs: dirs,
      env,
      enabled: true,
    },
  });
  await refreshWorkspaces();
  showToast("Среда сохранена");
}

async function deleteWorkspace(workspaceId) {
  await api(`/api/workspaces/${encodeURIComponent(workspaceId)}`, {
    method: "DELETE",
  });
  await refreshWorkspaces();
}

async function loadWorkspaceConfig(
  workspaceId = selectedWorkspaceIdForAdmin(),
) {
  if (!workspaceId) throw new Error("Нужен ID рабочей среды.");
  if (!workspaceById(workspaceId)) {
    clearWorkspaceConfig("Сначала сохраните среду");
    return;
  }
  window.clearTimeout(state.workspaceConfigSaveTimer);
  state.workspaceConfigSaveTimer = null;
  state.workspaceConfigDirty = false;
  state.workspaceConfigWorkspaceId = workspaceId;
  const loadSeq = (state.workspaceConfigLoadSeq += 1);
  $("workspaceConfigInput").disabled = true;
  setWorkspaceConfigStatus("загрузка...", "saving");
  const data = await api(
    `/api/workspaces/${encodeURIComponent(workspaceId)}/codex-config`,
  );
  if (
    loadSeq !== state.workspaceConfigLoadSeq ||
    selectedWorkspaceIdForAdmin() !== workspaceId ||
    state.workspaceConfigDirty
  ) {
    return;
  }
  $("workspaceConfigInput").value = data.text || "";
  $("workspaceConfigInput").disabled = false;
  state.workspaceConfigWorkspaceId = workspaceId;
  setWorkspaceConfigStatus(data.text ? "загружено" : "файл пока пустой");
}

async function saveWorkspaceConfig() {
  const workspaceId = selectedWorkspaceIdForAdmin();
  if (!workspaceId) throw new Error("Нужен ID рабочей среды.");
  if (!workspaceById(workspaceId)) {
    clearWorkspaceConfig("Сначала сохраните среду");
    return;
  }
  window.clearTimeout(state.workspaceConfigSaveTimer);
  state.workspaceConfigSaveTimer = null;
  const text = $("workspaceConfigInput").value;
  setWorkspaceConfigStatus("сохранение...", "saving");
  await api(`/api/workspaces/${encodeURIComponent(workspaceId)}/codex-config`, {
    method: "POST",
    body: { text },
  });
  if (selectedWorkspaceIdForAdmin() !== workspaceId) return;
  if ($("workspaceConfigInput").value !== text) {
    scheduleWorkspaceConfigSave(450);
    return;
  }
  state.workspaceConfigDirty = false;
  state.workspaceConfigWorkspaceId = workspaceId;
  setWorkspaceConfigStatus("сохранено");
}

function scheduleWorkspaceConfigSave(delay = 750) {
  if ($("workspaceConfigInput").disabled) return;
  state.workspaceConfigDirty = true;
  setWorkspaceConfigStatus("ожидает автосохранения", "saving");
  window.clearTimeout(state.workspaceConfigSaveTimer);
  state.workspaceConfigSaveTimer = window.setTimeout(() => {
    state.workspaceConfigSaveTimer = null;
    saveWorkspaceConfig().catch((error) => {
      setWorkspaceConfigStatus(error.message, "error");
      showToast(error.message);
    });
  }, delay);
}

function commandModes() {
  const modes = Array.isArray(state.capabilities.modes)
    ? state.capabilities.modes
    : [];
  return modes.length
    ? modes
    : ["exec", "review", "help", "mcp-list", "plugin-list", "doctor"];
}

function activeCommandKeys(mode) {
  const keys = [
    "mode",
    "workspace_id",
    "chat_id",
    ...(MODE_FIELDS[mode] || []),
    "timeout_seconds",
  ];
  return [...new Set(keys)];
}

function isEmptyCommandValue(value) {
  if (value === undefined || value === null || value === "") return true;
  if (Array.isArray(value)) return value.length === 0;
  if (typeof value === "object") return Object.keys(value).length === 0;
  return false;
}

function defaultFieldValue(key) {
  const spec = FIELD_META[key] || {};
  if (key === "mode") return $("modeSelect")?.value || "exec";
  if (key === "workspace_id") return $("workspaceSelect")?.value || "main";
  if (key === "chat_id")
    return (
      firstChatForWorkspace($("workspaceSelect")?.value || "main")?.id || ""
    );
  if (Object.hasOwn(spec, "default")) return structuredClone(spec.default);
  if (spec.type === "flag") return false;
  if (spec.type === "list" || spec.type === "shell") return [];
  if (spec.type === "json") return {};
  if (spec.type === "number") return null;
  return "";
}

function defaultCommandBody(
  mode = $("modeSelect")?.value || "exec",
  previous = {},
) {
  const body = {
    mode,
    workspace_id:
      previous.workspace_id || $("workspaceSelect")?.value || "main",
  };
  activeCommandKeys(mode).forEach((key) => {
    if (key === "mode" || key === "workspace_id") return;
    const spec = FIELD_META[key] || {};
    const value = Object.hasOwn(previous, key)
      ? previous[key]
      : defaultFieldValue(key);
    if (
      spec.type === "flag" ||
      Object.hasOwn(spec, "default") ||
      !isEmptyCommandValue(value)
    ) {
      body[key] = value;
    }
  });
  return normalizeCommandBody(body);
}

function setCommandJsonStatus(message, variant = "") {
  const status = $("commandJsonStatus");
  if (!status) return;
  status.textContent = message;
  status.classList.toggle("is-saving", variant === "saving");
  status.classList.toggle("is-error", variant === "error");
}

function writeCommandJson(body) {
  const input = $("commandJsonInput");
  if (!input) return;
  input.value = JSON.stringify(normalizeCommandBody(body), null, 2);
  setCommandJsonStatus("шаблон готов");
}

function listFromText(value) {
  if (Array.isArray(value)) return value.map(String).filter(Boolean);
  return String(value || "")
    .split(";")
    .map((item) => item.trim())
    .filter(Boolean);
}

function normalizeCommandBody(body) {
  const source =
    body && typeof body === "object" && !Array.isArray(body) ? { ...body } : {};
  const mode = String(source.mode || $("modeSelect")?.value || "exec");
  const normalized = {
    mode,
    workspace_id: String(
      source.workspace_id || $("workspaceSelect")?.value || "main",
    ),
  };
  activeCommandKeys(mode).forEach((key) => {
    if (key === "mode" || key === "workspace_id") return;
    const spec = FIELD_META[key] || {};
    let value = Object.hasOwn(source, key)
      ? source[key]
      : defaultFieldValue(key);
    if (spec.type === "list") value = listFromText(value);
    if (spec.type === "shell" && typeof value === "string")
      value = parseCommandLine(value);
    if (spec.type === "flag") value = Boolean(value);
    if (spec.type === "number") {
      value =
        value === "" || value === null || value === undefined
          ? null
          : Number(value);
      if (Number.isNaN(value)) value = null;
    }
    if (
      spec.type === "json" &&
      (value === "" || value === null || value === undefined)
    ) {
      value = {};
    }
    if (
      spec.type === "select" &&
      Array.isArray(spec.options) &&
      value === undefined
    ) {
      value = spec.options[0] || "";
    }
    if (
      spec.type === "flag" ||
      Object.hasOwn(spec, "default") ||
      !isEmptyCommandValue(value)
    ) {
      normalized[key] = value;
    }
  });
  return normalized;
}

function readCommandBody({ silent = false } = {}) {
  const input = $("commandJsonInput");
  if (!input) return defaultCommandBody();
  try {
    const body = normalizeCommandBody(JSON.parse(input.value || "{}"));
    if (!silent) setCommandJsonStatus("JSON корректен");
    return body;
  } catch (error) {
    if (!silent) setCommandJsonStatus("ошибка JSON", "error");
    throw new Error(`JSON команды не читается: ${error.message}`);
  }
}

function syncCommandJsonFromControls({ forceEmpty = false } = {}) {
  const input = $("commandJsonInput");
  if (!input) return;
  let body;
  try {
    const currentText = input.value.trim();
    body =
      !currentText || forceEmpty
        ? defaultCommandBody()
        : defaultCommandBody(
            JSON.parse(currentText).mode || $("modeSelect")?.value || "exec",
            JSON.parse(currentText),
          );
  } catch {
    body = defaultCommandBody();
  }
  if ($("modeSelect")) $("modeSelect").value = body.mode;
  if ($("workspaceSelect") && body.workspace_id)
    $("workspaceSelect").value = body.workspace_id;
  writeCommandJson(body);
  renderCommandParameterEditor(body);
}

function renderModeSelect() {
  const select = $("modeSelect");
  if (!select) return;
  const previous = select.value || "exec";
  const values = commandModes();
  select.innerHTML = "";
  values.forEach((mode) => {
    const option = document.createElement("option");
    option.value = mode;
    option.textContent = mode;
    select.appendChild(option);
  });
  select.value = values.includes(previous) ? previous : values[0] || "exec";
  syncCommandJsonFromControls();
}

function firstChatForWorkspace(workspaceId) {
  return state.chats.find((chat) => chat.workspace_id === workspaceId);
}

function modelOptions() {
  const configured = Array.isArray(state.capabilities.models)
    ? state.capabilities.models
    : [];
  const workspaceModels = state.workspaces
    .map((workspace) => workspace.default_model)
    .filter(Boolean);
  return [
    ...new Set(["", ...configured, ...workspaceModels, ...MODEL_CHOICES]),
  ];
}

function fieldOptions(key, body) {
  if (key === "mode") return commandModes();
  if (key === "workspace_id") {
    return state.workspaces.length
      ? state.workspaces.map((workspace) => ({
          value: workspace.id,
          label: workspace.name || workspace.id,
        }))
      : [
          {
            value: body.workspace_id || "main",
            label: body.workspace_id || "main",
          },
        ];
  }
  if (key === "chat_id") {
    const workspaceId =
      body.workspace_id || $("workspaceSelect")?.value || "main";
    return state.chats
      .filter((chat) => chat.workspace_id === workspaceId)
      .map((chat) => ({
        value: chat.id,
        label: chat.name || chat.id,
      }));
  }
  if (key === "model") return modelOptions();
  return FIELD_META[key]?.options || [];
}

function valueForDisplay(key, value) {
  const spec = FIELD_META[key] || {};
  if (spec.type === "list")
    return Array.isArray(value) ? value.join("; ") : value || "";
  if (spec.type === "shell")
    return Array.isArray(value) ? value.join(" ") : value || "";
  if (spec.type === "json") return JSON.stringify(value || {}, null, 2);
  return value ?? "";
}

function valueFromControl(control, key) {
  const spec = FIELD_META[key] || {};
  if (spec.type === "flag") return Boolean(control.checked);
  if (spec.type === "number") {
    return control.value === "" ? null : Number(control.value);
  }
  if (spec.type === "list") return listFromText(control.value);
  if (spec.type === "shell") return parseCommandLine(control.value);
  if (spec.type === "json") {
    const text = control.value.trim();
    return text ? JSON.parse(text) : {};
  }
  return control.value;
}

function bindCommandControl(control) {
  if (control.type === "checkbox" || control.tagName === "SELECT") {
    control.addEventListener("change", () =>
      updateCommandBodyFromControl(control),
    );
    return;
  }
  control.addEventListener("input", () =>
    updateCommandBodyFromControl(control, { rerender: false }),
  );
  control.addEventListener("change", () =>
    updateCommandBodyFromControl(control),
  );
}

function commandValueType(key, value) {
  const spec = FIELD_META[key] || {};
  if (spec.type === "workspace") return "workspace";
  if (spec.type === "chat") return "chat";
  if (spec.type === "model") return "model";
  if (spec.type === "select") return "select";
  if (spec.type === "flag") return "boolean";
  if (spec.type === "list" || spec.type === "shell") return "array";
  if (spec.type === "json") return "object";
  if (spec.type === "number") return "number|null";
  if (value === null) return "null";
  if (Array.isArray(value)) return "array";
  return typeof value;
}

function bindCommandControlId(control, key, prefix) {
  const id = `${prefix}-${key}`;
  if (control.matches?.("input, select, textarea")) {
    control.id = id;
    control.setAttribute("aria-label", FIELD_META[key]?.label || key);
    return id;
  }
  const input = control.querySelector("input, select, textarea");
  if (input) {
    input.id = id;
    input.setAttribute("aria-label", FIELD_META[key]?.label || key);
  }
  return id;
}

function createJsonNode(key, body, isLast) {
  const spec = FIELD_META[key] || { label: key, tooltip: key };
  const value = Object.hasOwn(body, key) ? body[key] : defaultFieldValue(key);
  const row = document.createElement("div");
  row.className = `json-node json-node-${String(spec.type || commandValueType(key, value)).replace(/[^a-z0-9-]/gi, "-")}`;
  row.title = spec.tooltip || key;

  const keyName = document.createElement("code");
  keyName.className = "json-key";
  keyName.textContent = `"${key}"`;
  keyName.title = spec.tooltip || key;

  const colon = document.createElement("span");
  colon.className = "json-colon";
  colon.textContent = ":";

  const valueWrap = document.createElement("div");
  valueWrap.className = "json-value";
  const control = createFieldControl(key, body);
  control.classList?.add("json-inline-control");
  bindCommandControlId(control, key, "json-cmd");
  valueWrap.appendChild(control);

  const type = document.createElement("span");
  type.className = "json-type";
  type.textContent = commandValueType(key, value);

  const help = document.createElement("b");
  help.className = "param-help json-help";
  help.title = spec.tooltip || key;
  help.textContent = "?";

  const comma = document.createElement("span");
  comma.className = "json-comma";
  comma.textContent = isLast ? "" : ",";

  row.append(keyName, colon, valueWrap, type, help, comma);
  return row;
}

function createFieldControl(key, body) {
  const spec = FIELD_META[key] || {};
  const value = Object.hasOwn(body, key) ? body[key] : defaultFieldValue(key);
  if (
    spec.type === "select" ||
    spec.type === "workspace" ||
    spec.type === "model"
  ) {
    const select = document.createElement("select");
    const options = fieldOptions(key, body);
    if (
      value &&
      !options.some(
        (optionValue) =>
          (typeof optionValue === "object"
            ? optionValue.value
            : optionValue) === value,
      )
    ) {
      options.push(value);
    }
    options.forEach((optionValue) => {
      const option = document.createElement("option");
      if (typeof optionValue === "object") {
        option.value = optionValue.value;
        option.textContent = optionValue.label;
      } else {
        option.value = optionValue;
        option.textContent = optionValue || "по умолчанию";
      }
      select.appendChild(option);
    });
    select.value = value || "";
    select.dataset.commandKey = key;
    return select;
  }
  if (spec.type === "chat") {
    const input = document.createElement("input");
    input.type = "text";
    input.setAttribute("list", "chatOptions");
    input.placeholder = "новый или существующий чат";
    input.value = valueForDisplay(key, value);
    input.dataset.commandKey = key;
    return input;
  }
  if (spec.type === "textarea" || spec.type === "json") {
    const textarea = document.createElement("textarea");
    textarea.value = valueForDisplay(key, value);
    textarea.spellcheck = false;
    textarea.dataset.commandKey = key;
    return textarea;
  }
  if (spec.type === "flag") {
    const label = document.createElement("label");
    label.className = "flag-row";
    const input = document.createElement("input");
    input.type = "checkbox";
    input.checked = Boolean(value);
    input.dataset.commandKey = key;
    const text = document.createElement("span");
    text.textContent = "включено";
    label.append(input, text);
    return label;
  }
  const input = document.createElement("input");
  input.type =
    spec.type === "secret"
      ? "password"
      : spec.type === "number"
        ? "number"
        : "text";
  input.value = valueForDisplay(key, value);
  input.dataset.commandKey = key;
  if (spec.type === "number") input.min = "0";
  return input;
}

function renderCommandParameterEditor(body = null) {
  const grid = $("commandJsonViewer") || $("commandParameterGrid");
  if (!grid) return;
  const current = normalizeCommandBody(
    body || readCommandBody({ silent: true }),
  );
  const keys = activeCommandKeys(current.mode);
  grid.innerHTML = "";
  const tree = document.createElement("div");
  tree.className = "json-tree";
  const openBrace = document.createElement("div");
  openBrace.className = "json-brace";
  openBrace.textContent = "{";
  tree.appendChild(openBrace);
  const hints = document.querySelector(".json-hints");
  if (hints) {
    hints.innerHTML = keys
      .map((key) => {
        const spec = FIELD_META[key] || {};
        return `<span title="${escapeHtml(spec.tooltip || key)}">${escapeHtml(key)}</span>`;
      })
      .join("");
  }
  keys.forEach((key, index) => {
    tree.appendChild(createJsonNode(key, current, index === keys.length - 1));
  });
  const closeBrace = document.createElement("div");
  closeBrace.className = "json-brace";
  closeBrace.textContent = "}";
  tree.appendChild(closeBrace);
  grid.appendChild(tree);
  grid.querySelectorAll("[data-command-key]").forEach((control) => {
    bindCommandControl(control);
  });
}

function updateCommandBodyFromControl(control, { rerender = true } = {}) {
  const key = control.dataset.commandKey;
  if (!key) return;
  let body = readCommandBody({ silent: true });
  let value;
  try {
    value = valueFromControl(control, key);
  } catch (error) {
    setCommandJsonStatus(`${key}: ${error.message}`, "error");
    return;
  }
  if (key === "mode") {
    body = defaultCommandBody(String(value || "exec"), body);
    if ($("modeSelect")) $("modeSelect").value = body.mode;
    writeCommandJson(body);
    renderModeHelp();
    renderCommandParameterEditor(body);
    return;
  }
  if (key === "workspace_id" && $("workspaceSelect")) {
    $("workspaceSelect").value = value;
    body.chat_id = firstChatForWorkspace(value)?.id || "";
    refreshChats(value).catch((error) => showToast(error.message));
  }
  body[key] = value;
  body = normalizeCommandBody(body);
  writeCommandJson(body);
  if (rerender) renderCommandParameterEditor(body);
}

async function runJob() {
  const body = readCommandBody();
  const data = await api("/api/jobs", { method: "POST", body });
  state.activeJobId = data.job.id;
  state.eventCursor = 0;
  $("activeJobTitle").textContent = `${data.job.mode} / ${data.job.id}`;
  $("logOutput").textContent = "";
  $("cancelButton").disabled = false;
  await refreshJobs();
  startPolling();
}

function parseCommandLine(value) {
  const args = [];
  let current = "";
  let quote = "";
  let escaping = false;
  for (const char of value.trim()) {
    if (escaping) {
      current += char;
      escaping = false;
      continue;
    }
    if (char === "\\") {
      escaping = true;
      continue;
    }
    if (quote) {
      if (char === quote) quote = "";
      else current += char;
      continue;
    }
    if (char === '"' || char === "'") {
      quote = char;
      continue;
    }
    if (/\s/.test(char)) {
      if (current) {
        args.push(current);
        current = "";
      }
      continue;
    }
    current += char;
  }
  if (escaping) current += "\\";
  if (current) args.push(current);
  return args;
}

function applyModeSpecificFields(body) {
  const aux = $("sessionInput").value.trim();
  if (body.mode === "doctor") {
    body.prompt = "";
  }
  if (body.mode === "exec-resume") {
    body.session_id = aux && aux !== "--last" ? aux : undefined;
    body.last = $("lastToggle").checked || aux === "--last";
  }
  if (["resume", "fork"].includes(body.mode)) {
    body.session_id = aux && aux !== "--last" ? aux : undefined;
    body.last = $("lastToggle").checked || aux === "--last";
  }
  if (body.mode === "apply") {
    body.task_id = aux;
    body.prompt = "";
  }
  if (body.mode === "completion") {
    body.shell = aux || "powershell";
    body.prompt = "";
  }
  if (body.mode === "debug-models") {
    body.bundled = true;
    body.prompt = "";
  }
  if (body.mode === "debug-app-server-send-message-v2") {
    body.message = body.prompt || aux;
    body.prompt = "";
  }
  if (body.mode === "debug-prompt-input") {
    body.prompt = body.prompt || aux;
  }
  if (body.mode === "login-api-key" || body.mode === "login-access-token") {
    body.secret = $("secretInput").value;
    body.prompt = "";
  }
  if (body.mode === "cloud-list") {
    body.env_id = aux || undefined;
    body.prompt = "";
  }
  if (["cloud-status", "cloud-diff", "cloud-apply"].includes(body.mode)) {
    body.task_id = aux;
    body.prompt = "";
  }
  if (body.mode === "cloud-exec") {
    body.env_id = aux;
    body.branch = $("marketplaceInput").value.trim() || undefined;
  }
  if (
    ["sandbox-linux", "sandbox-macos", "sandbox-windows"].includes(body.mode)
  ) {
    body.command = body.prompt.split(/\s+/).filter(Boolean);
    body.prompt = "";
  }
  if (body.mode === "exec-server-start") {
    body.listen = aux || "ws://127.0.0.1:0";
    body.name = $("marketplaceInput").value.trim() || undefined;
    body.prompt = "";
  }
  if (body.mode === "mcp-server") {
    body.prompt = "";
  }
  if (body.mode === "app-open") {
    body.path = aux || undefined;
    body.prompt = "";
  }
  if (body.mode === "app-server-start") {
    body.listen = aux || "ws://127.0.0.1:0";
    body.ws_auth = $("marketplaceInput").value.trim() || undefined;
    body.prompt = "";
  }
  if (body.mode === "app-server-proxy") {
    body.sock = aux || undefined;
    body.prompt = "";
  }
  if (
    ["app-server-generate-ts", "app-server-generate-json-schema"].includes(
      body.mode,
    )
  ) {
    body.out_dir = aux;
    body.experimental = $("lastToggle").checked;
    body.prompt = "";
  }
  if (body.mode === "app-daemon-bootstrap") {
    body.remote_control = $("lastToggle").checked;
    body.prompt = "";
  }
  if (body.mode === "mcp-get") {
    body.name = aux;
    body.prompt = "";
  }
  if (["mcp-remove", "mcp-login", "mcp-logout"].includes(body.mode)) {
    body.name = aux;
    body.prompt = "";
  }
  if (body.mode === "mcp-add") {
    body.name = aux;
    body.url = $("marketplaceInput").value.trim() || undefined;
    body.prompt = "";
  }
  if (body.mode === "plugin-list") {
    body.marketplace = $("marketplaceInput").value.trim() || undefined;
    body.prompt = "";
  }
  if (["plugin-add", "plugin-remove"].includes(body.mode)) {
    body.plugin = aux;
    body.marketplace = $("marketplaceInput").value.trim() || undefined;
    body.prompt = "";
  }
  if (body.mode === "plugin-marketplace-add") {
    body.source = aux;
    body.ref = $("marketplaceInput").value.trim() || undefined;
    body.prompt = "";
  }
  if (
    ["plugin-marketplace-remove", "plugin-marketplace-upgrade"].includes(
      body.mode,
    )
  ) {
    body.marketplace = aux || $("marketplaceInput").value.trim() || undefined;
    body.prompt = "";
  }
  if (["features-enable", "features-disable"].includes(body.mode)) {
    body.feature = aux;
    body.prompt = "";
  }
  if (body.mode === "help") {
    body.topic = aux || "codex";
    body.prompt = "";
  }
  if (body.mode === "raw") {
    body.args = parseCommandLine(aux);
    body.stdin = body.prompt;
    body.prompt = "";
  }
  if (
    [
      "login-status",
      "login-device-auth",
      "logout",
      "update",
      "mcp-list",
      "features-list",
      "plugin-marketplace-list",
      "app-daemon-version",
      "app-daemon-bootstrap",
      "app-daemon-start",
      "app-daemon-restart",
      "app-daemon-stop",
      "app-daemon-enable-remote",
      "app-daemon-disable-remote",
      "remote-start",
      "remote-stop",
    ].includes(body.mode)
  ) {
    body.prompt = "";
  }
}

async function selectJob(jobId) {
  state.activeJobId = jobId;
  state.eventCursor = 0;
  $("logOutput").textContent = "";
  $("activeJobTitle").textContent = jobId;
  await pollEvents();
  activateTab("run");
}

function startPolling() {
  window.clearInterval(state.pollTimer);
  state.pollTimer = window.setInterval(pollEvents, 1500);
  pollEvents();
}

async function pollEvents() {
  if (!state.activeJobId) return;
  try {
    const data = await api(
      `/api/jobs/${state.activeJobId}/events?since=${state.eventCursor}`,
    );
    const output = $("logOutput");
    (data.events || []).forEach((event) => {
      output.textContent += `${event.text}\n`;
      state.eventCursor = event.index + 1;
    });
    setText("streamCounter", `Строк: ${state.eventCursor}`);
    output.scrollTop = output.scrollHeight;
    const job = await api(`/api/jobs/${state.activeJobId}`);
    const status = job.job.status;
    $("activeJobTitle").textContent =
      `${job.job.mode} / ${job.job.id} / ${statusLabel(status)}`;
    if (["completed", "failed", "cancelled"].includes(status)) {
      $("cancelButton").disabled = true;
      window.clearInterval(state.pollTimer);
      await refreshJobs();
    }
  } catch (error) {
    showToast(error.message);
  }
}

async function cancelActiveJob() {
  if (!state.activeJobId) return;
  await api(`/api/jobs/${state.activeJobId}/cancel`, {
    method: "POST",
    body: {},
  });
  $("cancelButton").disabled = true;
  await refreshJobs();
}

async function runDoctor() {
  await runQuickAction("doctor");
}

async function runQuickAction(mode, extra = {}) {
  const body = {
    mode,
    workspace_id: $("workspaceSelect").value,
    ...extra,
  };
  const data = await api("/api/jobs", { method: "POST", body });
  if ($("doctorResult"))
    $("doctorResult").textContent = `задача=${data.job.id}`;
  state.activeJobId = data.job.id;
  state.eventCursor = 0;
  $("logOutput").textContent = "";
  $("activeJobTitle").textContent = `${data.job.mode} / ${data.job.id}`;
  activateTab("run");
  startPolling();
}

function renderModeHelp() {
  const details = state.capabilities.mode_details || {};
  const select = $("modeSelect");
  if (!select) return;
  const mode = select.value;
  select.title = details[mode]?.title || mode;
}

function filterModes() {
  const input = $("modeFilterInput");
  const select = $("modeSelect");
  if (!input || !select) return;
  const query = input.value.trim().toLowerCase();
  let firstVisible = "";
  [...select.options].forEach((option) => {
    const visible = !query || option.value.toLowerCase().includes(query);
    option.hidden = !visible;
    if (visible && !firstVisible) firstVisible = option.value;
  });
  if (select.selectedOptions[0]?.hidden && firstVisible) {
    select.value = firstVisible;
    renderModeHelp();
  }
}

function resetMainScroll() {
  const main = document.querySelector(".main");
  if (main) {
    main.scrollTop = 0;
    window.requestAnimationFrame(() => {
      main.scrollTop = 0;
    });
  } else window.scrollTo(0, 0);
}

function canScrollElementInDirection(element, deltaY) {
  if (
    !element ||
    element === document.body ||
    element === document.documentElement
  ) {
    return false;
  }
  const style = window.getComputedStyle(element);
  if (!/(auto|scroll)/.test(style.overflowY)) return false;
  if (element.scrollHeight <= element.clientHeight + 1) return false;
  if (deltaY > 0) {
    return element.scrollTop + element.clientHeight < element.scrollHeight - 1;
  }
  if (deltaY < 0) return element.scrollTop > 1;
  return false;
}

function scrollableAncestor(target, deltaY) {
  let element = target instanceof Element ? target : target?.parentElement;
  while (
    element &&
    element !== document.body &&
    element !== document.documentElement
  ) {
    if (canScrollElementInDirection(element, deltaY)) return element;
    element = element.parentElement;
  }
  return null;
}

function wireMainWheelScroll() {
  const main = document.querySelector(".main");
  if (!main) return;
  document.addEventListener(
    "wheel",
    (event) => {
      if (!event.deltaY || event.defaultPrevented) return;
      if (event.target instanceof Element && event.target.closest("select")) {
        return;
      }
      const scrollTarget = scrollableAncestor(event.target, event.deltaY);
      if (scrollTarget && scrollTarget !== main) return;
      if (main.scrollHeight <= main.clientHeight + 1) return;
      const before = main.scrollTop;
      main.scrollTop += event.deltaY;
      if (main.scrollTop !== before) event.preventDefault();
    },
    { passive: false },
  );
}

function activateTab(name) {
  document
    .querySelectorAll(".tab")
    .forEach((tab) =>
      tab.classList.toggle("is-active", tab.dataset.tab === name),
    );
  document
    .querySelectorAll(".view")
    .forEach((view) => view.classList.remove("is-active"));
  $(`view-${name}`).classList.add("is-active");
  resetMainScroll();
  if (name === "jobs") refreshJobs().catch((error) => showToast(error.message));
  if (name === "workspaces")
    refreshWorkspaces().catch((error) => showToast(error.message));
  if (name === "tokens")
    refreshTokens().catch((error) => showToast(error.message));
  if (name === "audit")
    refreshAudit().catch((error) => showToast(error.message));
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

async function toggleServerPower() {
  if (!state.serverOnline) {
    showToast(
      "Запустите codex-bridge.exe на этой машине и нажмите Подключить.",
    );
    return;
  }
  await api("/api/server/stop", { method: "POST", body: {} });
  state.connected = false;
  setStatus(false, "останавливается");
  window.setTimeout(checkBridgeHealth, 900);
}

function wire() {
  $("bridgeUrl").value = state.bridgeUrl;
  $("bridgeToken").value = state.token;
  $("userNameInput").value = state.userName;
  wireMainWheelScroll();
  setBridgeTokenVisible(false);
  updateConnectionControls();
  $("connectButton").addEventListener("click", connect);
  $("toggleBridgeTokenVisibility").addEventListener("click", () =>
    setBridgeTokenVisible($("bridgeToken").type === "password"),
  );
  $("bridgeUrl").addEventListener("change", () =>
    loadCurrentMachineToken().catch(() => {}),
  );
  $("userNameInput").addEventListener("change", () => {
    state.userName = $("userNameInput").value.trim() || "Локальный админ";
    localStorage.setItem("codexBridge.userName", state.userName);
    if (!$("workspaceOwnerInput").value.trim())
      $("workspaceOwnerInput").value = state.userName;
    connect();
  });
  $("topRefreshButton").addEventListener("click", connect);
  $("serverPowerButton").addEventListener("click", () =>
    toggleServerPower().catch((error) => showToast(error.message)),
  );
  $("runButton").addEventListener("click", () =>
    runJob().catch((error) => showToast(error.message)),
  );
  $("cancelButton").addEventListener("click", () =>
    cancelActiveJob().catch((error) => showToast(error.message)),
  );
  $("refreshJobsButton").addEventListener("click", () =>
    refreshJobs().catch((error) => showToast(error.message)),
  );
  $("refreshWorkspacesButton").addEventListener("click", () =>
    refreshWorkspaces().catch((error) => showToast(error.message)),
  );
  $("refreshTokensButton").addEventListener("click", () =>
    refreshTokens().catch((error) => showToast(error.message)),
  );
  $("refreshAuditButton").addEventListener("click", () =>
    refreshAudit().catch((error) => showToast(error.message)),
  );
  $("tokenSortSelect").addEventListener("change", () => {
    state.tokenSort = $("tokenSortSelect").value;
    renderTokensList();
  });
  $("auditSortSelect").addEventListener("change", () => {
    state.auditSort = $("auditSortSelect").value;
    renderAuditTable();
  });
  $("addJobUserTabButton").addEventListener("click", () => {
    const picker = $("jobUserSelect");
    picker.hidden = !picker.hidden;
    if (!picker.hidden) picker.focus();
  });
  $("jobUserSelect").addEventListener("change", () => {
    addJobUserTab($("jobUserSelect").value);
    $("jobUserSelect").hidden = true;
    $("jobUserSelect").value = "";
  });
  $("createTokenButton").addEventListener("click", () =>
    createToken().catch((error) => showToast(error.message)),
  );
  $("saveWorkspaceButton").addEventListener("click", () =>
    saveWorkspace().catch((error) => showToast(error.message)),
  );
  $("workspaceIdInput").addEventListener("input", () =>
    syncWorkspaceConfigFromAdminSelection(),
  );
  $("workspaceConfigInput").addEventListener("input", () =>
    scheduleWorkspaceConfigSave(),
  );
  $("modeSelect").addEventListener("change", () => {
    renderModeHelp();
    syncCommandJsonFromControls();
  });
  $("commandJsonInput").addEventListener("input", () => {
    try {
      const body = readCommandBody();
      if ($("modeSelect")) $("modeSelect").value = body.mode;
      if ($("workspaceSelect") && body.workspace_id) {
        $("workspaceSelect").value = body.workspace_id;
      }
      renderCommandParameterEditor(body);
    } catch {
      // readCommandBody already updates the inline status.
    }
  });
  document.querySelectorAll("[data-action]").forEach((button) =>
    button.addEventListener("click", () =>
      runQuickAction(button.dataset.action, {
        topic: button.dataset.topic,
      }).catch((error) => showToast(error.message)),
    ),
  );
  document
    .querySelectorAll(".tab")
    .forEach((tab) =>
      tab.addEventListener("click", () => activateTab(tab.dataset.tab)),
    );
  loadCurrentMachineToken()
    .catch(() => {})
    .finally(() => connect());
  startHealthPolling();
}

wire();
