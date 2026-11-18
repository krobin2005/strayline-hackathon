"""Video: sample frames with OpenCV and let the vision model read them in order."""

import tempfile
from pathlib import Path

import cv2

from .. import llm
from ..router import VIDEO
from . import Answer

MIN_FRAMES = 8
MAX_FRAMES = 16
SECONDS_PER_FRAME = 2.0  # longer clips get more frames, up to MAX_FRAMES
MAX_SIDE = 512
# Each 512-px frame costs roughly 400-1,100 tokens in Qwen3-VL; 16 frames need about this much room.
CONTEXT_TOKENS = 20480

SYSTEM = (
    "You are Strayline Desk, an assistant for a college IT security team. You are given frames "
    "sampled in order from one short video, each labelled with its time. Treat them as a single "
    "clip. Track how things move and change between frames. When counting, count distinct objects "
    "across the whole clip, not per frame, and say how you counted. Quote any visible text exactly. "
    "If the frames can't answer the question, say so."
)
DEFAULT_QUESTION = (
    "Describe what happens in this video in at most 5 short bullet points with approximate times, "
    "then one sentence on anything that looks like a scam or attack (or say nothing does). "
    "Keep it under 120 words."
)


class VideoError(ValueError):
    pass


def sample_frames(data: bytes, filename: str) -> tuple[list[bytes], list[float], float]:
    """Return (JPEG frames, their times in seconds, clip length in seconds)."""
    with tempfile.NamedTemporaryFile(suffix=Path(filename).suffix or ".mp4") as tmp:
        tmp.write(data)
        tmp.flush()
        cap = cv2.VideoCapture(tmp.name)
        if not cap.isOpened():
            raise VideoError("Couldn't open that video. Try an MP4 or MOV file.")
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        if total <= 0:
            cap.release()
            raise VideoError("That video has no readable frames.")
        length = total / fps
        count = max(MIN_FRAMES, min(MAX_FRAMES, int(length / SECONDS_PER_FRAME) + 1))
        count = min(count, total)
        indices = [round(i * (total - 1) / max(count - 1, 1)) for i in range(count)]

        frames, times = [], []
        for index in indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, index)
            ok, frame = cap.read()
            if not ok:
                continue
            h, w = frame.shape[:2]
            scale = MAX_SIDE / max(h, w)
            if scale < 1:
                frame = cv2.resize(frame, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
            ok, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if ok:
                frames.append(jpeg.tobytes())
                times.append(index / fps)
        cap.release()
    if not frames:
        raise VideoError("Couldn't read any frames from that video.")
    return frames, times, length


def answer(data: bytes, filename: str, question: str) -> Answer:
    frames, times, length = sample_frames(data, filename)
    labels = ", ".join(f"frame {i + 1} at {t:.1f} s" for i, t in enumerate(times))
    prompt = (f"These are {len(frames)} frames from a {length:.1f}-second video, in order: {labels}.\n\n"
              f"{question.strip() or DEFAULT_QUESTION}")
    text, seconds = llm.chat(llm.VISION_MODEL, prompt, system=SYSTEM, media=frames, context=CONTEXT_TOKENS)
    evidence = [f"{len(frames)} frames sampled from a {length:.1f} s clip at: "
                + ", ".join(f"{t:.1f} s" for t in times)]
    return Answer(text=text, kind=VIDEO, model=llm.VISION_MODEL, seconds=seconds, evidence=evidence)
