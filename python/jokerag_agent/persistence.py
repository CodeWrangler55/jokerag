from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import sqlite3
from typing import Any


@dataclass(frozen=True, slots=True)
class RunRecord:
    run_id: str
    run_date: str
    topic: str
    status: str
    started_at: str
    completed_at: str | None = None
    winner_joke_id: str | None = None


@dataclass(frozen=True, slots=True)
class HeadlineRecord:
    headline_id: str
    run_id: str
    position: int
    title: str
    normalized_title: str
    source: str
    url: str
    published_at: str
    retrieval_context: str = ""


@dataclass(frozen=True, slots=True)
class JokeRecord:
    joke_id: str
    run_id: str
    primary_headline_id: str | None
    position: int
    text: str
    created_at: str
    headline_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RatingRecord:
    joke_id: str
    voter_id: str
    rating: int
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class LeaderboardRow:
    rank: int
    joke_id: str
    run_id: str
    text: str
    created_at: str
    score: int
    rating_count: int


@dataclass(frozen=True, slots=True)
class DailyRunSnapshot:
    run: RunRecord
    headlines: tuple[HeadlineRecord, ...]
    jokes: tuple[JokeRecord, ...]
    leaderboard: tuple[LeaderboardRow, ...]


@lru_cache(maxsize=1)
def _schema_sql() -> str:
    return Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")


def open_database(path: str | Path) -> sqlite3.Connection:
    resolved = Path(path)
    if resolved.parent != Path("."):
        resolved.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(resolved))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    initialize_schema(connection)
    return connection


def initialize_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(_schema_sql())
    connection.commit()


def upsert_run(connection: sqlite3.Connection, run: RunRecord) -> None:
    connection.execute(
        """
        INSERT INTO runs (
          run_id, run_date, topic, status, started_at, completed_at, winner_joke_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(run_id) DO UPDATE SET
          run_date = excluded.run_date,
          topic = excluded.topic,
          status = excluded.status,
          started_at = excluded.started_at,
          completed_at = excluded.completed_at,
          winner_joke_id = excluded.winner_joke_id
        """,
        (
            run.run_id,
            run.run_date,
            run.topic,
            run.status,
            run.started_at,
            run.completed_at,
            run.winner_joke_id,
        ),
    )
    connection.commit()


def mark_run_complete(
    connection: sqlite3.Connection,
    run_id: str,
    *,
    completed_at: str,
    winner_joke_id: str | None,
    status: str = "completed",
) -> None:
    connection.execute(
        """
        UPDATE runs
        SET status = ?, completed_at = ?, winner_joke_id = ?
        WHERE run_id = ?
        """,
        (status, completed_at, winner_joke_id, run_id),
    )
    connection.commit()


def upsert_headlines(
    connection: sqlite3.Connection, headlines: Iterable[HeadlineRecord]
) -> None:
    for headline in headlines:
        connection.execute(
            """
            INSERT INTO headlines (
              headline_id,
              run_id,
              position,
              title,
              normalized_title,
              source,
              url,
              published_at,
              retrieval_context
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(headline_id) DO UPDATE SET
              run_id = excluded.run_id,
              position = excluded.position,
              title = excluded.title,
              normalized_title = excluded.normalized_title,
              source = excluded.source,
              url = excluded.url,
              published_at = excluded.published_at,
              retrieval_context = excluded.retrieval_context
            """,
            (
                headline.headline_id,
                headline.run_id,
                headline.position,
                headline.title,
                headline.normalized_title,
                headline.source,
                headline.url,
                headline.published_at,
                headline.retrieval_context,
            ),
        )
    connection.commit()


def upsert_jokes(connection: sqlite3.Connection, jokes: Iterable[JokeRecord]) -> None:
    for joke in jokes:
        connection.execute(
            """
            INSERT INTO jokes (
              joke_id,
              run_id,
              primary_headline_id,
              position,
              text,
              created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(joke_id) DO UPDATE SET
              run_id = excluded.run_id,
              primary_headline_id = excluded.primary_headline_id,
              position = excluded.position,
              text = excluded.text,
              created_at = excluded.created_at
            """,
            (
                joke.joke_id,
                joke.run_id,
                joke.primary_headline_id,
                joke.position,
                joke.text,
                joke.created_at,
            ),
        )
        connection.execute("DELETE FROM joke_headlines WHERE joke_id = ?", (joke.joke_id,))
        for index, headline_id in enumerate(joke.headline_ids):
            connection.execute(
                """
                INSERT INTO joke_headlines (joke_id, headline_id, position)
                VALUES (?, ?, ?)
                """,
                (joke.joke_id, headline_id, index),
            )
    connection.commit()


def upsert_rating(connection: sqlite3.Connection, rating: RatingRecord) -> None:
    rating_value = _require_integer(rating.rating, "rating")
    connection.execute(
        """
        INSERT INTO ratings (
          joke_id,
          voter_id,
          rating,
          created_at,
          updated_at
        ) VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(joke_id, voter_id) DO UPDATE SET
          rating = excluded.rating,
          updated_at = excluded.updated_at
        """,
        (
            rating.joke_id,
            rating.voter_id,
            rating_value,
            rating.created_at,
            rating.updated_at,
        ),
    )
    connection.commit()


def fetch_run(connection: sqlite3.Connection, run_id: str) -> RunRecord | None:
    row = connection.execute(
        """
        SELECT run_id, run_date, topic, status, started_at, completed_at, winner_joke_id
        FROM runs
        WHERE run_id = ?
        """,
        (run_id,),
    ).fetchone()
    if row is None:
        return None
    return _run_from_row(row)


def fetch_headlines(
    connection: sqlite3.Connection, run_id: str
) -> tuple[HeadlineRecord, ...]:
    rows = connection.execute(
        """
        SELECT
          headline_id,
          run_id,
          position,
          title,
          normalized_title,
          source,
          url,
          published_at,
          retrieval_context
        FROM headlines
        WHERE run_id = ?
        ORDER BY position ASC, headline_id ASC
        """,
        (run_id,),
    ).fetchall()
    return tuple(_headline_from_row(row) for row in rows)


def fetch_jokes(connection: sqlite3.Connection, run_id: str) -> tuple[JokeRecord, ...]:
    rows = connection.execute(
        """
        SELECT
          joke_id,
          run_id,
          primary_headline_id,
          position,
          text,
          created_at
        FROM jokes
        WHERE run_id = ?
        ORDER BY position ASC, joke_id ASC
        """,
        (run_id,),
    ).fetchall()

    jokes: list[JokeRecord] = []
    for row in rows:
        headline_ids = connection.execute(
            """
            SELECT headline_id
            FROM joke_headlines
            WHERE joke_id = ?
            ORDER BY position ASC, headline_id ASC
            """,
            (row["joke_id"],),
        ).fetchall()
        jokes.append(
            JokeRecord(
                joke_id=row["joke_id"],
                run_id=row["run_id"],
                primary_headline_id=row["primary_headline_id"],
                position=row["position"],
                text=row["text"],
                created_at=row["created_at"],
                headline_ids=tuple(entry["headline_id"] for entry in headline_ids),
            )
        )
    return tuple(jokes)


def fetch_rating(
    connection: sqlite3.Connection, joke_id: str, voter_id: str
) -> RatingRecord | None:
    row = connection.execute(
        """
        SELECT joke_id, voter_id, rating, created_at, updated_at
        FROM ratings
        WHERE joke_id = ? AND voter_id = ?
        """,
        (joke_id, voter_id),
    ).fetchone()
    if row is None:
        return None
    return RatingRecord(
        joke_id=row["joke_id"],
        voter_id=row["voter_id"],
        rating=row["rating"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def fetch_leaderboard(
    connection: sqlite3.Connection, run_id: str
) -> tuple[LeaderboardRow, ...]:
    rows = connection.execute(
        """
        SELECT
          j.joke_id,
          j.run_id,
          j.text,
          j.created_at,
          COALESCE(SUM(r.rating), 0) AS score,
          COUNT(r.joke_id) AS rating_count
        FROM jokes AS j
        LEFT JOIN ratings AS r ON r.joke_id = j.joke_id
        WHERE j.run_id = ?
        GROUP BY j.joke_id, j.run_id, j.text, j.created_at
        ORDER BY score DESC, j.created_at ASC, j.joke_id ASC
        """,
        (run_id,),
    ).fetchall()

    leaderboard = [
        LeaderboardRow(
            rank=index,
            joke_id=row["joke_id"],
            run_id=row["run_id"],
            text=row["text"],
            created_at=row["created_at"],
            score=row["score"],
            rating_count=row["rating_count"],
        )
        for index, row in enumerate(rows, start=1)
    ]
    return tuple(leaderboard)


def fetch_score_book(connection: sqlite3.Connection, run_id: str) -> dict[str, dict[str, int]]:
    rows = connection.execute(
        """
        SELECT
          r.joke_id,
          r.voter_id,
          r.rating
        FROM ratings AS r
        INNER JOIN jokes AS j ON j.joke_id = r.joke_id
        WHERE j.run_id = ?
        ORDER BY r.joke_id ASC, r.voter_id ASC
        """,
        (run_id,),
    ).fetchall()

    score_book: dict[str, dict[str, int]] = {}
    for row in rows:
        joke_id = row["joke_id"]
        voter_id = row["voter_id"]
        rating = row["rating"]
        bucket = score_book.setdefault(str(joke_id), {})
        bucket[str(voter_id)] = int(rating)

    return score_book


def fetch_daily_run(
    connection: sqlite3.Connection, run_id: str
) -> DailyRunSnapshot | None:
    run = fetch_run(connection, run_id)
    if run is None:
        return None
    headlines = fetch_headlines(connection, run_id)
    jokes = fetch_jokes(connection, run_id)
    leaderboard = fetch_leaderboard(connection, run_id)
    return DailyRunSnapshot(
        run=run,
        headlines=headlines,
        jokes=jokes,
        leaderboard=leaderboard,
    )


def _run_from_row(row: sqlite3.Row) -> RunRecord:
    return RunRecord(
        run_id=row["run_id"],
        run_date=row["run_date"],
        topic=row["topic"],
        status=row["status"],
        started_at=row["started_at"],
        completed_at=row["completed_at"],
        winner_joke_id=row["winner_joke_id"],
    )


def _headline_from_row(row: sqlite3.Row) -> HeadlineRecord:
    return HeadlineRecord(
        headline_id=row["headline_id"],
        run_id=row["run_id"],
        position=row["position"],
        title=row["title"],
        normalized_title=row["normalized_title"],
        source=row["source"],
        url=row["url"],
        published_at=row["published_at"],
        retrieval_context=row["retrieval_context"],
    )


def _require_integer(value: Any, field_name: str) -> int:
    if not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")
    return value
