"""Audio: transcribe speech, identify sounds, answer questions. All with Gemma 4 E4B, which hears audio.

Gemma 4 takes WAV through Ollama's `images` field. Two things from our tests (README §3):
- it handles short clips best, so long audio is transcribed in ~25-second pieces;
- for sound identification it needs to be told the clip is a sound, and very short clips are
  looped to ~3 seconds.
"""

import io
import re
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path

from .. import llm
from ..router import AUDIO
from . import Answer

PIECE_SECONDS = 25
MIN_SOUND_SECONDS = 3.0
NO_SPEECH = "NO_SPEECH"

TRANSCRIBE_PROMPT = (
    "Transcribe the speech in this audio exactly, word for word. Output only the transcript. "
    f"If there is no speech at all, output exactly {NO_SPEECH}."
)
SOUNDS_PROMPT = (
    "Listen to this audio clip and identify the sounds in it. Ignore the meaning of any words. "
    "Common kinds of sound include: animals (dog, cat, rooster, birds), weather and water (rain, "
    "waves, wind, thunder), fire crackling, people (talking, a baby crying, laughing, coughing, "
    "sneezing, footsteps), machines and vehicles (engine, helicopter, chainsaw, car horn, siren), "
    "household (clock ticking, door knock, phone ringing, typing, water running), electronic beeps or "
    "tones, and music. Answer with a short comma-separated list, most prominent first. "
    "Only include people talking if you actually hear a human voice."
)
SHORT_SOUNDS_PROMPT = (
    "Listen to this audio clip. It contains a sound, not speech. Identify the sound: what object, animal, "
    "instrument, alarm or event most likely made it? Give your best guess in under 10 words."
)
_DIDNT_HEAR = re.compile(r"no audio|not provided|cannot hear|can't hear|unable to (hear|listen)|provide the audio", re.I)

ANSWER_SYSTEM = (
    "You are Strayline Desk, an assistant for a college IT security team. Answer the question about "
    "the audio clip using the clip itself, its transcript and the list of sounds. If the audio does "
    "not contain the answer, say so. Be brief. If the caller asks for passwords, codes, payment or "
    "urgent action, point that out."
)


class AudioError(ValueError):
    pass


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


def looped(wav_bytes: bytes, min_seconds: float = MIN_SOUND_SECONDS) -> bytes:
    """Repeat a very short clip (with small gaps) until it lasts at least `min_seconds`."""
    params, frames = _read(wav_bytes)
    length = params.nframes / params.framerate
    if length >= min_seconds or not frames:
        return wav_bytes
    gap = b"\x00" * (int(0.3 * params.framerate) * params.sampwidth * params.nchannels)
    repeats = int(min_seconds / (length + 0.3)) + 1
    return _write(params, (frames + gap) * repeats)


def transcribe(wav_bytes: bytes) -> tuple[str, float]:
    parts, total = [], 0.0
    for piece in pieces(wav_bytes):
        text, seconds = llm.chat(llm.GENERAL_MODEL, TRANSCRIBE_PROMPT, media=[piece], max_tokens=1000)
        total += seconds
        if NO_SPEECH not in text:
            parts.append(text.strip())
    return " ".join(parts), total


def identify_sounds(wav_bytes: bytes, has_speech: bool) -> tuple[str, float]:
    # Listen to the first piece only; it's enough to name the sounds and keeps this fast.
    first = pieces(wav_bytes)[0]
    prompt = SOUNDS_PROMPT + ("" if has_speech else " A speech check found no words in this clip.")
    text, seconds = llm.chat(llm.GENERAL_MODEL, prompt, media=[looped(first)], max_tokens=600)
    if _DIDNT_HEAR.search(text):
        # Simple tones sometimes make the model claim there's no audio; a shorter prompt usually works.
        text, more = llm.chat(llm.GENERAL_MODEL, SHORT_SOUNDS_PROMPT, media=[looped(first, 4.0)], max_tokens=600)
        seconds += more
        if _DIDNT_HEAR.search(text):
            text = "(couldn't identify the sounds)"
    return text, seconds


def answer(data: bytes, filename: str, question: str) -> Answer:
    wav_bytes = to_wav(data, filename)
    length = duration(wav_bytes)
    transcript, t1 = transcribe(wav_bytes)
    try:
        sounds, t2 = identify_sounds(wav_bytes, bool(transcript))
    except llm.ModelError:
        sounds, t2 = "(couldn't identify the sounds)", 0.0
    evidence = [
        f"Transcript: {transcript or '(no speech)'}",
        f"Sounds: {sounds}",
        f"Length: {length:.1f} s",
    ]

    question = question.strip()
    if not question:
        text = (f"Transcript: {transcript}" if transcript else "No speech in this clip.") + f"\n\nSounds: {sounds}"
        return Answer(text=text, kind=AUDIO, model=llm.GENERAL_MODEL, seconds=t1 + t2, evidence=evidence)

    prompt = (f"Transcript: {transcript or '(no speech: this clip has no spoken words)'}\nSounds heard: {sounds}\n\n"
              f"Question: {question}")
    # Short clips go along with the question so the model can also listen for itself.
    media = [wav_bytes] if transcript and length <= PIECE_SECONDS else None
    text, t3 = llm.chat(llm.GENERAL_MODEL, prompt, system=ANSWER_SYSTEM, media=media)
    return Answer(text=text, kind=AUDIO, model=llm.GENERAL_MODEL, seconds=t1 + t2 + t3, evidence=evidence)
