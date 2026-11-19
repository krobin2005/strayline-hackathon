"""Web server: one chat page plus a small JSON API. Runs on the laptop; phones on the same network can use it."""

import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import llm, router
from .sandbox import SandboxUnavailable
from .handlers import audio, code, document, image, logs, text, video

STATIC = Path(__file__).parent / "static"
MAX_UPLOAD_BYTES = 400 * 1024 * 1024  # a full day of CIC-IDS2017 logs is ~290 MB

MAX_STORED_BYTES = 512 * 1024 * 1024
MAX_ATTACHMENTS = 32

app = FastAPI(title="Strayline Desk")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@dataclass
class Attachment:
    name: str
    kind: str
    data: bytes


# Uploads live in memory only, for this run of the app. Nothing is written to disk or sent anywhere.
_attachments: dict[str, Attachment] = {}


class Ask(BaseModel):
    question: str = ""
    attachment_id: str | None = None


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
def health():
    return {"ollama": llm.server_ok(), "vision_model": llm.VISION_MODEL, "general_model": llm.GENERAL_MODEL}


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "That file is over 400 MB.")
    if not data:
        raise HTTPException(400, "That file is empty.")
    kind = router.kind_of(file.filename or "", file.content_type)
    if kind == router.UNKNOWN:
        raise HTTPException(415, f"I can't read {file.filename!r}. Try an image, audio, video, PDF, text or log file.")
    attachment_id = uuid.uuid4().hex
    # Reserve room for the new file. Repeated full-day uploads previously grew without bound.
    retained = sum(len(item.data) for item in _attachments.values())
    while _attachments and (retained + len(data) > MAX_STORED_BYTES or len(_attachments) >= MAX_ATTACHMENTS):
        oldest = next(iter(_attachments))
        retained -= len(_attachments.pop(oldest).data)
    _attachments[attachment_id] = Attachment(name=file.filename or "upload", kind=kind, data=data)
    return {"id": attachment_id, "kind": kind, "name": file.filename}


@app.post("/api/ask")
def ask(body: Ask):
    question = body.question.strip()
    attachment = _attachments.get(body.attachment_id) if body.attachment_id else None
    if body.attachment_id and attachment is None:
        raise HTTPException(404, "That file is no longer loaded. Upload it again.")
    if not question and attachment is None:
        raise HTTPException(400, "Type a question or attach a file.")

    try:
        if attachment is None:
            result = code.answer(question) if code.is_code_request(question) else text.answer(question)
        elif attachment.kind == router.IMAGE:
            result = image.answer(attachment.data, question)
        elif attachment.kind == router.DOCUMENT:
            result = document.answer(attachment.data, attachment.name, question)
        elif attachment.kind == router.AUDIO:
            result = audio.answer(attachment.data, attachment.name, question)
        elif attachment.kind == router.VIDEO:
            result = video.answer(attachment.data, attachment.name, question)
        elif attachment.kind == router.LOGS and code.is_code_request(question):
            result = code.answer(question, attachment.name, attachment.data)
        else:
            result = logs.answer(body.attachment_id, attachment.data, attachment.name, question)
    except (llm.ModelError, SandboxUnavailable) as e:
        raise HTTPException(503, str(e)) from e
    except (audio.AudioError, video.VideoError) as e:
        raise HTTPException(422, str(e)) from e
    return asdict(result)
