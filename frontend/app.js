const STORAGE_KEYS = {
  apiBase: "cloudpilot.apiBase",
  apiKey: "cloudpilot.apiKey",
  userId: "cloudpilot.userId",
};

const elements = {
  apiNotice: document.getElementById("apiNotice"),
  apiBaseInput: document.getElementById("apiBaseInput"),
  apiKeyInput: document.getElementById("apiKeyInput"),
  cancelSettingsButton: document.getElementById("cancelSettingsButton"),
  chatForm: document.getElementById("chatForm"),
  chatScroll: document.getElementById("chatScroll"),
  closeSettingsButton: document.getElementById("closeSettingsButton"),
  connectionLabel: document.getElementById("connectionLabel"),
  conversationUser: document.getElementById("conversationUser"),
  inlineSettingsButton: document.getElementById("inlineSettingsButton"),
  messageInput: document.getElementById("messageInput"),
  messages: document.getElementById("messages"),
  miniStatusDot: document.getElementById("miniStatusDot"),
  miniStatusText: document.getElementById("miniStatusText"),
  mobileMenuButton: document.getElementById("mobileMenuButton"),
  newChatButton: document.getElementById("newChatButton"),
  settingsButton: document.getElementById("settingsButton"),
  settingsForm: document.getElementById("settingsForm"),
  settingsModal: document.getElementById("settingsModal"),
  sidebar: document.getElementById("sidebar"),
  sendButton: document.getElementById("sendButton"),
  statusDot: document.getElementById("statusDot"),
  statusPill: document.getElementById("statusPill"),
  statusText: document.getElementById("statusText"),
  userIdInput: document.getElementById("userIdInput"),
  welcomeState: document.getElementById("welcomeState"),
};

const state = {
  apiBase: sessionStorage.getItem(STORAGE_KEYS.apiBase) || window.location.origin,
  apiKey: sessionStorage.getItem(STORAGE_KEYS.apiKey) || "",
  userId: sessionStorage.getItem(STORAGE_KEYS.userId) || createUserId(),
  busy: false,
};

function createUserId() {
  const suffix = Math.random().toString(36).slice(2, 8);
  return `visitor-${suffix}`;
}

function normalizeBase(value) {
  return (value || window.location.origin).trim().replace(/\/+$/, "") || window.location.origin;
}

function saveSession() {
  sessionStorage.setItem(STORAGE_KEYS.apiBase, state.apiBase);
  sessionStorage.setItem(STORAGE_KEYS.apiKey, state.apiKey);
  sessionStorage.setItem(STORAGE_KEYS.userId, state.userId);
}

function setStatus(kind, text) {
  elements.statusDot.className = `status-dot ${kind}`;
  elements.miniStatusDot.className = `mini-status-dot ${kind}`;
  elements.statusText.textContent = text;
  elements.miniStatusText.textContent = kind === "online" ? "Service online" : kind === "offline" ? "Service unavailable" : "Checking service";
}

async function checkStatus() {
  setStatus("", "Checking status");
  try {
    const [healthResponse, readyResponse] = await Promise.all([
      fetch(`${state.apiBase}/health`, { cache: "no-store" }),
      fetch(`${state.apiBase}/ready`, { cache: "no-store" }),
    ]);
    if (healthResponse.ok && readyResponse.ok) {
      setStatus("online", "All systems operational");
    } else {
      setStatus("offline", "Service needs attention");
    }
  } catch (_error) {
    setStatus("offline", "Service unavailable");
  }
}

function updateConnectionState() {
  const connected = Boolean(state.apiKey);
  elements.apiNotice.classList.toggle("hidden", connected);
  elements.connectionLabel.textContent = connected ? `Connected · ${state.userId}` : "No API key connected";
  elements.connectionLabel.classList.toggle("connected", connected);
  elements.conversationUser.textContent = state.userId;
}

function openSettings() {
  elements.apiBaseInput.value = state.apiBase;
  elements.apiKeyInput.value = state.apiKey;
  elements.userIdInput.value = state.userId;
  elements.settingsModal.hidden = false;
  window.setTimeout(() => elements.apiKeyInput.focus(), 30);
}

function closeSettings() {
  elements.settingsModal.hidden = true;
}

function scrollToBottom() {
  elements.chatScroll.scrollTo({ top: elements.chatScroll.scrollHeight, behavior: "smooth" });
}

function escapeHtml(value) {
  return value.replace(/[&<>'"]/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "'": "&#39;",
    '"': "&quot;",
  }[character]));
}

function formatCost(value) {
  if (typeof value !== "number") return "—";
  return `$${value.toFixed(6)}`;
}

function appendMessage(role, text, metadata = []) {
  elements.welcomeState.style.display = "none";
  const row = document.createElement("article");
  row.className = `message-row ${role}`;
  const label = role === "user" ? "You" : "CloudPilot";
  const avatar = role === "user" ? "YOU" : "✦";
  row.innerHTML = `
    <div class="message-avatar" aria-hidden="true">${avatar}</div>
    <div class="message-content">
      <div class="message-label">${label}</div>
      <div class="message-bubble">${escapeHtml(text)}</div>
      ${metadata.length ? `<div class="message-meta">${metadata.map((item) => `<span class="meta-chip">${escapeHtml(item)}</span>`).join("")}</div>` : ""}
    </div>
  `;
  elements.messages.appendChild(row);
  scrollToBottom();
  return row;
}

function appendTyping() {
  const row = document.createElement("article");
  row.className = "message-row assistant";
  row.id = "typingRow";
  row.innerHTML = `
    <div class="message-avatar" aria-hidden="true">✦</div>
    <div class="message-content"><div class="message-label">CloudPilot</div><div class="message-bubble typing-bubble"><span></span><span></span><span></span></div></div>
  `;
  elements.messages.appendChild(row);
  scrollToBottom();
}

function removeTyping() {
  document.getElementById("typingRow")?.remove();
}

function friendlyError(status, detail) {
  if (status === 401) return "Your API key is missing or invalid. Open Connection settings and try again.";
  if (status === 402) return "This user has reached the monthly budget. Try a new user ID or raise the budget on the service.";
  if (status === 429) return "You are sending messages too quickly. Wait a moment and try again.";
  return detail || "The service could not complete that request. Check the service status and try again.";
}

async function sendMessage(question) {
  const trimmed = question.trim();
  if (!trimmed || state.busy) return;
  if (!state.apiKey) {
    openSettings();
    return;
  }

  state.busy = true;
  elements.sendButton.disabled = true;
  elements.messageInput.value = "";
  elements.messageInput.style.height = "auto";
  appendMessage("user", trimmed);
  appendTyping();

  try {
    const response = await fetch(`${state.apiBase}/ask`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": state.apiKey,
        "X-User-Id": state.userId,
      },
      body: JSON.stringify({ question: trimmed }),
    });
    const data = await response.json().catch(() => ({}));
    removeTyping();
    if (!response.ok) {
      appendMessage("assistant", friendlyError(response.status, data.detail));
      return;
    }
    const tokens = data.tokens || {};
    appendMessage("assistant", data.answer || "I did not receive an answer.", [
      `History ${data.history_length ?? 0}`,
      `${tokens.in ?? 0} in · ${tokens.out ?? 0} out`,
      formatCost(data.cost_usd),
    ]);
  } catch (_error) {
    removeTyping();
    appendMessage("assistant", "I could not reach the service. Check the API base URL and deployment status.");
    setStatus("offline", "Service unavailable");
  } finally {
    state.busy = false;
    elements.sendButton.disabled = false;
    elements.messageInput.focus();
  }
}

function startNewChat() {
  state.userId = createUserId();
  saveSession();
  elements.messages.replaceChildren();
  elements.welcomeState.style.display = "block";
  updateConnectionState();
  elements.messageInput.focus();
}

function autoResize() {
  elements.messageInput.style.height = "auto";
  elements.messageInput.style.height = `${Math.min(elements.messageInput.scrollHeight, 145)}px`;
}

elements.chatForm.addEventListener("submit", (event) => {
  event.preventDefault();
  sendMessage(elements.messageInput.value);
});

elements.messageInput.addEventListener("input", autoResize);
elements.messageInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    elements.chatForm.requestSubmit();
  }
});

document.querySelectorAll("[data-prompt]").forEach((button) => {
  button.addEventListener("click", () => {
    elements.messageInput.value = button.dataset.prompt || "";
    autoResize();
    elements.messageInput.focus();
  });
});

elements.settingsButton.addEventListener("click", openSettings);
elements.inlineSettingsButton.addEventListener("click", openSettings);
elements.closeSettingsButton.addEventListener("click", closeSettings);
elements.cancelSettingsButton.addEventListener("click", closeSettings);
elements.settingsModal.addEventListener("click", (event) => {
  if (event.target === elements.settingsModal) closeSettings();
});
elements.settingsForm.addEventListener("submit", (event) => {
  event.preventDefault();
  state.apiBase = normalizeBase(elements.apiBaseInput.value);
  state.apiKey = elements.apiKeyInput.value.trim();
  state.userId = elements.userIdInput.value.trim() || createUserId();
  saveSession();
  updateConnectionState();
  closeSettings();
  checkStatus();
});
elements.newChatButton.addEventListener("click", () => {
  startNewChat();
  elements.sidebar.classList.remove("open");
});
elements.conversationItem.addEventListener("click", startNewChat);
elements.statusPill.addEventListener("click", checkStatus);
elements.mobileMenuButton.addEventListener("click", () => elements.sidebar.classList.toggle("open"));

updateConnectionState();
checkStatus();
