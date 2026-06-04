from __future__ import annotations

from collections.abc import Iterable, Sequence
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
        records = [_headline_record(topic, headline) for headline in headlines]
        if not records:
            return
        _upsert_records(self._index, self._config.namespace, records)

    def search_headlines(self, topic: str, limit: int = 5) -> list[Document]:
        if limit <= 0:
            return []

        response = _search_records(self._index, self._config.namespace, topic, limit)
        hits = _extract_hits(response)
        return [_hit_to_document(hit) for hit in hits[:limit]]


def bootstrap_pinecone_index(config: PineconeConfig):
    """Create or open the Pinecone index using Starter-plan-safe defaults."""

    pinecone_client = _build_pinecone_client(config.api_key)
    if not _index_exists(pinecone_client, config.index_name):
        pinecone_client.create_index_for_model(
            name=config.index_name,
            cloud=config.cloud,
            region=config.region,
            embed={
                "model": config.embed_model,
                "field_map": {"text": "chunk_text"},
            },
        )
    return _open_index(pinecone_client, config.index_name)


def _build_pinecone_client(api_key: str):
    try:
        from pinecone import Pinecone
    except Exception as exc:  # pragma: no cover - import guard
        raise RuntimeError("pinecone package is required for PineconeHeadlineStore") from exc
    return Pinecone(api_key=api_key)


def _index_exists(client: object, index_name: str) -> bool:
    has_index = getattr(client, "has_index", None)
    if callable(has_index):
        try:
            return bool(has_index(index_name))
        except TypeError:
            pass

    list_indexes = getattr(client, "list_indexes", None)
    if callable(list_indexes):
        try:
            indexes = list_indexes()
        except TypeError:
            indexes = list_indexes(index_name)  # type: ignore[misc]
        return index_name in _extract_index_names(indexes)

    return False


def _extract_index_names(indexes: object) -> set[str]:
    names: set[str] = set()
    candidates: Sequence[object]
    if isinstance(indexes, dict):
        raw_indexes = indexes.get("indexes", [])
        candidates = raw_indexes if isinstance(raw_indexes, Sequence) else []
    elif isinstance(indexes, Sequence) and not isinstance(indexes, (str, bytes)):
        candidates = indexes
    else:
        candidates = []

    for item in candidates:
        if isinstance(item, str):
            names.add(item)
            continue
        name = getattr(item, "name", None)
        if isinstance(name, str):
            names.add(name)
            continue
        if isinstance(item, dict):
            value = item.get("name")
            if isinstance(value, str):
                names.add(value)
    return names


def _open_index(client: object, index_name: str):
    index_factory = getattr(client, "Index")
    try:
        return index_factory(index_name)
    except TypeError:
        describe_index = getattr(client, "describe_index", None)
        if callable(describe_index):
            description = describe_index(index_name)
            host = _extract_index_host(description)
            if host:
                return index_factory(host=host)
        raise


def _extract_index_host(description: object) -> str | None:
    if isinstance(description, dict):
        host = description.get("host")
        if isinstance(host, str):
            return host
    host = getattr(description, "host", None)
    if isinstance(host, str):
        return host
    return None


def _headline_record(topic: str, headline: Headline) -> dict[str, object]:
    return {
        "_id": headline.id,
        "chunk_text": headline.title.strip(),
        "topic": topic.strip(),
        "source": headline.source,
        "url": headline.url,
        "published_at": headline.published_at,
    }


def _upsert_records(index: object, namespace: str, records: Sequence[dict[str, object]]) -> object:
    upsert_records = getattr(index, "upsert_records", None)
    if callable(upsert_records):
        return upsert_records(namespace=namespace, records=records)

    upsert = getattr(index, "upsert", None)
    if callable(upsert):
        return upsert(namespace=namespace, records=records)

    raise AttributeError("Pinecone index does not support record upserts")


def _search_records(index: object, namespace: str, query_text: str, limit: int) -> object:
    inputs = {"text": query_text.strip()}
    fields = ["chunk_text", "topic", "source", "url", "published_at"]

    search_records = getattr(index, "search_records", None)
    if callable(search_records):
        return search_records(namespace=namespace, top_k=limit, inputs=inputs, fields=fields)

    search = getattr(index, "search", None)
    if callable(search):
        return search(namespace=namespace, top_k=limit, inputs=inputs, fields=fields)

    raise AttributeError("Pinecone index does not support text search")


def _extract_hits(response: object) -> list[object]:
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
            return list(hits)
    hits_attr = getattr(result_attr, "hits", None)
    if isinstance(hits_attr, list):
        return list(hits_attr)
    return []


def _hit_to_document(hit: object) -> Document:
    source = _coerce_hit(hit)
    fields = _hit_fields(source)
    page_content = str(
        fields.get("chunk_text")
        or source.get("chunk_text")
        or fields.get("text")
        or source.get("text")
        or ""
    ).strip()
    metadata: dict[str, object] = {
        "id": str(source.get("_id") or source.get("id") or ""),
        "score": float(source.get("_score") or source.get("score") or 0.0),
    }
    metadata.update(fields)
    metadata.pop("chunk_text", None)
    metadata.pop("text", None)
    return Document(page_content=page_content, metadata=metadata)


def _hit_fields(hit: object) -> dict[str, object]:
    if not isinstance(hit, dict):
        return {}
    fields = hit.get("fields")
    if isinstance(fields, dict):
        return dict(fields)
    return {
        key: value
        for key, value in hit.items()
        if key not in {"_id", "_score", "fields"} and value is not None
    }


def _coerce_hit(hit: object) -> dict[str, object]:
    if isinstance(hit, dict):
        return dict(hit)

    fields = getattr(hit, "fields", None)
    payload: dict[str, object] = {}
    for name in ("id", "_id", "score", "_score", "text", "chunk_text"):
        value = getattr(hit, name, None)
        if value is not None:
            payload[name] = value
    if isinstance(fields, dict):
        payload["fields"] = dict(fields)
    return payload

