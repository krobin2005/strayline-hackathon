"""Audio: identify sounds, transcribe speech, answer questions.

- Sounds: a small open-weight audio classifier trained on AudioSet's 527 everyday sound classes
  (MIT/ast-finetuned-audioset, BSD-3). Gemma 4 alone named only ~1 in 10 environmental sounds in the
  practice pack; the classifier got 9 in 10 in its top 3, in ~0.1 s.
- Speech: Gemma 4 E4B transcribes (WAV through Ollama's `images` field) in ~25-second pieces, which it
  handles best. Skipped when the classifier hears no speech, so it can't invent words.
- Answers: Gemma 4 answers from the transcript, the sound labels and (for speech) the clip itself.
"""

import io
import os
import shutil
import subprocess
import tempfile
import threading
import time
import wave
from pathlib import Path

import numpy as np

from .. import llm
from ..router import AUDIO
from . import Answer

PIECE_SECONDS = 25
NO_SPEECH = "NO_SPEECH"
SOUND_MODEL = "MIT/ast-finetuned-audioset-10-10-0.4593"
SPEECH_LABELS = {"Speech", "Male speech, man speaking", "Female speech, woman speaking", "Child speech, kid speaking",
                 "Conversation", "Narration, monologue", "Speech synthesizer", "Babbling", "Whispering"}

TRANSCRIBE_PROMPT = (
    "Transcribe the speech in this audio exactly, word for word. Output only the transcript. "
    f"If there is no speech at all, output exactly {NO_SPEECH}."
)
ANSWER_SYSTEM = (
    "You are Strayline Desk, an assistant for a college IT security team. Answer the question about an "
    "audio clip using its transcript and the sounds an audio classifier identified (with confidence). "
    "For 'what sound is this' questions, name the most likely sound source in a few words. If the audio "
    "does not contain the answer, say so. Be brief. If a caller asks for passwords, codes, payment or "
    "urgent action, point that out."
)


class AudioError(ValueError):
    pass


_classifier = None
_classifier_lock = threading.Lock()


def classifier():
    """Load the sound classifier once. Works offline after the first download (setup.sh does that)."""
    global _classifier
    with _classifier_lock:
        if _classifier is None:
            from huggingface_hub import try_to_load_from_cache
            if isinstance(try_to_load_from_cache(SOUND_MODEL, "config.json"), str):
                os.environ.setdefault("HF_HUB_OFFLINE", "1")  # cached: never touch the network
            from transformers import pipeline
            _classifier = pipeline("audio-classification", model=SOUND_MODEL, device="cpu")
        return _classifier


def to_wav(data: bytes, filename: str) -> bytes:
    """Return the audio as WAV. The web page already sends WAV; other formats are converted with
    macOS's built-in afconvert (no extra installs)."""
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return data
    afconvert = shutil.which("afconvert")
    if not afconvert:
        raise AudioError("Please upload WAV audio (other formats need macOS to convert).")
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / ("in" + (Path(filename).suffix or ".audio"))
        dst = Path(tmp) / "out.wav"
        src.write_bytes(data)
        result = subprocess.run([afconvert, "-f", "WAVE", "-d", "LEI16@16000", "-c", "1", str(src), str(dst)],
                                capture_output=True, timeout=60)
        if result.returncode != 0 or not dst.exists():
            raise AudioError(f"Couldn't read that audio file ({Path(filename).suffix or 'unknown type'}).")
        return dst.read_bytes()


def _read(wav_bytes: bytes):
    with wave.open(io.BytesIO(wav_bytes)) as w:
        return w.getparams(), w.readframes(w.getnframes())


def _write(params, frames: bytes) -> bytes:
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setparams(params)
        w.writeframes(frames)
    return out.getvalue()


def duration(wav_bytes: bytes) -> float:
    params, _ = _read(wav_bytes)
    return params.nframes / params.framerate


def pieces(wav_bytes: bytes, seconds: float = PIECE_SECONDS) -> list[bytes]:
    params, frames = _read(wav_bytes)
    frame_bytes = params.sampwidth * params.nchannels
    step = int(seconds * params.framerate) * frame_bytes
    return [_write(params, frames[i:i + step]) for i in range(0, max(len(frames), 1), step)] or [wav_bytes]


def _samples(wav_bytes: bytes) -> tuple[np.ndarray, int]:
    params, frames = _read(wav_bytes)
    if params.sampwidth != 2:
        raise AudioError("Expected 16-bit audio.")
    x = np.frombuffer(frames, np.int16).astype(np.float32) / 32768
    if params.nchannels > 1:
        x = x.reshape(-1, params.nchannels).mean(1)
    return x, params.framerate


def identify_sounds(wav_bytes: bytes, top: int = 3, min_score: float = 0.05) -> tuple[list[tuple[str, float]], float]:
    """Top sound labels with confidence, from the first 10 seconds (the classifier's window)."""
    start = time.monotonic()
    x, rate = _samples(wav_bytes)
    out = classifier()({"raw": x[: rate * 10], "sampling_rate": rate}, top_k=8)
    labels = [(o["label"], float(o["score"])) for o in out if o["score"] >= min_score][:top] or \
             [(out[0]["label"], float(out[0]["score"]))]
    return labels, time.monotonic() - start


def transcribe(wav_bytes: bytes) -> tuple[str, float]:
    parts, total = [], 0.0
    for piece in pieces(wav_bytes):
        text, seconds = llm.chat(llm.GENERAL_MODEL, TRANSCRIBE_PROMPT, media=[piece], max_tokens=1000)
        total += seconds
        if NO_SPEECH not in text:
            parts.append(text.strip())
    return " ".join(parts), total


def answer(data: bytes, filename: str, question: str) -> Answer:
    wav_bytes = to_wav(data, filename)
    length = duration(wav_bytes)
    sounds, t0 = identify_sounds(wav_bytes)
    has_speech = any(label in SPEECH_LABELS and score >= 0.15 for label, score in sounds)
    transcript, t1 = transcribe(wav_bytes) if has_speech else ("", 0.0)
    sound_text = ", ".join(f"{label} ({100 * score:.0f}%)" for label, score in sounds)
    evidence = [f"Sounds (audio classifier): {sound_text}",
                f"Transcript: {transcript or '(no speech)'}", f"Length: {length:.1f} s"]

    question = question.strip()
    if not question:
        text = f"Sounds: {sound_text}" + (f"\n\nTranscript: {transcript}" if transcript else "\n\nNo speech in this clip.")
        return Answer(text=text, kind=AUDIO, model=llm.GENERAL_MODEL, seconds=t0 + t1, evidence=evidence)

    prompt = (f"Sounds identified: {sound_text}\nTranscript: {transcript or '(no speech in this clip)'}\n\n"
              f"Question: {question}")
    # Speech clips go along with the question so the model can also listen for tone and details.
    media = [wav_bytes] if transcript and length <= PIECE_SECONDS else None
    text, t2 = llm.chat(llm.GENERAL_MODEL, prompt, system=ANSWER_SYSTEM, media=media)
    return Answer(text=text, kind=AUDIO, model=llm.GENERAL_MODEL, seconds=t0 + t1 + t2, evidence=evidence)
