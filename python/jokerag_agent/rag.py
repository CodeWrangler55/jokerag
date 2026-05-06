from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .models import Headline
from .ranking import normalize_headline_title

try:  # pragma: no cover - exercised when langchain-core is installed
    from langchain_core.documents import Document
except Exception:  # pragma: no cover - fallback for lean test environments

    @dataclass(frozen=True, slots=True)
    class Document:  # type: ignore[override]
        page_content: str
        metadata: dict[str, object]


def build_retrieval_context(topic: str, headlines: Iterable[Headline], limit: int = 5) -> list[Document]:
    scored = sorted(
        (
            (_headline_score(topic, headline), headline)
            for headline in headlines
        ),
        key=lambda item: (-item[0], normalize_headline_title(item[1].title), item[1].id),
    )
    selected = [headline for score, headline in scored if score > 0][:limit]
    if not selected:
        selected = list(headlines)[:limit]

    return [
        Document(
            page_content=headline.title,
            metadata={
                "id": headline.id,
                "source": headline.source,
                "url": headline.url,
                "published_at": headline.published_at,
            },
        )
        for headline in selected
    ]


def build_langchain_prompt(topic: str, context: Iterable[Document], joke_count: int = 10) -> str:
    if joke_count <= 0:
        raise ValueError("joke_count must be positive")

    lines = [
        f"Topic: {topic}",
        f"Return exactly {joke_count} short jokes.",
        "Use the retrieved context below.",
        "Do not explain the jokes.",
        "Context:",
    ]
    lines.extend(f"- {doc.page_content}" for doc in context)
    return "\n".join(lines)


def _headline_score(topic: str, headline: Headline) -> int:
    topic_words = set(_tokenize(topic))
    headline_words = set(_tokenize(headline.title))
    if not topic_words:
        return len(headline_words)
    return len(topic_words & headline_words)


def _tokenize(text: str) -> list[str]:
    normalized = "".join(char.lower() if char.isalnum() else " " for char in text)
    return [token for token in normalized.split() if token]

