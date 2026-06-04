from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from contextlib import closing
import os
import re
from pathlib import Path
from typing import Any

from .models import Headline, JokeCandidate
from .news_ingestion import fetch_news_headlines, resolve_news_feed_urls
from .persistence import (
    DailyRunSnapshot,
    HeadlineRecord,
    JokeRecord,
    RatingRecord,
    RunRecord,
    fetch_daily_run,
    fetch_jokes,
    fetch_leaderboard,
    fetch_score_book,
    fetch_run,
    initialize_schema,
    mark_run_complete,
    open_database,
    upsert_headlines,
    upsert_jokes,
    upsert_rating,
    upsert_run,
)
from .pinecone_store import PineconeConfig, PineconeHeadlineStore
from .ranking import normalize_headline_title
from .vector_store import HeadlineVectorStore, InMemoryHeadlineStore
from .workflow import run_daily_workflow


DashboardJson = dict[str, object]


@dataclass(slots=True)
class DashboardService:
    database_url: str | Path
    feed_urls: str | Iterable[str] | None = None
    topic: str = "daily news"
    joke_count: int = 10
    fetcher: Callable[[str], str | bytes] | None = None
    headline_store: HeadlineVectorStore | None = None
    joke_generator: Callable[[str, list[str]], list[str]] | None = None

    def __post_init__(self) -> None:
        self.feed_urls = resolve_news_feed_urls(self.feed_urls)

    def refresh_daily_run(self, *, force: bool = False) -> DashboardJson:
        with closing(open_database(self.database_url)) as connection:
            today = self._today()
            run_id = self._run_id(today)
            existing_run = fetch_run(connection, run_id)
            has_jokes = existing_run is not None and bool(fetch_jokes(connection, run_id))
            current_headlines = fetch_news_headlines(
                feed_urls=self.feed_urls,
                fetcher=self.fetcher,
            )

            if force or not has_jokes:
                return self._build_fresh_run(
                    connection,
                    run_id,
                    today,
                    headlines=current_headlines,
                )

            snapshot = self._snapshot(connection, run_id)
            if not self._stored_headlines_match(snapshot, current_headlines):
                return self._build_fresh_run(
                    connection,
                    run_id,
                    today,
                    headlines=current_headlines,
                    status_prefix="RSS feed changed; ",
                )

            score_book = fetch_score_book(connection, run_id)
            return self._serialize_snapshot(
                snapshot,
                score_book=score_book,
                status_message="Loaded the current live dashboard run.",
            )

    def current_dashboard(self) -> DashboardJson:
        return self.refresh_daily_run(force=False)

    def record_vote(self, joke_id: str, voter_id: str, rating: int) -> DashboardJson:
        normalized_rating = self._normalize_rating(rating)
        with closing(open_database(self.database_url)) as connection:
            today = self._today()
            run_id = self._run_id(today)
            existing_run = fetch_run(connection, run_id)
            if existing_run is None or not fetch_jokes(connection, run_id):
                fresh = self._build_fresh_run(connection, run_id, today)
                run_id = str(fresh["runId"])

            jokes = {joke.joke_id for joke in fetch_jokes(connection, run_id)}
            if joke_id not in jokes:
                raise KeyError(f"Unknown joke id for active run: {joke_id}")

            now = self._now()
            upsert_rating(
                connection,
                RatingRecord(
                    joke_id=joke_id,
                    voter_id=voter_id,
                    rating=normalized_rating,
                    created_at=now,
                    updated_at=now,
                ),
            )
            snapshot = self._snapshot(connection, run_id)
            score_book = fetch_score_book(connection, run_id)
            return self._serialize_snapshot(
                snapshot,
                score_book=score_book,
                status_message=f"Saved {normalized_rating} for {joke_id}.",
            )

    def _build_fresh_run(
        self,
        connection,
        run_id: str,
        today: str,
        *,
        headlines: list[Headline] | None = None,
        status_prefix: str = "",
    ) -> DashboardJson:
        headlines = headlines if headlines is not None else fetch_news_headlines(
            feed_urls=self.feed_urls,
            fetcher=self.fetcher,
        )
        if not headlines:
            raise RuntimeError("No headlines were returned from the configured RSS feeds.")

        now = self._now()
        connection.execute("DELETE FROM runs WHERE run_id = ?", (run_id,))
        connection.commit()
        upsert_run(
            connection,
            RunRecord(
                run_id=run_id,
                run_date=today,
                topic=self.topic,
                status="started",
                started_at=now,
            ),
        )

        workflow_result = run_daily_workflow(
            topic=self.topic,
            headlines=headlines,
            vote_totals={},
            generator=self._joke_generator,
            mailing_list="",
            joke_count=self.joke_count,
            headline_store=self._headline_store(),
        )

        upsert_headlines(
            connection,
            tuple(
                HeadlineRecord(
                    headline_id=headline.id,
                    run_id=run_id,
                    position=index,
                    title=headline.title,
                    normalized_title=normalize_headline_title(headline.title),
                    source=headline.source,
                    url=headline.url,
                    published_at=headline.published_at,
                    retrieval_context=headline.summary or headline.title,
                )
                for index, headline in enumerate(workflow_result.headlines)
            ),
        )
        upsert_jokes(
            connection,
            tuple(
                JokeRecord(
                    joke_id=candidate.id,
                    run_id=run_id,
                    primary_headline_id=(
                        candidate.headline_ids[0] if candidate.headline_ids else None
                    ),
                    position=index,
                    text=candidate.text,
                    created_at=candidate.created_at,
                    headline_ids=candidate.headline_ids,
                )
                for index, candidate in enumerate(workflow_result.candidates)
            ),
        )
        mark_run_complete(
            connection,
            run_id,
            completed_at=self._now(),
            winner_joke_id=workflow_result.winner.id if workflow_result.winner else None,
        )

        snapshot = self._snapshot(connection, run_id)
        score_book = fetch_score_book(connection, run_id)
        status_message = (
            f"{status_prefix}Fetched {len(workflow_result.headlines)} headlines and generated "
            f"{len(workflow_result.candidates)} jokes from live RSS."
        )
        return self._serialize_snapshot(
            snapshot,
            score_book=score_book,
            status_message=status_message,
        )

    def _snapshot(self, connection, run_id: str) -> DailyRunSnapshot:
        snapshot = fetch_daily_run(connection, run_id)
        if snapshot is None:
            raise RuntimeError(f"Dashboard run {run_id} is unavailable.")
        return snapshot

    def _stored_headlines_match(
        self,
        snapshot: DailyRunSnapshot,
        current_headlines: list[Headline],
    ) -> bool:
        stored_ids = tuple(headline.headline_id for headline in snapshot.headlines)
        current_ids = tuple(headline.id for headline in current_headlines)
        return stored_ids == current_ids

    def _serialize_snapshot(
        self,
        snapshot: DailyRunSnapshot,
        *,
        score_book: dict[str, dict[str, int]],
        status_message: str | None,
    ) -> DashboardJson:
        return {
            "runId": snapshot.run.run_id,
            "dateLabel": snapshot.run.run_date,
            "feedUrls": list(self.feed_urls),
            "topic": snapshot.run.topic,
            "statusMessage": status_message,
            "headlines": [
                {
                    "id": headline.headline_id,
                    "title": headline.title,
                    "source": headline.source,
                    "url": headline.url,
                    "publishedAt": headline.published_at,
                    "summary": headline.retrieval_context or None,
                }
                for headline in snapshot.headlines
            ],
            "jokes": [
                {
                    "id": joke.joke_id,
                    "text": joke.text,
                    "headlineIds": list(joke.headline_ids),
                    "votes": 0,
                    "createdAt": joke.created_at,
                }
                for joke in snapshot.jokes
            ],
            "initialScores": score_book,
            "leaderboard": [
                {
                    "rank": row.rank,
                    "jokeId": row.joke_id,
                    "runId": row.run_id,
                    "text": row.text,
                    "createdAt": row.created_at,
                    "score": row.score,
                    "ratingCount": row.rating_count,
                }
                for row in snapshot.leaderboard
            ],
        }

    def _headline_store(self) -> HeadlineVectorStore:
        if self.headline_store is not None:
            return self.headline_store

        api_key = os.getenv("PINECONE_API_KEY")
        if api_key:
            return PineconeHeadlineStore(
                PineconeConfig(
                    api_key=api_key,
                    index_name=os.getenv("PINECONE_INDEX_NAME", "jokerag-headlines"),
                    namespace=os.getenv("PINECONE_NAMESPACE", "daily-headlines"),
                    region=os.getenv("PINECONE_REGION", "us-east-1"),
                )
            )
        return InMemoryHeadlineStore()

    def _joke_generator(self, prompt: str, context: list[str]) -> list[str]:
        if self.joke_generator is not None:
            return self.joke_generator(prompt, context)
        return _default_joke_generator(prompt, context, self.joke_count)

    def _normalize_rating(self, rating: int) -> int:
        if not isinstance(rating, int):
            raise TypeError("rating must be an integer")
        if rating < 1 or rating > 5:
            raise ValueError("rating must be between 1 and 5")
        return rating

    @staticmethod
    def _today() -> str:
        return datetime.now(timezone.utc).date().isoformat()

    @staticmethod
    def _run_id(today: str) -> str:
        return f"run-{today}"

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
            "+00:00", "Z"
        )


def _default_joke_generator(prompt: str, context: list[str], joke_count: int) -> list[str]:
    topic = _extract_topic(prompt) or "today's news"
    headlines = [_compact_text(value) for value in context if _compact_text(value)]
    if not headlines:
        headlines = [topic]

    templates = (
        "If {headline} is the headline, the punchline has already filed a complaint.",
        "{headline} sounds like the news cycle tried stand-up and forgot the rehearsal.",
        "After {headline}, the rest of {topic} feels like a very expensive group chat.",
        "The best part of {headline} is how reality keeps writing the bit for us.",
        "{headline} is what happens when the headlines and the side quest become the same thing.",
    )
    jokes: list[str] = []
    for index in range(joke_count):
        primary = headlines[index % len(headlines)]
        secondary = headlines[(index + 1) % len(headlines)] if len(headlines) > 1 else primary
        template = templates[index % len(templates)]
        jokes.append(
            _truncate_text(
                template.format(
                    headline=primary,
                    topic=topic,
                    extra=secondary,
                ),
                180,
            )
        )
    return jokes


def _extract_topic(prompt: str) -> str:
    match = re.search(r"^Topic:\s*(.+)$", prompt, flags=re.MULTILINE)
    if match is None:
        return ""
    return match.group(1).strip()


def _compact_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split()).strip()


def _truncate_text(value: str, limit: int) -> str:
    text = _compact_text(value)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"
