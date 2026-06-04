from __future__ import annotations

import hashlib
import html
import os
import re
import sqlite3
import urllib.request
import xml.etree.ElementTree as ET
from contextlib import closing
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .models import Headline
from .ranking import normalize_headline_title

DEFAULT_BBC_NEWS_FEED_URL = "https://feeds.bbci.co.uk/news/rss.xml"

DEFAULT_NEWS_FEED_URLS = (DEFAULT_BBC_NEWS_FEED_URL,)

_HTML_TAG_RE = re.compile(r"<[^>]+>")


@dataclass(slots=True)
class SQLiteHeadlineStore:
    database_url: str | Path
    _database: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._database = _resolve_sqlite_database(self.database_url)
        _ensure_sqlite_parent_dir(self._database)

    def ensure_schema(self) -> None:
        with closing(sqlite3.connect(self._database)) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS headlines (
                    canonical_key TEXT PRIMARY KEY,
                    id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    source TEXT NOT NULL,
                    url TEXT NOT NULL,
                    published_at TEXT NOT NULL,
                    summary TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_headlines_published_at
                ON headlines(published_at DESC, title COLLATE NOCASE ASC, id ASC)
                """
            )
            connection.commit()

    def store_headlines(self, headlines: Iterable[Headline]) -> list[Headline]:
        unique = dedupe_headlines(headlines)
        if not unique:
            return []

        self.ensure_schema()
        with closing(sqlite3.connect(self._database)) as connection:
            connection.executemany(
                """
                INSERT INTO headlines (
                    canonical_key,
                    id,
                    title,
                    source,
                    url,
                    published_at,
                    summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(canonical_key) DO UPDATE SET
                    id = excluded.id,
                    title = excluded.title,
                    source = excluded.source,
                    url = excluded.url,
                    published_at = excluded.published_at,
                    summary = CASE
                        WHEN excluded.summary IS NOT NULL AND excluded.summary != ''
                        THEN excluded.summary
                        ELSE headlines.summary
                    END
                """,
                [
                    (
                        _headline_canonical_key(headline),
                        headline.id,
                        headline.title,
                        headline.source,
                        headline.url,
                        headline.published_at,
                        headline.summary,
                    )
                    for headline in unique
                ],
            )
            connection.commit()
        return unique

    def load_headlines(self, limit: int | None = None) -> list[Headline]:
        self.ensure_schema()
        query = [
            "SELECT id, title, source, url, published_at, summary",
            "FROM headlines",
            "ORDER BY published_at DESC, title COLLATE NOCASE ASC, id ASC",
        ]
        params: list[Any] = []
        if limit is not None:
            if limit < 0:
                raise ValueError("limit must be non-negative")
            query.append("LIMIT ?")
            params.append(limit)

        with closing(sqlite3.connect(self._database)) as connection:
            rows = connection.execute(" ".join(query), params).fetchall()

        return [
            Headline(
                id=str(row[0]),
                title=str(row[1]),
                source=str(row[2]),
                url=str(row[3]),
                published_at=str(row[4]),
                summary=None if row[5] in (None, "") else str(row[5]),
            )
            for row in rows
        ]


def resolve_news_feed_urls(feed_urls: str | Sequence[str] | None = None) -> tuple[str, ...]:
    raw_urls: Sequence[str] | None
    if feed_urls is None:
        raw_env = os.getenv("NEWS_FEED_URLS")
        raw_urls = _split_feed_urls(raw_env) if raw_env else DEFAULT_NEWS_FEED_URLS
    elif isinstance(feed_urls, str):
        raw_urls = _split_feed_urls(feed_urls)
    else:
        raw_urls = feed_urls

    normalized = tuple(
        url
        for url in (_normalize_url(url) for url in raw_urls)
        if url
    )
    return normalized or DEFAULT_NEWS_FEED_URLS


def fetch_news_headlines(
    feed_urls: str | Sequence[str] | None = None,
    fetcher: Callable[[str], str | bytes] | None = None,
) -> list[Headline]:
    resolved_urls = resolve_news_feed_urls(feed_urls)
    fetch = fetcher or _default_feed_fetcher

    headlines: list[Headline] = []
    for feed_url in resolved_urls:
        feed_payload = fetch(feed_url)
        headlines.extend(parse_rss_feed(feed_payload, feed_url=feed_url))
    return dedupe_headlines(headlines)


def ingest_news_headlines(
    database_url: str | Path,
    feed_urls: str | Sequence[str] | None = None,
    fetcher: Callable[[str], str | bytes] | None = None,
) -> list[Headline]:
    headlines = fetch_news_headlines(feed_urls=feed_urls, fetcher=fetcher)
    store = SQLiteHeadlineStore(database_url)
    store.store_headlines(headlines)
    return headlines


def parse_rss_feed(feed_payload: str | bytes, feed_url: str | None = None) -> list[Headline]:
    root = ET.fromstring(feed_payload)
    if _local_name(root.tag) == "feed":
        return _parse_atom_feed(root, feed_url=feed_url)

    channel = root.find("channel") if _local_name(root.tag) == "rss" else None
    if channel is None:
        channel = root
    source = _compact_text(_child_text(channel, "title")) or _source_from_url(feed_url)

    items: list[Headline] = []
    for item in channel.findall("item"):
        title = _compact_text(_child_text(item, "title"))
        url = _compact_text(_child_text(item, "link") or _child_text(item, "guid"))
        if not title or not url:
            continue
        published_at = _normalize_timestamp(
            _child_text(item, "pubDate")
            or _child_text(item, "published")
            or _child_text(item, "updated")
        )
        summary = _normalize_summary(
            _child_text(item, "description")
            or _child_text(item, "summary")
            or _child_text(item, "content")
        )
        items.append(
            _headline_from_parts(
                title=title,
                source=source,
                url=url,
                published_at=published_at,
                summary=summary,
            )
        )
    return dedupe_headlines(items)


def normalize_headline_text(text: str) -> str:
    return normalize_headline_title(text)


def dedupe_headlines(headlines: Iterable[Headline]) -> list[Headline]:
    seen: set[str] = set()
    unique: list[Headline] = []
    for headline in headlines:
        key = _headline_canonical_key(headline)
        if key in seen:
            continue
        seen.add(key)
        unique.append(headline)
    return unique


def _parse_atom_feed(root: ET.Element, feed_url: str | None = None) -> list[Headline]:
    source = _compact_text(_child_text(root, "title")) or _source_from_url(feed_url)
    items: list[Headline] = []
    for entry in root.findall(".//{*}entry"):
        title = _compact_text(_child_text(entry, "title"))
        if not title:
            continue
        link = _extract_atom_link(entry)
        if not link:
            continue
        published_at = _normalize_timestamp(
            _child_text(entry, "published") or _child_text(entry, "updated")
        )
        summary = _normalize_summary(
            _child_text(entry, "summary") or _child_text(entry, "content")
        )
        items.append(
            _headline_from_parts(
                title=title,
                source=source,
                url=link,
                published_at=published_at,
                summary=summary,
            )
        )
    return dedupe_headlines(items)


def _headline_from_parts(
    title: str,
    source: str,
    url: str,
    published_at: str,
    summary: str | None,
) -> Headline:
    normalized_title = normalize_headline_text(title)
    normalized_source = _compact_text(source) or "News"
    normalized_url = _compact_text(url)
    canonical_key = "|".join(
        (
            normalized_source.lower(),
            normalized_title,
            normalized_url,
        )
    )
    headline_id = hashlib.sha256(canonical_key.encode("utf-8")).hexdigest()
    return Headline(
        id=headline_id,
        title=_compact_text(title),
        source=normalized_source,
        url=normalized_url,
        published_at=published_at,
        summary=summary,
    )


def _headline_canonical_key(headline: Headline) -> str:
    return "|".join(
        (
            _compact_text(headline.source).lower(),
            normalize_headline_text(headline.title),
            _compact_text(headline.url),
        )
    )


def _default_feed_fetcher(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "jokerag-agent/1.0 (+https://example.com)",
            "Accept": "application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.1",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read()


def _resolve_sqlite_database(database_url: str | Path) -> str:
    if isinstance(database_url, Path):
        return str(database_url)

    text = str(database_url).strip()
    if text in {":memory:", "sqlite::memory:"}:
        return ":memory:"
    if text.startswith("sqlite:///"):
        return text.removeprefix("sqlite:///")
    if text.startswith("sqlite:"):
        return text.removeprefix("sqlite:")
    return text


def _split_feed_urls(raw_urls: str | None) -> tuple[str, ...]:
    if not raw_urls:
        return ()
    parts = re.split(r"[\n,]+", raw_urls)
    return tuple(part.strip() for part in parts if part.strip())


def _normalize_url(url: str) -> str:
    return _compact_text(url)


def _normalize_timestamp(raw_value: str | None) -> str:
    value = _compact_text(raw_value or "")
    if not value:
        return ""

    parsed: datetime | None = None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        parsed = None

    if parsed is None:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def _normalize_summary(raw_value: str | None) -> str | None:
    summary = _strip_html(raw_value or "")
    compact = _compact_text(summary)
    if not compact:
        return None
    if len(compact) <= 280:
        return compact
    return compact[:277].rstrip() + "..."


def _strip_html(value: str) -> str:
    return html.unescape(_HTML_TAG_RE.sub(" ", value))


def _compact_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split()).strip()


def _child_text(element: ET.Element, name: str) -> str | None:
    for child in list(element):
        if _local_name(child.tag) == name and child.text:
            return child.text
    return element.findtext(name)


def _extract_atom_link(entry: ET.Element) -> str | None:
    for child in list(entry):
        if _local_name(child.tag) != "link":
            continue
        href = child.attrib.get("href")
        if href:
            return href
        if child.text:
            return child.text
    return None


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def _source_from_url(feed_url: str | None) -> str:
    if not feed_url:
        return "News"
    host = urlparse(feed_url).netloc
    return host or "News"


def _ensure_sqlite_parent_dir(database: str) -> None:
    if database in {":memory:"}:
        return
    path = Path(database)
    if path.parent == Path("."):
        return
    path.parent.mkdir(parents=True, exist_ok=True)
