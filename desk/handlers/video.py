"""Video: sample frames with OpenCV and let the vision model read them in order."""

import base64
import math
import tempfile
import time
from pathlib import Path

import cv2
import numpy as np

from .. import llm
from ..router import VIDEO
from . import Answer

MIN_FRAMES = 10
MAX_FRAMES = 16
SECONDS_PER_FRAME = 1.0  # one frame a second (counts and bounces need it), between MIN and MAX frames
CELL_WIDTH = 288
CELL_HEIGHT = 216


SYSTEM = (
    "You are Strayline Desk, an assistant for a college IT security team. You are given frames "
    "sampled in chronological order from one short video. Treat them as a single "
    "clip. Track how things move and change between frames. When counting, count distinct objects "
    "across the whole clip, not per frame: objects that appear one at a time each count. Quote any "
    "visible text exactly. Answer directly in one or two sentences; do not describe the frames one by "
    "one. If the frames can't answer the question, say so."
)
DEFAULT_QUESTION = (
    "Describe what happens in this video in at most 5 short bullet points with approximate times, "
    "then one sentence on anything that looks like a scam or attack (or say nothing does). "
    "Keep it under 120 words."
)


class VideoError(ValueError):
    pass


def sample_frames(data: bytes, filename: str) -> tuple[list[np.ndarray], list[float], float]:
    """Return sampled frames, their timestamps, and the clip duration."""
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
            height, width = frame.shape[:2]
            scale = min(CELL_WIDTH / width, CELL_HEIGHT / height)
            size = max(1, round(width * scale)), max(1, round(height * scale))
            frames.append(cv2.resize(frame, size, interpolation=cv2.INTER_AREA))
            times.append(index / fps)
        cap.release()
    if not frames:
        raise VideoError("Couldn't read any frames from that video.")
    return frames, times, length


def contact_sheet(frames: list[np.ndarray]) -> tuple[bytes, int]:
    """Place the chronological samples in one image, preserving their aspect ratio."""
    columns = min(4, math.ceil(math.sqrt(len(frames))))
    rows = math.ceil(len(frames) / columns)
    sheet = np.zeros((rows * CELL_HEIGHT, columns * CELL_WIDTH, 3), dtype=np.uint8)
    for index, frame in enumerate(frames):
        height, width = frame.shape[:2]
        x = index % columns * CELL_WIDTH + (CELL_WIDTH - width) // 2
        y = index // columns * CELL_HEIGHT + (CELL_HEIGHT - height) // 2
        sheet[y:y + height, x:x + width] = frame
    ok, jpeg = cv2.imencode(".jpg", sheet, [cv2.IMWRITE_JPEG_QUALITY, 90])
    if not ok:
        raise VideoError("Couldn't prepare video frames.")
    return jpeg.tobytes(), columns


def _jpeg(frame: np.ndarray) -> bytes:
    ok, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
    if not ok:
        raise VideoError("Couldn't prepare video frames.")
    return jpeg.tobytes()


def answer(data: bytes, filename: str, question: str) -> Answer:
    start = time.monotonic()
    frames, times, length = sample_frames(data, filename)
    # The model gets the frames as separate images, in order. A single contact-sheet image was ~4x
    # faster but, on the practice pack, came back empty on 6/15 clips and confused motion and counts
    # (6/15 right vs 11/15 with separate frames). The sheet is still shown to the user as evidence.
    sheet_bytes, _ = contact_sheet(frames)
    labels = ", ".join(f"frame {i + 1} at {t:.1f} s" for i, t in enumerate(times))
    prompt = (f"These are {len(frames)} frames from a {length:.1f}-second video, in order: {labels}.\n\n"
              f"{question.strip() or DEFAULT_QUESTION}")
    text, _ = llm.chat(llm.VISION_MODEL, prompt, system=SYSTEM, media=[_jpeg(f) for f in frames], max_tokens=2048)
    evidence = [f"{len(frames)} frames sampled from a {length:.1f} s clip at: "
                + ", ".join(f"{t:.1f} s" for t in times)]
    return Answer(text=text, kind=VIDEO, model=llm.VISION_MODEL, seconds=time.monotonic() - start, evidence=evidence,
                  frame_sheet_jpeg=base64.b64encode(sheet_bytes).decode("ascii"))
