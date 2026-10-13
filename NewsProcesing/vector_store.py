"""Qdrant vector store for news article chunks.

Division of responsibilities
-----------------------------
* :mod:`repository` persists the chunk **text** into the PostgreSQL
  ``article_chunks`` table (``save_article_chunks``).
* This module persists the **vectors** produced by the OpenAI embeddings
  (see :mod:`embedder`) into a Qdrant collection.

Every Qdrant point is keyed by ``article_chunks.id`` (with a deterministic UUID
fallback when the database id is unknown) so vectors can always be joined back
to the relational chunk rows.

Environment variables
---------------------
``QDRANT_URL``
    Required. Qdrant endpoint, e.g. ``http://localhost:6333`` or
    ``https://<cluster-id>.<region>.cloud.qdrant.io:6333``.
``QDRANT_API_KEY``
    Optional API key (mandatory for Qdrant Cloud, unused by a local server).
``QDRANT_COLLECTION``
    Optional collection name, defaults to ``news_article_chunks``.
``OPENAI_API_KEY``
    Used by :mod:`embedder` when a query text must be embedded.
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any

from qdrant_client import QdrantClient, models

import embedder

logger = logging.getLogger(__name__)

DEFAULT_COLLECTION = "news_article_chunks"
DEFAULT_BATCH_SIZE = 100
DEFAULT_DISTANCE = "Cosine"
DEFAULT_TOP_K = 5
DEFAULT_TIMEOUT = 60.0

# Namespace used to derive stable point ids when the database chunk id is unknown.
_POINT_ID_NAMESPACE = uuid.UUID("6f2c9e5f-0d3b-4e4e-9b0e-0f8b3b0d3a11")

# Vector dimensions of the OpenAI embedding models.
MODEL_VECTOR_SIZES: dict[str, int] = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}

# Chunk metadata fields mirrored into the Qdrant payload for filtering.
_PAYLOAD_METADATA_FIELDS = (
    "section",
    "title",
    "source",
    "symbol",
    "url",
    "published_at",
)


def _resolve_distance(distance: str | models.Distance = DEFAULT_DISTANCE) -> models.Distance:
    """Convert a distance name (e.g. 'Cosine') into a qdrant models.Distance."""
    if isinstance(distance, models.Distance):
        return distance
    try:
        return models.Distance[str(distance).strip().upper()]
    except KeyError as exc:
        valid = ", ".join(item.name.lower() for item in models.Distance)
        raise ValueError(
            f"Unsupported distance '{distance}'. Use one of: {valid}"
        ) from exc


def get_qdrant_client(
    url: str | None = None,
    api_key: str | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    prefer_grpc: bool = False,
    client: QdrantClient | None = None,
) -> QdrantClient:
    """Return a Qdrant client, reusing the provided one when available.

    Args:
        url: Qdrant endpoint. Defaults to the QDRANT_URL environment variable.
        api_key: Qdrant API key. Defaults to the QDRANT_API_KEY environment variable.
        timeout: Request timeout in seconds.
        prefer_grpc: Use gRPC instead of REST (faster for large batches).
        client: Optional pre-built client; returned untouched when provided.

    Raises:
        ValueError: If no URL is provided and QDRANT_URL is not set.
    """
    if client is not None:
        return client

    resolved_url = url or os.getenv("QDRANT_URL")
    if not resolved_url:
        raise ValueError(
            "Qdrant URL is missing. Please set the QDRANT_URL environment variable "
            "or pass url directly."
        )

    resolved_api_key = api_key or os.getenv("QDRANT_API_KEY")
    logger.info("Connecting to Qdrant at %s", resolved_url)
    return QdrantClient(
        url=resolved_url,
        api_key=resolved_api_key,
        timeout=timeout,
        prefer_grpc=prefer_grpc,
    )


def resolve_collection_name(collection_name: str | None = None) -> str:
    """Resolve the target collection name (argument > QDRANT_COLLECTION > default)."""
    return collection_name or os.getenv("QDRANT_COLLECTION") or DEFAULT_COLLECTION


def resolve_vector_size(
    model: str = embedder.DEFAULT_MODEL,
    dimensions: int | None = None,
) -> int:
    """Best-effort vector size for an embedding model.

    Args:
        model: OpenAI embedding model name.
        dimensions: Explicit dimension reduction value (wins over the model default).

    Raises:
        ValueError: When the model is unknown and no dimensions were provided.
    """
    if dimensions is not None:
        return int(dimensions)
    if model in MODEL_VECTOR_SIZES:
        return MODEL_VECTOR_SIZES[model]
    known = ", ".join(sorted(MODEL_VECTOR_SIZES))
    raise ValueError(
        f"Unknown vector size for model '{model}'. Pass dimensions explicitly "
        f"or use one of: {known}"
    )

def ensure_collection(
    client: QdrantClient,
    collection_name: str | None = None,
    vector_size: int | None = None,
    distance: str | models.Distance = DEFAULT_DISTANCE,
    model: str = embedder.DEFAULT_MODEL,
    dimensions: int | None = None,
    recreate: bool = False,
    on_disk: bool = False,
) -> bool:
    """Create the Qdrant collection when it does not exist yet.

    Args:
        client: Qdrant client instance.
        collection_name: Target collection (defaults to QDRANT_COLLECTION env var).
        vector_size: Explicit vector size. Defaults to the embedding model size.
        distance: Distance metric name (default 'Cosine').
        model: Embedding model used to infer the vector size when not provided.
        dimensions: Explicit dimension reduction of the embedding model.
        recreate: Drop and re-create the collection when it already exists.
        on_disk: Store vectors on disk instead of RAM.

    Returns:
        True when a new collection was created, False when it already existed.
    """
    name = resolve_collection_name(collection_name)

    if recreate and client.collection_exists(name):
        client.delete_collection(name)
        logger.warning("Dropped existing Qdrant collection %s (recreate=True)", name)

    if client.collection_exists(name):
        return False

    size = vector_size or resolve_vector_size(model=model, dimensions=dimensions)
    client.create_collection(
        collection_name=name,
        vectors_config=models.VectorParams(
            size=int(size),
            distance=_resolve_distance(distance),
            on_disk=on_disk,
        ),
    )
    logger.info(
        "Created Qdrant collection %s (size=%d, distance=%s)",
        name,
        size,
        _resolve_distance(distance).value,
    )
    return True


def build_point_id(
    article_id: str | int,
    chunk_index: int,
    chunk_id: int | None = None,
) -> str | int:
    """Build a Qdrant point id for a chunk.

    The database chunk id is used when known (best case: vectors can be joined
    back to ``article_chunks.id``). Otherwise a deterministic UUIDv5 derived from
    ``article_id``/``chunk_index`` is used so repeated upserts stay idempotent.
    """
    if chunk_id is not None:
        return int(chunk_id)
    return str(uuid.uuid5(_POINT_ID_NAMESPACE, f"{article_id}:{int(chunk_index)}"))


def _compact(payload: dict[str, Any]) -> dict[str, Any]:
    """Drop empty values so Qdrant payloads stay clean and filterable."""
    return {key: value for key, value in payload.items() if value not in (None, "")}


def build_points(
    records: list[dict[str, Any]],
    chunk_ids: dict[tuple[str, int], int] | None = None,
    include_content: bool = True,
) -> list[models.PointStruct]:
    """Convert embedding records into Qdrant points.

    Args:
        records: Output of :func:`embedder.embed_chunks` (article_id, chunk_index,
                 content, embedding, metadata).
        chunk_ids: Mapping of ``(article_id, chunk_index) -> article_chunks.id``
                   as returned by :func:`repository.save_article_chunks`.
        include_content: Store the chunk text inside the Qdrant payload as well.

    Raises:
        ValueError: When a record has no embedding, article_id or chunk_index.
    """
    resolved_ids = chunk_ids or {}
    points: list[models.PointStruct] = []

    for record in records:
        vector = record.get("embedding")
        if not vector:
            raise ValueError(
                f"Record for article_id={record.get('article_id')} "
                f"chunk_index={record.get('chunk_index')} has no embedding"
            )

        article_id = record.get("article_id")
        chunk_index = record.get("chunk_index")
        if article_id is None or chunk_index is None:
            raise ValueError("Embedding record must contain 'article_id' and 'chunk_index'")

        meta = dict(record.get("metadata") or {})
        article_id = str(article_id)
        chunk_index = int(chunk_index)
        chunk_id = resolved_ids.get((article_id, chunk_index))

        payload: dict[str, Any] = {
            "article_id": article_id,
            "chunk_index": chunk_index,
            "chunk_id": int(chunk_id) if chunk_id is not None else None,
            "token_count": record.get("token_count", meta.get("token_count")),
        }
        for field in _PAYLOAD_METADATA_FIELDS:
            payload[field] = record.get(field, meta.get(field))
        if include_content:
            payload["content"] = record.get("content", meta.get("content"))

        points.append(
            models.PointStruct(
                id=build_point_id(article_id, chunk_index, chunk_id),
                vector=list(vector),
                payload=_compact(payload),
            )
        )

    return points

def delete_vectors_by_article_ids(
    article_ids: list[str] | tuple[str, ...] | set[str],
    collection_name: str | None = None,
    client: QdrantClient | None = None,
    url: str | None = None,
    api_key: str | None = None,
    wait: bool = True,
) -> int:
    """Delete every vector belonging to the given article ids.

    Args:
        article_ids: Article identifiers whose vectors must be removed.
        collection_name: Target collection (defaults to QDRANT_COLLECTION env var).
        client: Optional pre-built Qdrant client.
        url: Qdrant endpoint (defaults to QDRANT_URL env var).
        api_key: Qdrant API key (defaults to QDRANT_API_KEY env var).
        wait: Wait for the deletion to be applied before returning.

    Returns:
        Number of article ids requested for deletion (0 when nothing was done).
    """
    ids = sorted({str(article_id) for article_id in article_ids if article_id})
    if not ids:
        logger.info("No article ids provided for vector deletion.")
        return 0

    owns_client = client is None
    qdrant = get_qdrant_client(url=url, api_key=api_key, client=client)
    name = resolve_collection_name(collection_name)

    try:
        if not qdrant.collection_exists(name):
            logger.info("Collection %s does not exist; nothing to delete.", name)
            return 0

        qdrant.delete(
            collection_name=name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="article_id",
                            match=models.MatchAny(any=ids),
                        )
                    ]
                )
            ),
            wait=wait,
        )
        logger.info("Deleted vectors of %d article(s) from collection %s", len(ids), name)
        return len(ids)
    finally:
        _close_if_owned(qdrant, owns_client)


def _close_if_owned(client: QdrantClient, owns_client: bool) -> None:
    """Close a client only when this module created it."""
    if not owns_client:
        return
    close = getattr(client, "close", None)
    if callable(close):
        close()


def upsert_vectors(
    records: list[dict[str, Any]],
    chunk_ids: dict[tuple[str, int], int] | None = None,
    collection_name: str | None = None,
    client: QdrantClient | None = None,
    url: str | None = None,
    api_key: str | None = None,
    model: str = embedder.DEFAULT_MODEL,
    dimensions: int | None = None,
    distance: str | models.Distance = DEFAULT_DISTANCE,
    batch_size: int = DEFAULT_BATCH_SIZE,
    wait: bool = True,
    replace_existing: bool = True,
    include_content: bool = True,
    recreate: bool = False,
) -> int:
    """Upsert chunk embeddings into the Qdrant collection.

    The collection is created automatically when missing, using the vector size
    detected from the records (or the model default when there are no records).

    Args:
        records: Output of :func:`embedder.embed_chunks`.
        chunk_ids: Mapping of ``(article_id, chunk_index) -> article_chunks.id``;
                   used to key points with the PostgreSQL chunk id.
        collection_name: Target collection (defaults to QDRANT_COLLECTION env var).
        client: Optional pre-built Qdrant client (not closed by this function).
        url: Qdrant endpoint (defaults to QDRANT_URL env var).
        api_key: Qdrant API key (defaults to QDRANT_API_KEY env var).
        model: Embedding model, used to infer the default vector size.
        dimensions: Dimension reduction value of the embedding model.
        distance: Distance metric for a newly created collection.
        batch_size: Number of points sent per upsert request.
        wait: Wait for each upsert to be applied before returning.
        replace_existing: Delete previous vectors of the same articles first,
                          keeping PostgreSQL and Qdrant in sync.
        include_content: Also store the chunk text in the Qdrant payload.
        recreate: Drop and re-create the collection before upserting.

    Returns:
        Number of vectors upserted.
    """
    points = build_points(records, chunk_ids=chunk_ids, include_content=include_content)
    if not points:
        logger.info("No vector records to upsert.")
        return 0

    owns_client = client is None
    qdrant = get_qdrant_client(url=url, api_key=api_key, client=client)
    name = resolve_collection_name(collection_name)

    try:
        vector_size = len(points[0].vector)
        ensure_collection(
            qdrant,
            collection_name=name,
            vector_size=vector_size,
            distance=distance,
            model=model,
            dimensions=dimensions,
            recreate=recreate,
        )

        if replace_existing:
            article_ids = sorted({str(point.payload["article_id"]) for point in points})
            delete_vectors_by_article_ids(article_ids, collection_name=name, client=qdrant)

        upserted = 0
        for start in range(0, len(points), batch_size):
            batch = points[start : start + batch_size]
            qdrant.upsert(collection_name=name, points=batch, wait=wait)
            upserted += len(batch)

        logger.info("Upserted %d vectors into Qdrant collection %s", upserted, name)
        return upserted
    finally:
        _close_if_owned(qdrant, owns_client)

def search_similar(
    query_vector: list[float],
    top_k: int = DEFAULT_TOP_K,
    collection_name: str | None = None,
    client: QdrantClient | None = None,
    url: str | None = None,
    api_key: str | None = None,
    query_filter: models.Filter | None = None,
    score_threshold: float | None = None,
    with_payload: bool = True,
) -> list[dict[str, Any]]:
    """Search the most similar chunk vectors.

    Args:
        query_vector: Embedding of the search query.
        top_k: Maximum number of hits to return.
        collection_name: Target collection (defaults to QDRANT_COLLECTION env var).
        client: Optional pre-built Qdrant client.
        url: Qdrant endpoint (defaults to QDRANT_URL env var).
        api_key: Qdrant API key (defaults to QDRANT_API_KEY env var).
        query_filter: Optional Qdrant filter (e.g. restrict to one symbol).
        score_threshold: Minimum similarity score.
        with_payload: Return the stored chunk payload with each hit.

    Returns:
        List of dicts with 'id', 'score' and 'payload'.
    """
    if not query_vector:
        raise ValueError("query_vector must not be empty")

    owns_client = client is None
    qdrant = get_qdrant_client(url=url, api_key=api_key, client=client)
    name = resolve_collection_name(collection_name)

    try:
        if not qdrant.collection_exists(name):
            logger.info("Collection %s does not exist; returning no hits.", name)
            return []

        response = qdrant.query_points(
            collection_name=name,
            query=list(query_vector),
            limit=top_k,
            query_filter=query_filter,
            score_threshold=score_threshold,
            with_payload=with_payload,
        )
        hits = getattr(response, "points", response) or []
        return [
            {"id": hit.id, "score": hit.score, "payload": hit.payload}
            for hit in hits
        ]
    finally:
        _close_if_owned(qdrant, owns_client)


def search_similar_text(
    query_text: str,
    top_k: int = DEFAULT_TOP_K,
    collection_name: str | None = None,
    client: QdrantClient | None = None,
    url: str | None = None,
    api_key: str | None = None,
    model: str = embedder.DEFAULT_MODEL,
    dimensions: int | None = None,
    query_filter: models.Filter | None = None,
    score_threshold: float | None = None,
    with_payload: bool = True,
) -> list[dict[str, Any]]:
    """Embed a raw query text with OpenAI and search the vector store.

    Convenience wrapper around :func:`embedder.embed_texts` + :func:`search_similar`.
    """
    if not str(query_text or "").strip():
        raise ValueError("query_text must not be empty")

    vector = embedder.embed_texts(
        [query_text],
        model=model,
        dimensions=dimensions,
    )[0]
    return search_similar(
        query_vector=vector,
        top_k=top_k,
        collection_name=collection_name,
        client=client,
        url=url,
        api_key=api_key,
        query_filter=query_filter,
        score_threshold=score_threshold,
        with_payload=with_payload,
    )


def build_article_filter(article_ids: list[str] | tuple[str, ...] | set[str]) -> models.Filter:
    """Build a Qdrant filter matching the given article ids."""
    ids = sorted({str(article_id) for article_id in article_ids if article_id})
    if not ids:
        raise ValueError("At least one article id is required to build a filter")
    return models.Filter(
        must=[
            models.FieldCondition(key="article_id", match=models.MatchAny(any=ids))
        ]
    )


__all__ = [
    "DEFAULT_BATCH_SIZE",
    "DEFAULT_COLLECTION",
    "DEFAULT_DISTANCE",
    "DEFAULT_TOP_K",
    "MODEL_VECTOR_SIZES",
    "build_article_filter",
    "build_point_id",
    "build_points",
    "delete_vectors_by_article_ids",
    "ensure_collection",
    "get_qdrant_client",
    "resolve_collection_name",
    "resolve_vector_size",
    "search_similar",
    "search_similar_text",
    "upsert_vectors",
]



