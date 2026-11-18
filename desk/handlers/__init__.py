"""One module per kind of input. Each handler returns an Answer."""

from dataclasses import dataclass, field


@dataclass
class Answer:
    text: str
    kind: str
    model: str
    seconds: float
    # What the answer was based on, shown under it in the app (passages, transcript, frames...).
    evidence: list[str] = field(default_factory=list)
