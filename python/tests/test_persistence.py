from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PYTHON_ROOT = Path(__file__).resolve().parents[1]
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from jokerag_agent.persistence import (
    DailyRunSnapshot,
    HeadlineRecord,
    JokeRecord,
    RatingRecord,
    RunRecord,
    fetch_daily_run,
    fetch_leaderboard,
    fetch_rating,
    open_database,
    mark_run_complete,
    upsert_headlines,
    upsert_jokes,
    upsert_rating,
    upsert_run,
)


class PersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / "jokerag.sqlite3"
        self.connection = open_database(self.db_path)
        self.run = RunRecord(
            run_id="run-2026-05-06",
            run_date="2026-05-06",
            topic="headsets",
            status="started",
            started_at="2026-05-06T08:00:00Z",
        )
        upsert_run(self.connection, self.run)

        self.headlines = (
            HeadlineRecord(
                headline_id="headline-1",
                run_id=self.run.run_id,
                position=0,
                title="Apple launches a new headset",
                normalized_title="apple launches a new headset",
                source="Example News",
                url="https://example.com/1",
                published_at="2026-05-06T07:00:00Z",
                retrieval_context="Apple launched a new headset this morning.",
            ),
            HeadlineRecord(
                headline_id="headline-2",
                run_id=self.run.run_id,
                position=1,
                title="Market reacts to headset release",
                normalized_title="market reacts to headset release",
                source="Example News",
                url="https://example.com/2",
                published_at="2026-05-06T07:05:00Z",
                retrieval_context="Investors reacted to the headset launch.",
            ),
        )
        upsert_headlines(self.connection, self.headlines)

        self.jokes = (
            JokeRecord(
                joke_id="joke-1",
                run_id=self.run.run_id,
                primary_headline_id="headline-1",
                position=0,
                text="The new headset is so immersive, even the news cycle needed a reset.",
                created_at="2026-05-06T08:05:00Z",
                headline_ids=("headline-1", "headline-2"),
            ),
            JokeRecord(
                joke_id="joke-2",
                run_id=self.run.run_id,
                primary_headline_id="headline-2",
                position=1,
                text="Markets saw the headset and decided it was the next big headset.",
                created_at="2026-05-06T08:10:00Z",
                headline_ids=("headline-2",),
            ),
            JokeRecord(
                joke_id="joke-3",
                run_id=self.run.run_id,
                primary_headline_id="headline-1",
                position=2,
                text="Someone asked for mixed reality; the headline said mixed reactions.",
                created_at="2026-05-06T08:15:00Z",
                headline_ids=("headline-1",),
            ),
        )
        upsert_jokes(self.connection, self.jokes)

    def tearDown(self) -> None:
        self.connection.close()
        self.tempdir.cleanup()

    def test_rating_upsert_is_idempotent_per_voter_and_joke(self) -> None:
        first = RatingRecord(
            joke_id="joke-1",
            voter_id="voter-1",
            rating=2,
            created_at="2026-05-06T09:00:00Z",
            updated_at="2026-05-06T09:00:00Z",
        )
        second = RatingRecord(
            joke_id="joke-1",
            voter_id="voter-1",
            rating=5,
            created_at="2026-05-06T09:00:00Z",
            updated_at="2026-05-06T09:05:00Z",
        )
        upsert_rating(self.connection, first)
        upsert_rating(self.connection, second)

        self.assertEqual(
            self.connection.execute("SELECT COUNT(*) FROM ratings").fetchone()[0],
            1,
        )
        stored = fetch_rating(self.connection, "joke-1", "voter-1")
        self.assertIsNotNone(stored)
        self.assertEqual(stored.rating, 5)
        self.assertEqual(stored.created_at, "2026-05-06T09:00:00Z")
        self.assertEqual(stored.updated_at, "2026-05-06T09:05:00Z")

    def test_leaderboard_uses_deterministic_tiebreakers(self) -> None:
        upsert_rating(
            self.connection,
            RatingRecord(
                joke_id="joke-1",
                voter_id="voter-a",
                rating=4,
                created_at="2026-05-06T09:10:00Z",
                updated_at="2026-05-06T09:10:00Z",
            ),
        )
        upsert_rating(
            self.connection,
            RatingRecord(
                joke_id="joke-2",
                voter_id="voter-a",
                rating=2,
                created_at="2026-05-06T09:10:00Z",
                updated_at="2026-05-06T09:10:00Z",
            ),
        )
        upsert_rating(
            self.connection,
            RatingRecord(
                joke_id="joke-2",
                voter_id="voter-b",
                rating=2,
                created_at="2026-05-06T09:11:00Z",
                updated_at="2026-05-06T09:11:00Z",
            ),
        )
        upsert_rating(
            self.connection,
            RatingRecord(
                joke_id="joke-3",
                voter_id="voter-a",
                rating=1,
                created_at="2026-05-06T09:12:00Z",
                updated_at="2026-05-06T09:12:00Z",
            ),
        )
        leaderboard = fetch_leaderboard(self.connection, self.run.run_id)

        self.assertEqual([row.joke_id for row in leaderboard], ["joke-1", "joke-2", "joke-3"])
        self.assertEqual([row.score for row in leaderboard], [4, 4, 1])
        self.assertEqual(leaderboard[0].rank, 1)
        self.assertEqual(leaderboard[1].rank, 2)

    def test_daily_run_snapshot_includes_related_records(self) -> None:
        upsert_rating(
            self.connection,
            RatingRecord(
                joke_id="joke-1",
                voter_id="voter-a",
                rating=3,
                created_at="2026-05-06T09:10:00Z",
                updated_at="2026-05-06T09:10:00Z",
            ),
        )
        upsert_rating(
            self.connection,
            RatingRecord(
                joke_id="joke-2",
                voter_id="voter-a",
                rating=5,
                created_at="2026-05-06T09:11:00Z",
                updated_at="2026-05-06T09:11:00Z",
            ),
        )
        mark_run_complete(
            self.connection,
            self.run.run_id,
            completed_at="2026-05-06T10:00:00Z",
            winner_joke_id="joke-2",
        )
        snapshot = fetch_daily_run(self.connection, self.run.run_id)

        self.assertIsInstance(snapshot, DailyRunSnapshot)
        self.assertEqual(snapshot.run.status, "completed")
        self.assertEqual(snapshot.run.winner_joke_id, "joke-2")
        self.assertEqual([headline.headline_id for headline in snapshot.headlines], ["headline-1", "headline-2"])
        self.assertEqual([joke.headline_ids for joke in snapshot.jokes], [("headline-1", "headline-2"), ("headline-2",), ("headline-1",)])
        self.assertEqual([row.joke_id for row in snapshot.leaderboard], ["joke-2", "joke-1", "joke-3"])
        self.assertEqual([row.score for row in snapshot.leaderboard], [5, 3, 0])


if __name__ == "__main__":
    unittest.main()
