from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace

from .models import Headline, JokeCandidate


def normalize_headline_title(title: str) -> str:
    return " ".join(title.split()).strip().lower()


def dedupe_headlines(headlines: Iterable[Headline]) -> list[Headline]:
    seen: set[str] = set()
    unique: list[Headline] = []
    for headline in headlines:
        key = normalize_headline_title(headline.title)
        if key in seen:
            continue
        seen.add(key)
        unique.append(headline)
    return unique


def rank_jokes(candidates: Iterable[JokeCandidate]) -> list[JokeCandidate]:
    return sorted(candidates, key=_joke_sort_key)


def pick_joke_of_the_day(candidates: Iterable[JokeCandidate]) -> JokeCandidate | None:
    ranked = rank_jokes(candidates)
    return ranked[0] if ranked else None


def apply_vote_totals(
    candidates: Iterable[JokeCandidate], totals: dict[str, int]
) -> list[JokeCandidate]:
    updated: list[JokeCandidate] = []
    for candidate in candidates:
        updated.append(replace(candidate, votes=totals.get(candidate.id, candidate.votes)))
    return updated


def _joke_sort_key(candidate: JokeCandidate) -> tuple[int, str, str]:
    return (-candidate.votes, candidate.created_at, candidate.id)

