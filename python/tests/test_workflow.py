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
    build_langchain_rag_prompt_chain,
    build_retrieval_context,
    build_zapier_email_payload,
    build_zapier_webhook_payload,
    dedupe_headlines,
    pick_joke_of_the_day,
    rank_jokes,
    run_daily_workflow,
)
from jokerag_agent.agents import (
    build_comedian_prompt,
    build_editor_prompt,
    build_research_summary_prompt,
)
from jokerag_agent.pinecone_store import bootstrap_pinecone_index
from jokerag_agent.vector_store import InMemoryHeadlineStore


class StaleSearchStore:
    def __init__(self) -> None:
        self.queries: list[str] = []
        self.upserted: list[Headline] = []

    def upsert_headlines(self, topic: str, headlines: list[Headline]) -> None:
        del topic
        self.upserted = list(headlines)

    def search_headlines(self, topic: str, limit: int = 5):
        self.queries.append(topic)
        del limit
        return build_retrieval_context(
            "old headline",
            [
                Headline(
                    id="old",
                    title="Old stored headline",
                    source="Archive",
                    url="https://example.com/old",
                    published_at="2026-04-01T00:00:00.000Z",
                )
            ],
        )


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
        self.assertIn("System:", prompt)
        self.assertIn("Human:", prompt)

    def test_langchain_rag_prompt_chain_is_invokable(self) -> None:
        context = build_retrieval_context("headsets", self.headlines)
        chain = build_langchain_rag_prompt_chain()
        prompt = chain.invoke(
            {
                "topic": "headsets",
                "context": context,
                "joke_count": 10,
            }
        )

        self.assertIn("Topic: headsets", prompt)
        self.assertIn("Apple launches new headset", prompt)

    def test_crewai_plan_contains_three_roles(self) -> None:
        context = build_retrieval_context("headsets", self.headlines)
        plan = build_crewai_plan("headsets", context, research_summary="headline summary")
        self.assertIn("roles", plan)
        self.assertEqual(len(plan["roles"]), 3)
        self.assertIn("prompts", plan)
        self.assertIn("Research Agent", plan["prompts"]["research"])
        self.assertIn("headline summary", plan["prompts"]["comedian"])

    def test_prompt_assembly_includes_lineage_and_editor_scope(self) -> None:
        context = build_retrieval_context("headsets", self.headlines)
        research_prompt = build_research_summary_prompt("headsets", context, joke_count=10)
        comedian_prompt = build_comedian_prompt(
            "headsets",
            context,
            "Apple headset story angle",
            joke_count=10,
        )
        editor_prompt = build_editor_prompt(
            "headsets",
            [
                JokeCandidate(
                    id="j1",
                    text="Draft joke",
                    headline_ids=("h1",),
                    votes=0,
                    created_at="2026-04-07T00:00:00.000Z",
                )
            ],
            "Apple headset story angle",
        )
        self.assertIn("Research Agent", research_prompt)
        self.assertIn("Apple headset story angle", comedian_prompt)
        self.assertIn("Editor Agent", editor_prompt)
        self.assertIn("sources: h1", editor_prompt)

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

    def test_daily_workflow_runs_end_to_end_with_fake_adapters(self) -> None:
        seen: dict[str, object] = {}

        def researcher(prompt: str, context: list[str]) -> str:
            seen["research_prompt"] = prompt
            seen["research_context"] = tuple(context)
            self.assertIn("Research Agent", prompt)
            return "Apple headset launch is the strongest angle."

        def generator(prompt: str, context: list[str]) -> list[str]:
            seen["comedian_prompt"] = prompt
            seen["comedian_context"] = tuple(context)
            self.assertIn("Apple headset launch is the strongest angle.", prompt)
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
                "bad joke that should be rejected",
            ]

        def editor(prompt: str, drafts: list[dict[str, object]]) -> list[dict[str, object]]:
            seen["editor_prompt"] = prompt
            seen["editor_drafts"] = tuple(drafts)
            self.assertIn("Editor Agent", prompt)
            refined = []
            for draft in drafts:
                if draft["text"] == "bad joke that should be rejected":
                    continue
                if draft["id"] == "joke-1":
                    draft = dict(draft)
                    draft["text"] = "Joke 1, tightened"
                refined.append(draft)
            return refined

        result = run_daily_workflow(
            topic="headsets",
            headlines=self.headlines,
            vote_totals={"joke-1": 10, "joke-2": 8},
            generator=generator,
            mailing_list="laughs@example.com",
            headline_store=InMemoryHeadlineStore(),
            researcher=researcher,
            editor=editor,
        )
        self.assertEqual(result.winner_text, "Joke 1, tightened")
        self.assertEqual(len(result.candidates), 9)
        self.assertEqual(len(result.zapier_payload["workflow"]["draft_jokes"]), 10)
        self.assertEqual(len(result.zapier_payload["workflow"]["jokes"]), 9)
        self.assertIn("lineage", result.zapier_payload["workflow"]["jokes"][0])
        self.assertTrue(result.zapier_payload["workflow"]["jokes"][0]["headline_ids"])
        self.assertIn("research_prompt", seen)
        self.assertIn("comedian_prompt", seen)
        self.assertIn("editor_prompt", seen)
        self.assertEqual(
            result.zapier_payload["email"]["subject"], "Joke of the Day: headsets"
        )

    def test_daily_workflow_anchors_retrieval_to_current_headlines(self) -> None:
        store = StaleSearchStore()
        seen: dict[str, object] = {}

        def generator(prompt: str, context: list[str]) -> list[str]:
            del prompt
            seen["context"] = tuple(context)
            return [f"Joke {index + 1}: {context[index % len(context)]}" for index in range(10)]

        result = run_daily_workflow(
            topic="daily news",
            headlines=self.headlines,
            vote_totals={},
            generator=generator,
            mailing_list="",
            headline_store=store,
        )

        self.assertIn("Apple launches new headset", store.queries[0])
        self.assertNotIn("Old stored headline", seen["context"])
        self.assertIn("Apple launches new headset", seen["context"])
        self.assertTrue(
            any(
                "Apple launches new headset" in candidate.text
                for candidate in result.candidates
            )
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
