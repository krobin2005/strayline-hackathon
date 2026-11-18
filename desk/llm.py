"""Thin client for the local Ollama server. Every model call in the app goes through here."""

import base64
import json
import os
import time
import urllib.error
import urllib.request

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")

# Model choices and the reasons for them are in README §3.
VISION_MODEL = os.environ.get("DESK_VISION_MODEL", "qwen3-vl:8b")
GENERAL_MODEL = os.environ.get("DESK_GENERAL_MODEL", "gemma4:e4b-it-q4_K_M")

# Keep models loaded between questions so follow-ups are fast.
KEEP_ALIVE = "30m"


class ModelError(RuntimeError):
    """The local model server is down, or the model returned an error."""


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def chat(model: str, prompt: str, *, system: str | None = None, media: list[bytes] | None = None,
         temperature: float = 0.0, timeout: float = 300.0) -> tuple[str, float]:
    """Send one user turn to a local model. Returns (answer text, seconds taken).

    `media` holds raw image or audio bytes. Ollama takes both through the `images` field.
    """
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    user = {"role": "user", "content": prompt}
    if media:
        user["images"] = [_b64(m) for m in media]
    messages.append(user)

    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "keep_alive": KEEP_ALIVE,
        "options": {"temperature": temperature},
    }
    # Qwen3 models reason silently by default, which is slow and can leave the answer empty.
    if model.startswith("qwen3"):
        payload["think"] = False

    request = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    start = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.load(response)
    except urllib.error.HTTPError as e:
        raise ModelError(f"{model}: {e.code} {e.read().decode(errors='replace')[:300]}") from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise ModelError(f"Can't reach Ollama at {OLLAMA_URL}. Is the Ollama app running? ({e})") from e

    answer = (body.get("message") or {}).get("content", "").strip()
    if not answer:
        raise ModelError(f"{model} returned an empty answer.")
    return answer, time.monotonic() - start


def server_ok() -> bool:
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/version", timeout=3):
            return True
    except (urllib.error.URLError, TimeoutError):
        return False
