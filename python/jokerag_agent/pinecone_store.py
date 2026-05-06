from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .models import Headline
from .rag import Document


@dataclass(frozen=True, slots=True)
class PineconeConfig:
    api_key: str
    index_name: str = "jokerag-headlines"
    namespace: str = "daily-headlines"
    cloud: str = "aws"
    region: str = "us-east-1"
    embed_model: str = "llama-text-embed-v2"


class PineconeHeadlineStore:
    """Pinecone-backed headline retrieval using Starter-plan-safe defaults."""

    def __init__(self, config: PineconeConfig) -> None:
        self._config = config
        self._index = bootstrap_pinecone_index(config)

    def upsert_headlines(self, topic: str, headlines: Iterable[Headline]) -> None:
        records = [
            {
                "_id": headline.id,
                "chunk_text": headline.title,
                "topic": topic,
                "source": headline.source,
                "url": headline.url,
                "published_at": headline.published_at,
            }
            for headline in headlines
        ]
        if records:
            self._index.upsert_records(self._config.namespace, records)

    def search_headlines(self, topic: str, limit: int = 5) -> list[Document]:
        response = self._index.search(
            namespace=self._config.namespace,
            query={"top_k": limit, "inputs": {"text": topic}},
        )
        hits = _extract_hits(response)
        documents: list[Document] = []
        for hit in hits[:limit]:
            fields = hit.get("fields", {})
            chunk_text = fields.get("chunk_text") or fields.get("text") or hit.get("text") or ""
            documents.append(
                Document(
                    page_content=str(chunk_text),
                    metadata={
                        "id": hit.get("_id", ""),
                        "score": hit.get("_score", 0.0),
                        **fields,
                    },
                )
        )
        return documents


def bootstrap_pinecone_index(config: PineconeConfig):
    """Create or open the Pinecone index using Starter-plan-safe defaults."""

    pinecone_client = _build_pinecone_client(config.api_key)
    if not pinecone_client.has_index(config.index_name):
        pinecone_client.create_index_for_model(
            name=config.index_name,
            cloud=config.cloud,
            region=config.region,
            embed={
                "model": config.embed_model,
                "field_map": {"text": "chunk_text"},
            },
        )
    return pinecone_client.Index(config.index_name)


def _build_pinecone_client(api_key: str):
    try:
        from pinecone import Pinecone
    except Exception as exc:  # pragma: no cover - import guard
        raise RuntimeError("pinecone package is required for PineconeHeadlineStore") from exc
    return Pinecone(api_key=api_key)


def _extract_hits(response: object) -> list[dict[str, object]]:
    if isinstance(response, dict):
        result = response.get("result", {})
        if isinstance(result, dict):
            hits = result.get("hits", [])
            if isinstance(hits, list):
                return [hit for hit in hits if isinstance(hit, dict)]
    result_attr = getattr(response, "result", None)
    if isinstance(result_attr, dict):
        hits = result_attr.get("hits", [])
        if isinstance(hits, list):
            return [hit for hit in hits if isinstance(hit, dict)]
    return []
