from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import langchain as langchain_runtime
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda

from .models import Headline
from .ranking import normalize_headline_title

LANGCHAIN_PACKAGE_VERSION = getattr(langchain_runtime, "__version__", "unknown")


def build_retrieval_context(topic: str, headlines: Iterable[Headline], limit: int = 5) -> list[Document]:
    headline_list = list(headlines)
    scored = sorted(
        (
            (_headline_score(topic, headline), headline)
            for headline in headline_list
        ),
        key=lambda item: (-item[0], normalize_headline_title(item[1].title), item[1].id),
    )
    selected = [headline for score, headline in scored if score > 0][:limit]
    if not selected:
        selected = headline_list[:limit]

    return [
        Document(
            page_content=headline.title,
            metadata={
                "id": headline.id,
                "source": headline.source,
                "url": headline.url,
                "published_at": headline.published_at,
            },
        )
        for headline in selected
    ]


def build_langchain_prompt(topic: str, context: Iterable[Document], joke_count: int = 10) -> str:
    if joke_count <= 0:
        raise ValueError("joke_count must be positive")

    chain = build_langchain_rag_prompt_chain()
    return str(
        chain.invoke(
            {
                "topic": topic,
                "context": list(context),
                "joke_count": joke_count,
            }
        )
    )


def build_langchain_rag_prompt_chain():
    """Build the LangChain LCEL prompt chain used by the joke workflow."""

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are the RAG prompt layer for an AI joke-generation workflow. "
                "Use only the retrieved headline context as factual grounding.",
            ),
            (
                "human",
                "\n".join(
                    [
                        "Topic: {topic}",
                        "Return exactly {joke_count} short jokes.",
                        "Use the retrieved context below.",
                        "Do not explain the jokes.",
                        "Context:",
                        "{context}",
                    ]
                ),
            ),
        ]
    )
    return (
        {
            "topic": RunnableLambda(lambda payload: str(payload["topic"])),
            "joke_count": RunnableLambda(lambda payload: int(payload["joke_count"])),
            "context": RunnableLambda(
                lambda payload: _format_context_block(payload["context"])
            ),
        }
        | prompt
        | RunnableLambda(lambda prompt_value: prompt_value.to_string())
    )


def _headline_score(topic: str, headline: Headline) -> int:
    topic_words = set(_tokenize(topic))
    headline_words = set(_tokenize(headline.title))
    if not topic_words:
        return len(headline_words)
    return len(topic_words & headline_words)


def _tokenize(text: str) -> list[str]:
    normalized = "".join(char.lower() if char.isalnum() else " " for char in text)
    return [token for token in normalized.split() if token]


def _format_context_line(document: Document) -> str:
    parts = [document.page_content.strip()]
    metadata = document.metadata
    for label, key in (("source", "source"), ("published", "published_at"), ("url", "url")):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(f"{label}={value.strip()}")
    return " | ".join(part for part in parts if part)


def _format_context_block(context: Any) -> str:
    if not isinstance(context, Iterable):
        return ""

    lines = [_format_context_line(document) for document in context]
    return "\n".join(f"- {line}" for line in lines)
