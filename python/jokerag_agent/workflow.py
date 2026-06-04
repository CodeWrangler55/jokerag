from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import asdict

from .agents import (
    apply_editor_pass,
    build_comedian_prompt,
    build_crewai_plan,
    build_editor_prompt,
    build_research_summary_prompt,
    generate_jokes_with_callback,
    summarize_retrieved_context,
)
from .models import Headline, JokeCandidate, JokeRunResult
from .rag import Document, build_langchain_prompt, build_retrieval_context
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
    researcher: Callable[[str, list[str]], str] | None = None,
    editor: Callable[[str, list[dict[str, object]]], list[object]] | None = None,
) -> JokeRunResult:
    deduped = dedupe_headlines(headlines)
    store = headline_store or _build_default_headline_store()
    store.upsert_headlines(topic, deduped)
    retrieval_query = _build_headline_retrieval_query(topic, deduped)
    retrieval_context = _current_headline_context(
        store.search_headlines(retrieval_query, limit=5),
        deduped,
        retrieval_query,
        limit=5,
    )
    context_texts = [doc.page_content for doc in retrieval_context]

    research_prompt = build_research_summary_prompt(topic, retrieval_context, joke_count=joke_count)
    research_summary = researcher(research_prompt, context_texts) if researcher else summarize_retrieved_context(topic, retrieval_context, joke_count=joke_count)

    comedian_prompt = build_comedian_prompt(topic, retrieval_context, research_summary, joke_count=joke_count)
    brief = build_langchain_prompt(topic, retrieval_context, joke_count=joke_count)
    crew_plan = build_crewai_plan(topic, retrieval_context, joke_count=joke_count, research_summary=research_summary)

    draft_candidates = generate_jokes_with_callback(
        topic,
        retrieval_context,
        joke_count,
        generator,
        research_summary=research_summary,
    )
    final_candidates = apply_editor_pass(
        topic,
        draft_candidates,
        research_summary=research_summary,
        editor=editor,
    )
    if not final_candidates:
        raise ValueError("run_daily_workflow requires at least one joke candidate")

    ranked = rank_jokes(apply_vote_totals(final_candidates, vote_totals))
    winner = pick_joke_of_the_day(ranked)
    if winner is None:
        raise ValueError("run_daily_workflow requires at least one joke candidate")

    headline_list = tuple(deduped)
    workflow_payload = {
        "topic": topic,
        "brief": brief,
        "research_prompt": research_prompt,
        "research_summary": research_summary,
        "comedian_prompt": comedian_prompt,
        "editor_prompt": build_editor_prompt(topic, draft_candidates, research_summary),
        "roles": crew_plan["roles"],
        "jokes": [_candidate_payload(candidate, retrieval_context) for candidate in ranked],
        "draft_jokes": [_candidate_payload(candidate, retrieval_context) for candidate in draft_candidates],
        "lineage": {
            "headline_ids": [headline.id for headline in headline_list],
            "headlines": [asdict(headline) for headline in headline_list],
            "retrieval_context": [_document_payload(document) for document in retrieval_context],
        },
        "editor": {
            "accepted_count": len(final_candidates),
            "rejected_count": max(0, len(draft_candidates) - len(final_candidates)),
        },
    }

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
        brief=brief,
        retrieval_context=tuple(doc.page_content for doc in retrieval_context),
        candidates=tuple(ranked),
        winner=winner,
        zapier_payload={"webhook": webhook_payload, "email": email_payload, "workflow": workflow_payload},
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


def _build_headline_retrieval_query(topic: str, headlines: Iterable[Headline]) -> str:
    titles = " ".join(headline.title.strip() for headline in headlines if headline.title.strip())
    return f"{topic.strip()} {titles}".strip()


def _current_headline_context(
    documents: list[Document],
    headlines: Iterable[Headline],
    query: str,
    limit: int,
) -> list[Document]:
    current_ids = {headline.id for headline in headlines}
    current_documents = [
        document
        for document in documents
        if str(document.metadata.get("id", "")) in current_ids
    ]
    if current_documents:
        return current_documents[:limit]

    return build_retrieval_context(query, tuple(headlines), limit=limit)


def _candidate_payload(candidate: JokeCandidate, retrieval_context: list[object]) -> dict[str, object]:
    source_map = {}
    for document in retrieval_context:
        metadata = getattr(document, "metadata", {})
        if isinstance(metadata, dict):
            headline_id = str(metadata.get("id", ""))
            if headline_id:
                source_map[headline_id] = {
                    "id": headline_id,
                    "title": getattr(document, "page_content", ""),
                    "source": metadata.get("source", ""),
                    "url": metadata.get("url", ""),
                    "published_at": metadata.get("published_at", ""),
                }
    return {
        "id": candidate.id,
        "text": candidate.text,
        "votes": candidate.votes,
        "headline_ids": list(candidate.headline_ids),
        "lineage": [source_map[headline_id] for headline_id in candidate.headline_ids if headline_id in source_map],
        "created_at": candidate.created_at,
    }


def _document_payload(document: Document) -> dict[str, object]:
    return {
        "page_content": document.page_content,
        "metadata": dict(document.metadata),
    }
