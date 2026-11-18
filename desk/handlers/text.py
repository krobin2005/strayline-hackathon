"""Plain questions with no attachment."""

from .. import llm
from . import Answer

SYSTEM = (
    "You are Strayline Desk, an offline assistant for a small college's IT security team. You run "
    "entirely on the team's laptop; nothing leaves the building. Be direct and practical. If you are "
    "not sure of something, say so."
)


def answer(question: str) -> Answer:
    text, seconds = llm.chat(llm.GENERAL_MODEL, question, system=SYSTEM)
    return Answer(text=text, kind="text", model=llm.GENERAL_MODEL, seconds=seconds)
