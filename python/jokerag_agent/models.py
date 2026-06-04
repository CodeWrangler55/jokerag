from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True, slots=True)
class Headline:
    id: str
    title: str
    source: str
    url: str
    published_at: str
    summary: str | None = None


@dataclass(frozen=True, slots=True)
class JokeCandidate:
    id: str
    text: str
    headline_ids: tuple[str, ...]
    votes: int
    created_at: str


@dataclass(frozen=True, slots=True)
class JokeRunResult:
    topic: str
    brief: str
    retrieval_context: tuple[str, ...]
    candidates: tuple[JokeCandidate, ...]
    winner: JokeCandidate | None
    zapier_payload: dict[str, object]
    headlines: tuple[Headline, ...]
    votes: tuple[tuple[str, int], ...]

    @property
    def winner_text(self) -> str | None:
        return None if self.winner is None else self.winner.text

    @property
    def candidate_ids(self) -> Sequence[str]:
        return tuple(candidate.id for candidate in self.candidates)
