from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PYTHON_ROOT = Path(__file__).resolve().parents[1]
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from jokerag_agent.dashboard_service import DashboardService
from jokerag_agent.persistence import fetch_daily_run, fetch_score_book, open_database
from jokerag_agent.vector_store import InMemoryHeadlineStore


class DashboardServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / "jokerag.sqlite3"

        self.feed_payload = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
          <channel>
            <title>BBC News</title>
            <item>
              <title>Mayor unveils glitter bike lane</title>
              <link>https://example.com/news/1</link>
              <pubDate>Mon, 06 May 2026 08:00:00 GMT</pubDate>
              <description>The mayor promised the lane would sparkle in any weather.</description>
            </item>
            <item>
              <title>Scientists confirm ducks can negotiate</title>
              <link>https://example.com/news/2</link>
              <pubDate>Mon, 06 May 2026 08:05:00 GMT</pubDate>
              <description>Researchers say the ducks kept asking for better bread crumbs.</description>
            </item>
          </channel>
        </rss>
        """

        def fetcher(_: str) -> str:
            return self.feed_payload

        def joke_generator(prompt: str, context: list[str]) -> list[str]:
            self.assertIn("Comedian Agent", prompt)
            return [
                f"Joke {index + 1}: {context[index % len(context)]}"
                for index in range(10)
            ]

        self.service = DashboardService(
            database_url=self.db_path,
            feed_urls=("https://feeds.bbci.co.uk/news/rss.xml",),
            fetcher=fetcher,
            headline_store=InMemoryHeadlineStore(),
            joke_generator=joke_generator,
        )

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_refresh_daily_run_persists_live_headlines_and_jokes(self) -> None:
        payload = self.service.refresh_daily_run(force=True)

        self.assertEqual(payload["dateLabel"], self.service._today())
        self.assertEqual(
            payload["feedUrls"],
            ["https://feeds.bbci.co.uk/news/rss.xml"],
        )
        self.assertEqual(len(payload["headlines"]), 2)
        self.assertEqual(len(payload["jokes"]), 10)
        self.assertEqual(payload["initialScores"], {})
        self.assertIn("Fetched 2 headlines", payload["statusMessage"])

        connection = open_database(self.db_path)
        run_id = payload["runId"]
        snapshot = fetch_daily_run(connection, run_id)
        self.assertIsNotNone(snapshot)
        self.assertEqual(len(snapshot.headlines), 2)
        self.assertEqual(len(snapshot.jokes), 10)
        self.assertEqual(fetch_score_book(connection, run_id), {})
        connection.close()

    def test_record_vote_updates_the_active_run(self) -> None:
        payload = self.service.refresh_daily_run(force=True)
        voted = self.service.record_vote("joke-1", "anon-123", 5)

        self.assertEqual(voted["initialScores"]["joke-1"]["anon-123"], 5)
        self.assertIn("Saved 5", voted["statusMessage"])

        connection = open_database(self.db_path)
        self.assertEqual(
            fetch_score_book(connection, payload["runId"]),
            {"joke-1": {"anon-123": 5}},
        )
        connection.close()

    def test_current_dashboard_regenerates_when_feed_headlines_change(self) -> None:
        self.service.refresh_daily_run(force=True)
        self.service.record_vote("joke-1", "anon-123", 5)

        self.feed_payload = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
          <channel>
            <title>BBC News</title>
            <item>
              <title>New budget plan reaches parliament</title>
              <link>https://example.com/news/3</link>
              <pubDate>Tue, 07 May 2026 09:00:00 GMT</pubDate>
              <description>The proposal became the top story.</description>
            </item>
          </channel>
        </rss>
        """

        refreshed = self.service.current_dashboard()

        self.assertIn("RSS feed changed", refreshed["statusMessage"])
        self.assertEqual(len(refreshed["headlines"]), 1)
        self.assertEqual(
            refreshed["headlines"][0]["title"],
            "New budget plan reaches parliament",
        )
        self.assertIn("New budget plan reaches parliament", refreshed["jokes"][0]["text"])
        self.assertEqual(refreshed["initialScores"], {})


if __name__ == "__main__":
    unittest.main()
