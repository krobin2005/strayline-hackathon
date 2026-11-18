"""Documents: answer from the document's own text, and say so when the answer isn't there.

Pipeline: extract text with page numbers → split into overlapping chunks → pick the most relevant
chunks with BM25 (no extra model needed) → the model answers only from those chunks, or replies
NOT_FOUND.
"""

import io
import math
import re
from collections import Counter
from dataclasses import dataclass

from pypdf import PdfReader

from .. import llm
from ..router import DOCUMENT
from . import Answer

CHUNK_WORDS = 180
OVERLAP_WORDS = 40
TOP_K = 4
NOT_FOUND = "NOT_FOUND"
NOT_FOUND_MESSAGE = "This isn't in the document."

SYSTEM = (
    "You answer questions about a document using ONLY the numbered passages provided. "
    "Do not use outside knowledge. If the passages do not contain the answer, reply with exactly "
    f"{NOT_FOUND} and nothing else. Otherwise answer in one to three sentences and cite the page, "
    "like (p. 3)."
)

_STOPWORDS = set(
    "a an the and or of to in on at for by with from is are was were be been it its this that these "
    "those as if then than so do does did what which who whom whose when where why how can could "
    "should would will shall may might must i you we they he she our your their my me us them".split()
)


@dataclass
class Chunk:
    page: int
    text: str


def extract_pages(data: bytes, filename: str) -> list[str]:
    """Return the document's text, one string per page (plain text counts as one page)."""
    if filename.lower().endswith(".pdf"):
        reader = PdfReader(io.BytesIO(data))
        return [(page.extract_text() or "") for page in reader.pages]
    return [data.decode("utf-8", errors="replace")]


def chunk_pages(pages: list[str]) -> list[Chunk]:
    chunks = []
    step = CHUNK_WORDS - OVERLAP_WORDS
    for number, text in enumerate(pages, start=1):
        words = text.split()
        for start in range(0, max(len(words), 1), step):
            piece = " ".join(words[start:start + CHUNK_WORDS])
            if piece:
                chunks.append(Chunk(page=number, text=piece))
            if start + CHUNK_WORDS >= len(words):
                break
    return chunks


def _terms(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in _STOPWORDS]


def top_chunks(chunks: list[Chunk], question: str, k: int = TOP_K) -> list[Chunk]:
    """Rank chunks by BM25 against the question."""
    if not chunks:
        return []
    docs = [_terms(c.text) for c in chunks]
    avg_len = sum(len(d) for d in docs) / len(docs) or 1.0
    doc_freq = Counter(term for d in docs for term in set(d))
    n = len(docs)
    query = set(_terms(question))
    k1, b = 1.5, 0.75

    def score(doc: list[str]) -> float:
        counts = Counter(doc)
        total = 0.0
        for term in query:
            if term not in counts:
                continue
            idf = math.log(1 + (n - doc_freq[term] + 0.5) / (doc_freq[term] + 0.5))
            tf = counts[term]
            total += idf * tf * (k1 + 1) / (tf + k1 * (1 - b + b * len(doc) / avg_len))
        return total

    ranked = sorted(range(n), key=lambda i: score(docs[i]), reverse=True)
    best = [chunks[i] for i in ranked[:k] if score(docs[i]) > 0]
    # Nothing matched at all: fall back to the start of the document (good for "summarize this").
    return best or chunks[:k]


def answer(data: bytes, filename: str, question: str) -> Answer:
    pages = extract_pages(data, filename)
    chunks = chunk_pages(pages)
    if not chunks:
        return Answer(text="I couldn't read any text in this document. If it's a scanned PDF, "
                           "upload the page as an image instead.",
                      kind=DOCUMENT, model="none", seconds=0.0)

    question = question.strip() or "Summarize this document in three sentences."
    passages = top_chunks(chunks, question)
    numbered = "\n\n".join(f"[{i}] (p. {c.page}) {c.text}" for i, c in enumerate(passages, 1))
    prompt = f"Passages:\n{numbered}\n\nQuestion: {question}"

    text, seconds = llm.chat(llm.GENERAL_MODEL, prompt, system=SYSTEM)
    if NOT_FOUND in text:
        text = NOT_FOUND_MESSAGE
    evidence = [f"p. {c.page}: {c.text[:280]}{'…' if len(c.text) > 280 else ''}" for c in passages]
    return Answer(text=text, kind=DOCUMENT, model=llm.GENERAL_MODEL, seconds=seconds, evidence=evidence)
