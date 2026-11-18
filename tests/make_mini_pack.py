"""Build a tiny stand-in pack in the practice pack's format, from our own synthetic media.

    .venv/bin/python tests/make_mini_pack.py      # writes data/mini_pack/ (git-ignored)
    .venv/bin/python -m desk.eval --pack data/mini_pack --summary data/mini_pack/results.md

It exists to check the harness itself. Real numbers come from the organizers' practice pack.
"""

import json
import math
import struct
import subprocess
import wave
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data/mini_pack"


def main():
    for sub in ["image", "audio", "text", "video", "code/tests"]:
        (OUT / sub).mkdir(parents=True, exist_ok=True)
    items, answers = [], []

    def add(item, answer):
        items.append(item)
        answers.append({"id": item["id"], "modality": item["modality"], **answer})

    # Images: count shapes, read a sign.
    img = np.full((480, 640, 3), 245, np.uint8)
    for x in (100, 250, 400, 550):
        cv2.circle(img, (x, 300), 45, (40, 40, 200), -1)
    cv2.imwrite(str(OUT / "image/m_img_001.jpg"), img)
    add({"id": "m_img_001", "modality": "image", "file": "image/m_img_001.jpg", "question": "How many red circles are in this image?"},
        {"reference_answer": "4 (4 red circles)."})
    sign = np.full((480, 640, 3), 200, np.uint8)
    cv2.rectangle(sign, (170, 160), (470, 320), (30, 30, 180), -1)
    cv2.putText(sign, "NO ENTRY", (195, 260), cv2.FONT_HERSHEY_SIMPLEX, 1.6, (255, 255, 255), 4)
    cv2.imwrite(str(OUT / "image/m_img_002.jpg"), sign)
    add({"id": "m_img_002", "modality": "image", "file": "image/m_img_002.jpg", "question": "What does the sign say?"},
        {"reference_answer": "NO ENTRY"})

    # Audio: speech (macOS say) and a beep.
    transcript = "The quarterly report is due on Friday afternoon"
    subprocess.run(["say", "-o", str(OUT / "audio/s.aiff"), transcript], check=True)
    subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16@16000", "-c", "1", str(OUT / "audio/s.aiff"),
                    str(OUT / "audio/m_aud_001.wav")], check=True)
    (OUT / "audio/s.aiff").unlink()
    add({"id": "m_aud_001", "modality": "audio", "file": "audio/m_aud_001.wav", "question": "Transcribe the speech."},
        {"reference_answer": transcript, "transcript": transcript})
    add({"id": "m_aud_002", "modality": "audio", "file": "audio/m_aud_001.wav", "question": "When is the report due?"},
        {"reference_answer": "Friday afternoon", "transcript": transcript})
    with wave.open(str(OUT / "audio/m_aud_003.wav"), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes(b"".join(struct.pack("<h", int(12000 * math.sin(2 * math.pi * 1000 * i / 16000))) for i in range(48000)))
    add({"id": "m_aud_003", "modality": "audio", "file": "audio/m_aud_003.wav", "question": "What sound is this?"},
        {"reference_answer": "a beep or tone"})

    # Text: one document, one answerable and one unanswerable question.
    (OUT / "text/m_txt_doc_01.txt").write_text(
        "The Harbor Library opened in 1921. It has 3 floors and a rooftop garden. "
        "The children's section is on the second floor. The library closes at 8 pm on weekdays.")
    add({"id": "m_txt_001", "modality": "text", "file": "text/m_txt_doc_01.txt", "question": "What year did the library open?"},
        {"reference_answer": "1921", "answerable": True})
    add({"id": "m_txt_002", "modality": "text", "file": "text/m_txt_doc_01.txt", "question": "Who designed the library building?"},
        {"reference_answer": "", "answerable": False})

    # Video: a ball moving left to right and three squares.
    out = cv2.VideoWriter(str(OUT / "video/m_vid_001.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), 20, (640, 360))
    for i in range(120):
        f = np.full((360, 640, 3), 235, np.uint8)
        for k in range(3):
            cv2.rectangle(f, (40 + k * 70, 280), (90 + k * 70, 330), (200, 80, 30), -1)
        cv2.circle(f, (int(40 + 560 * i / 120), 180), 25, (30, 30, 220), -1)
        out.write(f)
    out.release()
    add({"id": "m_vid_001", "modality": "video", "file": "video/m_vid_001.mp4", "question": "How many blue squares are in the video?"},
        {"reference_answer": "3"})
    add({"id": "m_vid_002", "modality": "video", "file": "video/m_vid_001.mp4", "question": "In which direction does the red ball move?"},
        {"reference_answer": "left to right"})

    # Code: a HumanEval-style check(candidate) test and a pytest-style test.
    add({"id": "m_code_001", "modality": "code", "file": None, "question":
         'def count_vowels(s: str) -> int:\n    """Return the number of vowels (a, e, i, o, u, either case) in s.\n'
         '    >>> count_vowels("Hello")\n    2\n    """\n'},
        {"reference_answer": "", "entry_point": "count_vowels"})
    (OUT / "code/tests/m_code_001_test.py").write_text(
        "def check(candidate):\n    assert candidate('Hello') == 2\n    assert candidate('') == 0\n"
        "    assert candidate('AEIOUxyz') == 5\n")
    add({"id": "m_code_002", "modality": "code", "file": None, "question":
         'def second_largest(nums: list) -> int:\n    """Return the second largest distinct value in nums.\n'
         '    >>> second_largest([3, 1, 4, 4])\n    3\n    """\n'},
        {"reference_answer": "", "entry_point": "second_largest"})
    (OUT / "code/tests/m_code_002_test.py").write_text(
        "from solution import second_largest\n\ndef test_basic():\n    assert second_largest([3, 1, 4, 4]) == 3\n"
        "    assert second_largest([10, 20]) == 10\n")

    (OUT / "items.json").write_text(json.dumps(items, indent=1))
    (OUT / "answers.json").write_text(json.dumps(answers, indent=1))
    print(f"Wrote {len(items)} items to {OUT}")


if __name__ == "__main__":
    main()
