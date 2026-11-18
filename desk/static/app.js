// Strayline Desk chat page. No frameworks or CDNs, so it works with no internet.

const log = document.getElementById("log");
const form = document.getElementById("composer");
const input = document.getElementById("question");
const fileInput = document.getElementById("file");
const sendButton = document.getElementById("send");
const chip = document.getElementById("chip");
const statusEl = document.getElementById("status");

// The file currently attached. It stays attached for follow-up questions until removed.
let attachment = null; // {id, kind, name, previewUrl}

const KIND_LABEL = { image: "Image", document: "Document", audio: "Audio", video: "Video", logs: "Logs" };

async function checkHealth() {
  try {
    const r = await fetch("/api/health");
    const h = await r.json();
    statusEl.textContent = h.ollama ? "Local models ready" : "Ollama not running";
    statusEl.className = "status " + (h.ollama ? "ok" : "bad");
  } catch {
    statusEl.textContent = "Server offline";
    statusEl.className = "status bad";
  }
}

function scrollDown() { log.scrollTop = log.scrollHeight; }

function hideWelcome() {
  const w = document.getElementById("welcome");
  if (w) w.remove();
}

function addUserMessage(question, att) {
  hideWelcome();
  const el = document.createElement("div");
  el.className = "msg user";
  if (att) {
    if (att.kind === "image" && att.previewUrl) {
      const img = document.createElement("img");
      img.className = "thumb";
      img.src = att.previewUrl;
      img.alt = att.name;
      el.appendChild(img);
    } else {
      const f = document.createElement("div");
      f.className = "file";
      f.textContent = `📎 ${att.name}`;
      el.appendChild(f);
    }
  }
  el.appendChild(document.createTextNode(question || "(no question: describe it)"));
  log.appendChild(el);
  scrollDown();
}

function addPending(kind) {
  const el = document.createElement("div");
  el.className = "msg bot typing";
  const what = { image: "Looking at the image", document: "Reading the document" }[kind] || "Thinking";
  const start = performance.now();
  el.textContent = `${what}…`;
  const timer = setInterval(() => {
    el.textContent = `${what}… ${Math.round((performance.now() - start) / 1000)} s`;
  }, 1000);
  log.appendChild(el);
  scrollDown();
  return { el, stop: () => clearInterval(timer) };
}

function fillAnswer(el, result) {
  el.className = "msg bot";
  el.textContent = result.text;
  const meta = document.createElement("div");
  meta.className = "meta";
  meta.textContent = `${result.model} · ${result.seconds.toFixed(1)} s · on this laptop`;
  el.appendChild(meta);
  if (result.evidence && result.evidence.length) {
    const d = document.createElement("details");
    d.className = "evidence";
    const s = document.createElement("summary");
    s.textContent = `Based on ${result.evidence.length} passage${result.evidence.length > 1 ? "s" : ""}`;
    d.appendChild(s);
    for (const e of result.evidence) {
      const p = document.createElement("p");
      p.textContent = e;
      d.appendChild(p);
    }
    el.appendChild(d);
  }
}

function fillError(el, message) {
  el.className = "msg bot error";
  el.textContent = message;
}

function showChip() {
  if (!attachment) { chip.hidden = true; return; }
  document.getElementById("chip-kind").textContent = KIND_LABEL[attachment.kind] || attachment.kind;
  document.getElementById("chip-name").textContent = attachment.name;
  chip.hidden = false;
}

document.getElementById("chip-clear").addEventListener("click", () => {
  attachment = null;
  showChip();
  input.focus();
});

fileInput.addEventListener("change", async () => {
  const file = fileInput.files[0];
  fileInput.value = "";
  if (!file) return;
  const body = new FormData();
  body.append("file", file);
  chip.hidden = false;
  document.getElementById("chip-kind").textContent = "Uploading";
  document.getElementById("chip-name").textContent = file.name;
  try {
    const r = await fetch("/api/upload", { method: "POST", body });
    const data = await r.json();
    if (!r.ok) throw new Error(data.detail || "Upload failed");
    attachment = { ...data, previewUrl: data.kind === "image" ? URL.createObjectURL(file) : null };
    showChip();
    input.focus();
  } catch (err) {
    attachment = null;
    chip.hidden = true;
    hideWelcome();
    const el = document.createElement("div");
    log.appendChild(el);
    fillError(el, err.message);
  }
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = input.value.trim();
  if (!question && !attachment) { input.focus(); return; }
  addUserMessage(question, attachment);
  input.value = "";
  autosize();
  sendButton.disabled = true;
  const pending = addPending(attachment && attachment.kind);
  try {
    const r = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, attachment_id: attachment ? attachment.id : null }),
    });
    const data = await r.json();
    pending.stop();
    if (!r.ok) fillError(pending.el, data.detail || "Something went wrong.");
    else fillAnswer(pending.el, data);
  } catch {
    pending.stop();
    fillError(pending.el, "Lost contact with the Strayline Desk server.");
  } finally {
    sendButton.disabled = false;
    scrollDown();
    input.focus();
  }
});

// Enter sends; Shift+Enter makes a new line.
input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); }
});

function autosize() {
  input.style.height = "auto";
  input.style.height = Math.min(input.scrollHeight, 160) + "px";
}
input.addEventListener("input", autosize);

checkHealth();
setInterval(checkHealth, 15000);
