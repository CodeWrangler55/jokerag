from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

PYTHON_ROOT = Path(__file__).resolve().parents[1]
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from jokerag_agent import (
    Headline,
    JokeCandidate,
    PineconeConfig,
    build_crewai_plan,
    build_langchain_prompt,
    build_retrieval_context,
    build_zapier_email_payload,
    build_zapier_webhook_payload,
    dedupe_headlines,
    pick_joke_of_the_day,
    rank_jokes,
    run_daily_workflow,
)
from jokerag_agent.pinecone_store import bootstrap_pinecone_index
from jokerag_agent.vector_store import InMemoryHeadlineStore


class WorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.headlines = [
            Headline(
                id="h1",
                title="Apple launches new headset",
                source="News",
                url="https://example.com/a",
                published_at="2026-04-07T00:00:00.000Z",
            ),
            Headline(
                id="h2",
                title=" Apple launches new headset ",
                source="Alt",
                url="https://example.com/b",
                published_at="2026-04-07T00:01:00.000Z",
            ),
            Headline(
                id="h3",
                title="Market falls on inflation worries",
                source="News",
                url="https://example.com/c",
                published_at="2026-04-07T00:02:00.000Z",
            ),
        ]

    def test_dedupes_headlines(self) -> None:
        self.assertEqual(len(dedupe_headlines(self.headlines)), 2)

    def test_builds_langchain_prompt_from_retrieval_context(self) -> None:
        context = build_retrieval_context("headsets", self.headlines)
        prompt = build_langchain_prompt("headsets", context, joke_count=10)
        self.assertIn("Topic: headsets", prompt)
        self.assertIn("Apple launches new headset", prompt)

    def test_crewai_plan_contains_three_roles(self) -> None:
        context = build_retrieval_context("headsets", self.headlines)
        plan = build_crewai_plan("headsets", context)
        self.assertIn("roles", plan)
        self.assertEqual(len(plan["roles"]), 3)

    def test_rank_and_pick_winner(self) -> None:
        candidates = [
            JokeCandidate(
                id="j2",
                text="Second joke",
                headline_ids=("h1",),
                votes=3,
                created_at="2026-04-07T10:01:00.000Z",
            ),
            JokeCandidate(
                id="j1",
                text="First joke",
                headline_ids=("h2",),
                votes=3,
                created_at="2026-04-07T10:00:00.000Z",
            ),
        ]
        self.assertEqual(rank_jokes(candidates)[0].id, "j1")
        self.assertEqual(pick_joke_of_the_day(candidates).id, "j1")

    def test_zapier_payloads_are_structured(self) -> None:
        winner = JokeCandidate(
            id="j1",
            text="Winning joke",
            headline_ids=("h1",),
            votes=9,
            created_at="2026-04-07T10:00:00.000Z",
        )
        webhook_payload = build_zapier_webhook_payload(
            topic="headsets",
            winner=winner,
            headlines=self.headlines[:1],
            mailing_list="laughs@example.com",
        )
        email_payload = build_zapier_email_payload(
            topic="headsets",
            winner=winner,
            headlines=self.headlines[:1],
            mailing_list="laughs@example.com",
        )
        self.assertEqual(webhook_payload["winner"]["text"], "Winning joke")
        self.assertEqual(email_payload["subject"], "Joke of the Day: headsets")

    def test_daily_workflow_runs_end_to_end(self) -> None:
        def generator(prompt: str, context: list[str]) -> list[str]:
            self.assertIn("Topic: headsets", prompt)
            self.assertTrue(context)
            return [
                "Joke 1",
                "Joke 2",
                "Joke 3",
                "Joke 4",
                "Joke 5",
                "Joke 6",
                "Joke 7",
                "Joke 8",
                "Joke 9",
                "Joke 10",
            ]

        result = run_daily_workflow(
            topic="headsets",
            headlines=self.headlines,
            vote_totals={"joke-1": 10, "joke-2": 8},
            generator=generator,
            mailing_list="laughs@example.com",
            headline_store=InMemoryHeadlineStore(),
        )
        self.assertEqual(result.winner_text, "Joke 1")
        self.assertEqual(
            result.zapier_payload["email"]["subject"], "Joke of the Day: headsets"
        )

    def test_bootstrap_pinecone_index_uses_starter_defaults(self) -> None:
        created: dict[str, object] = {}

        class FakeIndex:
            def __init__(self) -> None:
                self.records: list[tuple[str, object]] = []

        class FakePineconeClient:
            def __init__(self, api_key: str) -> None:
                self.api_key = api_key
                self.index = FakeIndex()

            def has_index(self, name: str) -> bool:
                created["has_index_name"] = name
                return False

            def create_index_for_model(self, **kwargs: object) -> None:
                created["create_index_for_model"] = kwargs

            def Index(self, name: str) -> FakeIndex:
                created["index_name"] = name
                return self.index

        fake_module = SimpleNamespace(Pinecone=FakePineconeClient)
        config = PineconeConfig(api_key="test-key")

        with patch.dict(sys.modules, {"pinecone": fake_module}):
            index = bootstrap_pinecone_index(config)

        self.assertIsInstance(index, FakeIndex)
        self.assertEqual(created["has_index_name"], "jokerag-headlines")
        self.assertEqual(created["index_name"], "jokerag-headlines")
        self.assertEqual(created["create_index_for_model"]["cloud"], "aws")
        self.assertEqual(created["create_index_for_model"]["region"], "us-east-1")
        self.assertEqual(
            created["create_index_for_model"]["embed"],
            {"model": "llama-text-embed-v2", "field_map": {"text": "chunk_text"}},
        )


if __name__ == "__main__":
    unittest.main()
