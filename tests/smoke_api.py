"""Quick end-to-end check of every input type against a running app.

Start the app (`.venv/bin/python -m desk`), then run:
    .venv/bin/python tests/smoke_api.py

It makes its own test clips (a spoken voicemail via macOS `say`, a tone, a short video with a sign
and a moving ball) and prints each answer with its time. This is a smoke test, not the scored
evaluation; that's the practice-pack harness.
"""

import io
import json
import math
import struct
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid
import wave
from pathlib import Path

BASE = "http://localhost:8000"
ROOT = Path(__file__).resolve().parent.parent


def upload(name: str, data: bytes, content_type: str) -> str:
    boundary = uuid.uuid4().hex
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{name}\"\r\n"
            f"Content-Type: {content_type}\r\n\r\n").encode() + data + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(f"{BASE}/api/upload", body, {"Content-Type": f"multipart/form-data; boundary={boundary}"})
    return json.load(urllib.request.urlopen(req))["id"]


def ask(question: str, attachment_id: str | None = None) -> dict:
    req = urllib.request.Request(f"{BASE}/api/ask", json.dumps({"question": question, "attachment_id": attachment_id}).encode(),
                                 {"Content-Type": "application/json"})
    try:
        return json.load(urllib.request.urlopen(req, timeout=600))
    except urllib.error.HTTPError as e:
        return {"text": "ERROR: " + json.load(e).get("detail", str(e)), "seconds": 0, "model": "-"}


def tone_wav(seconds=2.0, freq=880) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes(b"".join(struct.pack("<h", int(12000 * math.sin(2 * math.pi * freq * i / 16000)))
                               for i in range(int(16000 * seconds))))
    return buf.getvalue()


def speech_wav(tmp: Path) -> bytes | None:
    text = ("Hello, this is the IT help desk. We noticed a problem with your account. "
            "Please call us back at five five five, one two one two, and have your password ready.")
    try:
        subprocess.run(["say", "-o", str(tmp / "s.aiff"), text], check=True, capture_output=True)
        subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16@16000", "-c", "1", str(tmp / "s.aiff"), str(tmp / "s.wav")],
                       check=True, capture_output=True)
        return (tmp / "s.wav").read_bytes()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None  # not on a Mac


def test_video(tmp: Path) -> bytes:
    import cv2
    import numpy as np
    path, (w, h), fps = str(tmp / "v.mp4"), (640, 360), 20
    out = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    for i in range(fps * 6):
        f = np.full((h, w, 3), 235, np.uint8)
        cv2.rectangle(f, (450, 30), (610, 90), (40, 120, 40), -1)
        cv2.putText(f, "EXIT 4", (468, 72), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255, 255, 255), 3)
        for k in range(3):
            cv2.rectangle(f, (40 + k * 70, 280), (90 + k * 70, 330), (200, 80, 30), -1)
        cv2.circle(f, (int(40 + (w - 80) * i / (fps * 6)), 180), 25, (30, 30, 220), -1)
        out.write(f)
    out.release()
    return Path(path).read_bytes()


def show(label: str, result: dict, expect: str = ""):
    text = " ".join(result.get("text", "").split())
    print(f"\n[{label}] {result.get('seconds', 0):.1f}s  {result.get('model')}")
    print(f"  {text[:400]}")
    if expect:
        print(f"  expected: {expect}")


def main():
    start = time.monotonic()
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        show("text", ask("In one sentence, what is credential stuffing?"))

        doc = upload("runbook.md", (ROOT / "tests/fixtures/sample_runbook.md").read_bytes(), "text/markdown")
        show("document", ask("Who do we notify about a compromised account?", doc),
             "Director of Information Security + account owner")
        show("document, not there", ask("What is the library wifi password?", doc), "This isn't in the document.")

        speech = speech_wav(tmp)
        if speech:
            a = upload("voicemail.wav", speech, "audio/wav")
            show("audio, no question", ask("", a), "transcript + 'speech'")
            show("audio, question", ask("What does the caller want? Is it suspicious?", a), "password → suspicious")
        tone = upload("tone.wav", tone_wav(), "audio/wav")
        show("audio, sound", ask("", tone), "no speech; a tone/beep")

        v = upload("clip.mp4", test_video(tmp), "video/mp4")
        show("video", ask("What does the sign say, which way does the red ball move, and how many blue squares are there?", v),
             "EXIT 4, left to right, 3")

        show("code", ask("Write a Python function that checks whether a string is a valid IPv4 address."),
             "✅ ran and passed")
    print(f"\nTotal {time.monotonic() - start:.0f}s")


if __name__ == "__main__":
    sys.exit(main())
