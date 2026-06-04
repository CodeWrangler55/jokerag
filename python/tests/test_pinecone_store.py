from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

PYTHON_ROOT = Path(__file__).resolve().parents[1]
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from jokerag_agent import Headline, PineconeConfig
from jokerag_agent.pinecone_store import PineconeHeadlineStore, bootstrap_pinecone_index


class FakeIndex:
    def __init__(self, response: object | None = None) -> None:
        self.response = response or {"result": {"hits": []}}
        self.upsert_calls: list[tuple[str, list[dict[str, object]]]] = []
        self.search_calls: list[dict[str, object]] = []

    def upsert_records(self, namespace: str, records: list[dict[str, object]]) -> dict[str, int]:
        self.upsert_calls.append((namespace, records))
        return {"upsertedCount": len(records)}

    def search_records(
        self,
        namespace: str,
        top_k: int,
        inputs: dict[str, object] | None = None,
        fields: list[str] | None = None,
    ) -> object:
        self.search_calls.append(
            {"namespace": namespace, "top_k": top_k, "inputs": inputs, "fields": fields}
        )
        return self.response


class PineconeStoreTests(unittest.TestCase):
    def test_bootstrap_creates_starter_safe_index(self) -> None:
        created: dict[str, object] = {}

        class FakePineconeClient:
            def __init__(self, api_key: str) -> None:
                created["api_key"] = api_key
                self._index = FakeIndex()

            def has_index(self, name: str) -> bool:
                created["has_index_name"] = name
                return False

            def create_index_for_model(self, **kwargs: object) -> None:
                created["create_index_for_model"] = kwargs

            def Index(self, name: str) -> FakeIndex:
                created["index_name"] = name
                return self._index

        fake_module = SimpleNamespace(Pinecone=FakePineconeClient)

        with patch.dict(sys.modules, {"pinecone": fake_module}):
            index = bootstrap_pinecone_index(PineconeConfig(api_key="test-key"))

        self.assertIsInstance(index, FakeIndex)
        self.assertEqual(created["api_key"], "test-key")
        self.assertEqual(created["has_index_name"], "jokerag-headlines")
        self.assertEqual(created["index_name"], "jokerag-headlines")
        self.assertEqual(created["create_index_for_model"]["cloud"], "aws")
        self.assertEqual(created["create_index_for_model"]["region"], "us-east-1")
        self.assertEqual(
            created["create_index_for_model"]["embed"],
            {"model": "llama-text-embed-v2", "field_map": {"text": "chunk_text"}},
        )

    def test_upsert_headlines_writes_compact_records(self) -> None:
        fake_index = FakeIndex()
        config = PineconeConfig(api_key="test-key")
        headline = Headline(
            id="h1",
            title="Apple launches new headset",
            source="News",
            url="https://example.com/a",
            published_at="2026-04-07T00:00:00.000Z",
        )

        with patch("jokerag_agent.pinecone_store.bootstrap_pinecone_index", return_value=fake_index):
            store = PineconeHeadlineStore(config)
            store.upsert_headlines("headsets", [headline])

        self.assertEqual(fake_index.upsert_calls[0][0], "daily-headlines")
        self.assertEqual(
            fake_index.upsert_calls[0][1][0],
            {
                "_id": "h1",
                "chunk_text": "Apple launches new headset",
                "topic": "headsets",
                "source": "News",
                "url": "https://example.com/a",
                "published_at": "2026-04-07T00:00:00.000Z",
            },
        )

    def test_search_headlines_queries_pinecone_and_formats_documents(self) -> None:
        fake_index = FakeIndex(
            response={
                "result": {
                    "hits": [
                        {
                            "_id": "h2",
                            "_score": 0.91,
                            "fields": {
                                "chunk_text": "Markets rally on calmer inflation fears",
                                "topic": "markets",
                                "source": "News",
                                "url": "https://example.com/b",
                                "published_at": "2026-04-07T00:05:00.000Z",
                            },
                        }
                    ]
                }
            }
        )
        config = PineconeConfig(api_key="test-key")

        with patch("jokerag_agent.pinecone_store.bootstrap_pinecone_index", return_value=fake_index):
            store = PineconeHeadlineStore(config)
            documents = store.search_headlines("inflation fears", limit=3)

        self.assertEqual(len(documents), 1)
        self.assertEqual(fake_index.search_calls[0]["namespace"], "daily-headlines")
        self.assertEqual(fake_index.search_calls[0]["top_k"], 3)
        self.assertEqual(fake_index.search_calls[0]["inputs"], {"text": "inflation fears"})
        self.assertEqual(
            fake_index.search_calls[0]["fields"],
            ["chunk_text", "topic", "source", "url", "published_at"],
        )
        self.assertEqual(documents[0].page_content, "Markets rally on calmer inflation fears")
        self.assertEqual(documents[0].metadata["id"], "h2")
        self.assertEqual(documents[0].metadata["score"], 0.91)
        self.assertEqual(documents[0].metadata["source"], "News")
        self.assertEqual(documents[0].metadata["topic"], "markets")


if __name__ == "__main__":
    unittest.main()
