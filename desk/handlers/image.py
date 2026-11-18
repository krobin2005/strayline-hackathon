"""Images: describe a photo or screenshot and answer questions about it."""

from .. import llm
from ..router import IMAGE
from . import Answer

SYSTEM = (
    "You are Strayline Desk, an assistant for a college IT security team. You are looking at an image "
    "the user uploaded. Answer only from what is visible in the image. When counting, count carefully "
    "and give the number. When reading text, quote it exactly. If something can't be determined from "
    "the image, say so plainly instead of guessing."
)

DEFAULT_QUESTION = (
    "Describe this image in two or three sentences. If it is a screenshot of an email, message, website "
    "or login page, also say whether it looks like phishing and list the specific signs (sender, links, "
    "urgency, requests for passwords or money, branding problems)."
)


def answer(image: bytes, question: str) -> Answer:
    prompt = question.strip() or DEFAULT_QUESTION
    # Big photos can need more than Ollama's default 4,096-token context.
    text, seconds = llm.chat(llm.VISION_MODEL, prompt, system=SYSTEM, media=[image], context=8192)
    return Answer(text=text, kind=IMAGE, model=llm.VISION_MODEL, seconds=seconds)
