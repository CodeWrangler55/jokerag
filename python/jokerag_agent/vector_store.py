from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from .models import Headline
from .rag import Document, build_retrieval_context


class HeadlineVectorStore(Protocol):
    def upsert_headlines(self, topic: str, headlines: Iterable[Headline]) -> None: ...

    def search_headlines(self, topic: str, limit: int = 5) -> list[Document]: ...


@dataclass(slots=True)
class InMemoryHeadlineStore:
    """Local fallback for tests and offline development."""

    headlines: tuple[Headline, ...] = ()

    def upsert_headlines(self, topic: str, headlines: Iterable[Headline]) -> None:
        del topic
        self.headlines = tuple(headlines)

    def search_headlines(self, topic: str, limit: int = 5) -> list[Document]:
        return build_retrieval_context(topic, self.headlines, limit=limit)
