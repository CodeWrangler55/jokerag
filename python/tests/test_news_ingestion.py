from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from contextlib import closing
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

PYTHON_ROOT = Path(__file__).resolve().parents[1]
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from jokerag_agent.news_ingestion import (
    DEFAULT_BBC_NEWS_FEED_URL,
    SQLiteHeadlineStore,
    dedupe_headlines,
    fetch_news_headlines,
    ingest_news_headlines,
    normalize_headline_text,
    parse_rss_feed,
    resolve_news_feed_urls,
)


RSS_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>BBC News</title>
    <item>
      <title>  Apple launches new headset  </title>
      <link>https://example.com/a</link>
      <pubDate>Tue, 07 Apr 2026 10:00:00 GMT</pubDate>
      <description><![CDATA[<p>  Apple unveils <strong>new</strong> headset.  </p>]]></description>
    </item>
    <item>
      <title>Apple launches new headset</title>
      <link>https://example.com/a</link>
      <pubDate>Tue, 07 Apr 2026 10:01:00 GMT</pubDate>
      <description>Duplicate item that should not be stored twice.</description>
    </item>
    <item>
      <title>Market falls on inflation worries</title>
      <link>https://example.com/b</link>
      <pubDate>Tue, 07 Apr 2026 11:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""


class NewsIngestionTests(TestCase):
    def test_resolve_news_feed_urls_defaults_to_bbc(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(resolve_news_feed_urls(), (DEFAULT_BBC_NEWS_FEED_URL,))

    def test_normalizes_and_dedupes_rss_items(self) -> None:
        headlines = parse_rss_feed(RSS_SAMPLE)

        self.assertEqual(len(headlines), 2)
        self.assertEqual(normalize_headline_text("  Apple   Launches   New Headset "), "apple launches new headset")
        self.assertEqual(headlines[0].source, "BBC News")
        self.assertEqual(headlines[0].title, "Apple launches new headset")
        self.assertEqual(headlines[0].url, "https://example.com/a")
        self.assertEqual(headlines[0].published_at, "2026-04-07T10:00:00Z")
        self.assertEqual(headlines[0].summary, "Apple unveils new headset.")
        self.assertEqual(headlines[1].title, "Market falls on inflation worries")
        self.assertIsNone(headlines[1].summary)

    def test_dedupe_headlines_is_stable(self) -> None:
        headlines = parse_rss_feed(RSS_SAMPLE)
        deduped = dedupe_headlines([*headlines, headlines[0]])

        self.assertEqual(deduped, headlines)

    def test_sqlite_store_persists_unique_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "headlines.sqlite3"
            store = SQLiteHeadlineStore(db_path)
            stored = store.store_headlines(parse_rss_feed(RSS_SAMPLE))

            self.assertEqual(len(stored), 2)
            self.assertTrue(db_path.exists())

            reopened = SQLiteHeadlineStore(db_path)
            loaded = reopened.load_headlines()

            self.assertEqual(len(loaded), 2)
            self.assertIsNone(loaded[0].summary)
            self.assertEqual(loaded[1].summary, "Apple unveils new headset.")

            with closing(sqlite3.connect(db_path)) as connection:
                row_count = connection.execute("SELECT COUNT(*) FROM headlines").fetchone()[0]

            self.assertEqual(row_count, 2)

    def test_ingest_news_headlines_uses_default_feed_and_persists(self) -> None:
        calls: list[str] = []

        def fake_fetcher(url: str) -> bytes:
            calls.append(url)
            self.assertEqual(url, DEFAULT_BBC_NEWS_FEED_URL)
            return RSS_SAMPLE.encode("utf-8")

        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "ingested.sqlite3"
            headlines = ingest_news_headlines(db_path, fetcher=fake_fetcher)
            store = SQLiteHeadlineStore(db_path)

            self.assertEqual(calls, [DEFAULT_BBC_NEWS_FEED_URL])
            self.assertEqual(len(headlines), 2)
            self.assertEqual(len(store.load_headlines()), 2)

    def test_fetch_news_headlines_accepts_explicit_feed_urls(self) -> None:
        seen: list[str] = []

        def fake_fetcher(url: str) -> bytes:
            seen.append(url)
            return RSS_SAMPLE.encode("utf-8")

        headlines = fetch_news_headlines(feed_urls=["https://example.com/news.rss"], fetcher=fake_fetcher)

        self.assertEqual(seen, ["https://example.com/news.rss"])
        self.assertEqual(len(headlines), 2)


if __name__ == "__main__":
    import unittest

    unittest.main()
