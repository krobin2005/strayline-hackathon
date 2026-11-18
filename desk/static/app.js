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
  const what = {
    image: "Looking at the image",
    document: "Reading the document",
    audio: "Listening",
    video: "Watching the video",
    code: "Writing and testing code",
  }[kind] || "Thinking";
  const start = performance.now();
  el.textContent = `${what}…`;
  const timer = setInterval(() => {
    el.textContent = `${what}… ${Math.round((performance.now() - start) / 1000)} s`;
  }, 1000);
  log.appendChild(el);
  scrollDown();
  return { el, stop: () => clearInterval(timer) };
}

// Render model text safely: ``` fences become code blocks, **x** becomes bold. No innerHTML.
function renderText(el, text) {
  const parts = text.split(/```[a-zA-Z]*\n?/);
  parts.forEach((part, i) => {
    if (i % 2 === 1) {
      const pre = document.createElement("pre");
      pre.textContent = part.replace(/\n$/, "");
      el.appendChild(pre);
      return;
    }
    part.split(/(\*\*[^*]+\*\*)/).forEach((bit) => {
      if (/^\*\*[^*]+\*\*$/.test(bit)) {
        const b = document.createElement("strong");
        b.textContent = bit.slice(2, -2);
        el.appendChild(b);
      } else if (bit) {
        el.appendChild(document.createTextNode(bit));
      }
    });
  });
}

function fillAnswer(el, result) {
  el.className = "msg bot";
  el.textContent = "";
  renderText(el, result.text);
  const meta = document.createElement("div");
  meta.className = "meta";
  meta.textContent = `${result.model} · ${result.seconds.toFixed(1)} s · on this laptop`;
  el.appendChild(meta);
  if (result.evidence && result.evidence.length) {
    const d = document.createElement("details");
    d.className = "evidence";
    const s = document.createElement("summary");
    s.textContent = result.kind === "document"
      ? `Based on ${result.evidence.length} passage${result.evidence.length > 1 ? "s" : ""}`
      : "How I got this";
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

// Convert any audio the browser can decode (mic recordings, MP3, M4A...) to 16 kHz mono WAV,
// which the local audio model reads directly. If decoding fails, the original file is sent and
// the server converts it.
async function toWav(blob, name) {
  const AudioCtx = window.AudioContext || window.webkitAudioContext;
  const decoded = await new AudioCtx().decodeAudioData(await blob.arrayBuffer());
  const rate = 16000;
  const offline = new OfflineAudioContext(1, Math.ceil(decoded.duration * rate), rate);
  const src = offline.createBufferSource();
  src.buffer = decoded;
  src.connect(offline.destination);
  src.start();
  const samples = (await offline.startRendering()).getChannelData(0);
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const v = new DataView(buffer);
  const str = (o, s) => [...s].forEach((c, i) => v.setUint8(o + i, c.charCodeAt(0)));
  str(0, "RIFF"); v.setUint32(4, 36 + samples.length * 2, true); str(8, "WAVE");
  str(12, "fmt "); v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
  v.setUint32(24, rate, true); v.setUint32(28, rate * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true);
  str(36, "data"); v.setUint32(40, samples.length * 2, true);
  samples.forEach((s, i) => v.setInt16(44 + i * 2, Math.max(-1, Math.min(1, s)) * 0x7fff, true));
  return new File([buffer], name.replace(/\.[^.]+$/, "") + ".wav", { type: "audio/wav" });
}

async function uploadFile(file) {
  chip.hidden = false;
  document.getElementById("chip-kind").textContent = "Uploading";
  document.getElementById("chip-name").textContent = file.name;
  if (file.type.startsWith("audio/") && file.type !== "audio/wav") {
    try { file = await toWav(file, file.name); } catch { /* server converts instead */ }
  }
  const body = new FormData();
  body.append("file", file);
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
}

fileInput.addEventListener("change", () => {
  const file = fileInput.files[0];
  fileInput.value = "";
  if (file) uploadFile(file);
});

// Mic recording. Browsers only allow the mic on secure pages (localhost counts), so on a phone
// using the laptop's network address the button stays hidden; upload a voice memo instead.
const micButton = document.getElementById("mic");
let recorder = null;
if (navigator.mediaDevices && window.MediaRecorder && window.isSecureContext) {
  micButton.hidden = false;
  micButton.addEventListener("click", async () => {
    if (recorder && recorder.state === "recording") { recorder.stop(); return; }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const chunks = [];
      recorder = new MediaRecorder(stream);
      recorder.ondataavailable = (e) => chunks.push(e.data);
      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        micButton.classList.remove("recording");
        micButton.title = "Record audio";
        const blob = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
        const stamp = new Date().toTimeString().slice(0, 8).replace(/:/g, "");
        uploadFile(new File([blob], `recording-${stamp}.webm`, { type: blob.type }));
      };
      recorder.start();
      micButton.classList.add("recording");
      micButton.title = "Stop recording";
    } catch {
      micButton.hidden = true;
    }
  });
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = input.value.trim();
  if (!question && !attachment) { input.focus(); return; }
  addUserMessage(question, attachment);
  input.value = "";
  autosize();
  sendButton.disabled = true;
  const looksLikeCode = /\b(write|create|generate|implement|build|make)\b.{0,60}\b(function|script|program|code|class|regex|parser|query|snippet|method)\b|\bin python\b|^\s*(def |from \w+ import |import \w+)/im;
  const pendingKind = attachment ? attachment.kind : (looksLikeCode.test(question) ? "code" : null);
  const pending = addPending(pendingKind);
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
