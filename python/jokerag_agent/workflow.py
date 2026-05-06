from __future__ import annotations

from collections.abc import Callable, Iterable

from .agents import build_crewai_plan, generate_jokes_with_callback
from .models import Headline, JokeCandidate, JokeRunResult
from .rag import build_langchain_prompt
from .ranking import apply_vote_totals, dedupe_headlines, pick_joke_of_the_day, rank_jokes
from .pinecone_store import PineconeConfig, PineconeHeadlineStore
from .vector_store import HeadlineVectorStore, InMemoryHeadlineStore
from .zapier import build_zapier_email_payload, build_zapier_webhook_payload


def run_daily_workflow(
    topic: str,
    headlines: Iterable[Headline],
    vote_totals: dict[str, int],
    generator: Callable[[str, list[str]], list[str]],
    mailing_list: str,
    joke_count: int = 10,
    headline_store: HeadlineVectorStore | None = None,
) -> JokeRunResult:
    deduped = dedupe_headlines(headlines)
    store = headline_store or _build_default_headline_store()
    store.upsert_headlines(topic, deduped)
    retrieval_context = store.search_headlines(topic, limit=5)
    prompt = build_langchain_prompt(topic, retrieval_context, joke_count=joke_count)
    build_crewai_plan(topic, retrieval_context, joke_count=joke_count)
    generated = generate_jokes_with_callback(topic, retrieval_context, joke_count, generator)
    ranked = rank_jokes(apply_vote_totals(generated, vote_totals))
    winner = pick_joke_of_the_day(ranked)
    headline_list = tuple(deduped)
    if winner is None:
        raise ValueError("run_daily_workflow requires at least one joke candidate")

    webhook_payload = build_zapier_webhook_payload(
        topic=topic,
        winner=winner,
        headlines=list(headline_list),
        mailing_list=mailing_list,
    )
    email_payload = build_zapier_email_payload(
        topic=topic,
        winner=winner,
        headlines=list(headline_list),
        mailing_list=mailing_list,
    )
    return JokeRunResult(
        topic=topic,
        brief=prompt,
        retrieval_context=tuple(doc.page_content for doc in retrieval_context),
        candidates=tuple(ranked),
        winner=winner,
        zapier_payload={"webhook": webhook_payload, "email": email_payload},
        headlines=headline_list,
        votes=tuple(sorted(vote_totals.items())),
    )


def _build_default_headline_store() -> HeadlineVectorStore:
    import os

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
