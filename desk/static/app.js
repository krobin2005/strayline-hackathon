// Strayline Desk chat page. No frameworks or CDNs, so it works with no internet.

const log = document.getElementById("log");
const form = document.getElementById("composer");
const input = document.getElementById("question");
const fileInput = document.getElementById("file");
const sendButton = document.getElementById("send");
const chip = document.getElementById("chip");
const statusEl = document.getElementById("status");

// The file currently attached. It stays attached for follow-up questions until removed.
let uploadVersion = 0;
let uploading = false;
let answering = false;
let attachment = null; // {id, kind, name, previewUrl}

const KIND_LABEL = { image: "Image", document: "Document", audio: "Audio", video: "Video", logs: "Logs" };

async function checkHealth() {
  try {
    const r = await fetch("/api/health");
    const h = await r.json();
    statusEl.textContent = h.ollama ? "Ollama connected" : "Ollama not running";
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
  if (att && att.id) {
    const again = document.createElement("button");
    again.type = "button";
    again.className = "reuse";
    again.textContent = "Ask about this file";
    again.addEventListener("click", () => {
      if (answering) return;
      uploadVersion++;
      uploading = false;
      attachment = att;
      showChip();
      sendButton.disabled = false;
      input.focus();
    });
    el.appendChild(again);
  }
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
    logs: "Running the Strayline detector on the logs",
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
    d.open = true;
    const s = document.createElement("summary");
    s.textContent = result.kind === "document"
      ? `Based on ${result.evidence.length} passage${result.evidence.length > 1 ? "s" : ""}`
      : "How I got this";
    d.appendChild(s);
    if (result.frame_sheet_jpeg) {
      s.textContent = "View the frames used for this answer";
      const sheet = document.createElement("img");
      sheet.className = "frame-sheet";
      sheet.alt = "Video frames in chronological order, read left to right by row";
      sheet.src = "data:image/jpeg;base64," + result.frame_sheet_jpeg;
      d.appendChild(sheet);
    }
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
  uploadVersion++;
  uploading = false;
  sendButton.disabled = answering;
  attachment = null;
  showChip();
  input.focus();
});

// Convert any audio the browser can decode (mic recordings, MP3, M4A...) to 16 kHz mono WAV,
// which the local audio model reads directly. If decoding fails, the original file is sent and
// the server converts it.
async function toWav(blob, name) {
  const AudioCtx = window.AudioContext || window.webkitAudioContext;
  const ctx = new AudioCtx();
  let decoded;
  try {
    decoded = await ctx.decodeAudioData(await blob.arrayBuffer());
  } finally {
    await ctx.close();
  }
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

// Upload one file and return its attachment record; throws on failure.
async function sendFile(file) {
  if (file.type.startsWith("audio/") && file.type !== "audio/wav") {
    try { file = await toWav(file, file.name); } catch { /* server converts instead */ }
  }
  const body = new FormData();
  body.append("file", file);
  const r = await fetch("/api/upload", { method: "POST", body });
  const data = await r.json();
  if (!r.ok) throw new Error(data.detail || "Upload failed");
  return { ...data, previewUrl: data.kind === "image" ? URL.createObjectURL(file) : null };
}

async function uploadFile(file) {
  const version = ++uploadVersion;
  attachment = null;
  uploading = true;
  sendButton.disabled = true;
  chip.hidden = false;
  document.getElementById("chip-kind").textContent = "Uploading";
  document.getElementById("chip-name").textContent = file.name;
  try {
    const att = await sendFile(file);
    if (version !== uploadVersion) return;
    attachment = att;
    showChip();
    input.focus();
  } catch (err) {
    if (version !== uploadVersion) return;
    attachment = null;
    chip.hidden = true;
    hideWelcome();
    const el = document.createElement("div");
    log.appendChild(el);
    fillError(el, err.message);
  } finally {
    if (version === uploadVersion) {
      uploading = false;
      sendButton.disabled = answering;
    }
  }
}

fileInput.addEventListener("change", () => {
  const files = [...fileInput.files];
  fileInput.value = "";
  handleFiles(files);
});

function handleFiles(files) {
  if (!files.length || answering) return;
  if (files.length === 1) uploadFile(files[0]);
  else runCase(files);
}

// Drop files anywhere on the page. Without this, Safari drops the file's path into the text box.
// Safari labels files from Finder as "Files", "public.file-url" or "text/uri-list" depending on version.
const FILE_DRAG_TYPES = ["Files", "public.file-url", "text/uri-list"];
document.addEventListener("dragover", (e) => {
  if ([...e.dataTransfer.types].some((t) => FILE_DRAG_TYPES.includes(t))) {
    e.preventDefault();
    document.body.classList.add("dropping");
  }
}, true);
document.addEventListener("dragenter", (e) => {
  if ([...e.dataTransfer.types].some((t) => FILE_DRAG_TYPES.includes(t))) e.preventDefault();
}, true);
document.addEventListener("dragleave", (e) => {
  if (!e.relatedTarget) document.body.classList.remove("dropping");
}, true);
document.addEventListener("drop", (e) => {
  if (!e.dataTransfer.files.length) return;
  e.preventDefault();
  e.stopPropagation();
  document.body.classList.remove("dropping");
  handleFiles([...e.dataTransfer.files]);
}, true);

// Several files at once (a "case"): each is analysed in turn, in filename order, with the question
// typed in the box or, if it's empty, the default for its kind. Answers appear as they finish, so
// the page can run in the background while presenting; "Ask about this file" picks one for follow-ups.
const CASE_DEFAULTS = {
  audio: "Summarize what is said, name any background sounds, and flag anything suspicious.",
};

async function runCase(files) {
  if (uploading || answering) return;
  answering = true;
  sendButton.disabled = true;
  uploadVersion++;
  attachment = null;
  const typed = input.value.trim();
  input.value = "";
  autosize();
  files.sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true }));
  let done = 0;
  for (const [i, file] of files.entries()) {
    chip.hidden = false;
    document.getElementById("chip-kind").textContent = `Case ${i + 1} of ${files.length}`;
    document.getElementById("chip-name").textContent = file.name;
    let att;
    try {
      att = await sendFile(file);
    } catch (err) {
      hideWelcome();
      const el = document.createElement("div");
      log.appendChild(el);
      fillError(el, `${file.name}: ${err.message}`);
      continue;
    }
    if (await askAbout(typed || CASE_DEFAULTS[att.kind] || "", att)) done++;
  }
  chip.hidden = true;
  const note = document.createElement("div");
  note.className = "msg bot";
  note.textContent = `Case finished: ${done} of ${files.length} files answered. ` +
    "Press \"Ask about this file\" on any of them to ask a follow-up.";
  log.appendChild(note);
  scrollDown();
  answering = false;
  sendButton.disabled = false;
  input.focus();
}

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
  if (uploading || answering) return;
  const question = input.value.trim();
  if (!question && !attachment) { input.focus(); return; }
  answering = true;
  input.value = "";
  autosize();
  sendButton.disabled = true;
  await askAbout(question, attachment);
  answering = false;
  sendButton.disabled = uploading;
  input.focus();
});

// Show the question, ask the server, and fill in the answer. Returns true if an answer came back.
async function askAbout(question, att) {
  addUserMessage(question, att);
  const looksLikeCode = /\b(write|create|generate|implement|build|make)\b.{0,60}\b(function|script|program|code|class|regex|parser|query|snippet|method)\b|\bin python\b|^\s*(def |from \w+ import |import \w+)/im;
  const pendingKind = att ? att.kind : (looksLikeCode.test(question) ? "code" : null);
  const pending = addPending(pendingKind);
  try {
    const r = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, attachment_id: att ? att.id : null }),
    });
    const data = await r.json();
    pending.stop();
    if (!r.ok) { fillError(pending.el, data.detail || "Something went wrong."); return false; }
    fillAnswer(pending.el, data);
    return true;
  } catch {
    pending.stop();
    fillError(pending.el, "Lost contact with the Strayline Desk server.");
    return false;
  } finally {
    scrollDown();
  }
}

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

// Opening /?case=demo (a link in the slides) loads the five demo files from this laptop and runs them as
// one case, exactly as if they had been dropped on the page.
const MIME = { mp4: "video/mp4", png: "image/png", wav: "audio/wav", md: "text/markdown", csv: "text/csv" };
async function runDemoCaseFromLink() {
  if (new URLSearchParams(location.search).get("case") !== "demo") return;
  history.replaceState(null, "", location.pathname); // a reload shouldn't start it again
  try {
    const list = await (await fetch("/api/demo-case")).json();
    const files = [];
    for (const item of list) {
      const blob = await (await fetch(`/api/demo-case/${item.index}`)).blob();
      files.push(new File([blob], item.name, { type: MIME[item.name.split(".").pop()] || blob.type }));
    }
    if (files.length) runCase(files);
  } catch {
    hideWelcome();
    const el = document.createElement("div");
    log.appendChild(el);
    fillError(el, "Couldn't load the demo files from this laptop.");
  }
}
runDemoCaseFromLink();
