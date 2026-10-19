from __future__ import annotations

import logging
import os
from typing import Any
from langchain_core.documents import Document
from openai import OpenAI

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "text-embedding-3-small"
DEFAULT_BATCH_SIZE = 100


def get_openai_client(api_key: str | None = None) -> OpenAI:
    """Retrieve an initialized OpenAI client.

    Args:
        api_key: Optional explicit API key. Defaults to OPENAI_API_KEY env var.
    """
    key = api_key or os.getenv("OPENAI_API_KEY")
    if not key:
        raise ValueError(
            "OpenAI API key is missing. Please set the OPENAI_API_KEY environment variable "
            "or pass api_key directly."
        )
    return OpenAI(api_key=key)


def embed_texts(
    texts: list[str],
    client: OpenAI | None = None,
    model: str = DEFAULT_MODEL,
    batch_size: int = DEFAULT_BATCH_SIZE,
    dimensions: int | None = None,
) -> list[list[float]]:
    """Embed a list of text strings in batches using OpenAI Embeddings API.

    Args:
        texts: List of text strings to embed.
        client: Optional OpenAI client instance.
        model: Embedding model name (defaults to 'text-embedding-3-small').
        batch_size: Maximum number of texts per API batch request.
        dimensions: Optional dimension reduction parameter (supported by text-embedding-3 models).

    Returns:
        List of embedding vectors (list of floats).
    """
    if not texts:
        return []

    client = client or get_openai_client()
    embeddings: list[list[float]] = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        # Sanitize empty strings to avoid API validation errors
        sanitized_batch = [t if str(t).strip() else " " for t in batch]

        kwargs: dict[str, Any] = {
            "model": model,
            "input": sanitized_batch,
        }
        if dimensions is not None:
            kwargs["dimensions"] = dimensions

        response = client.embeddings.create(**kwargs)
        # Ensure returned embeddings match input order via item.index
        batch_embeddings = [
            item.embedding
            for item in sorted(response.data, key=lambda x: x.index)
        ]
        embeddings.extend(batch_embeddings)

    return embeddings


def embed_chunks(
    chunks: list[Document | dict[str, Any]],
    client: OpenAI | None = None,
    model: str = DEFAULT_MODEL,
    batch_size: int = DEFAULT_BATCH_SIZE,
    dimensions: int | None = None,
) -> list[dict[str, Any]]:
    """Generate vector embeddings for article chunks using text-embedding-3-small.

    Args:
        chunks: List of LangChain Document objects or chunk dictionaries.
        client: Optional OpenAI client instance.
        model: Embedding model name (defaults to 'text-embedding-3-small').
        batch_size: Batch size for OpenAI API calls.
        dimensions: Optional dimension parameter.

    Returns:
        List of records, each containing 'article_id', 'chunk_index', 'content',
        'embedding', and 'metadata'.
    """
    if not chunks:
        logger.info("No chunks provided for embedding.")
        return []

    texts: list[str] = []
    chunk_meta_list: list[dict[str, Any]] = []

    for chunk in chunks:
        if isinstance(chunk, Document):
            content = chunk.page_content
            meta = dict(chunk.metadata or {})
        elif isinstance(chunk, dict):
            content = chunk.get("content") or chunk.get("page_content") or ""
            meta = dict(chunk.get("metadata") or chunk)
        else:
            raise TypeError(f"Unsupported chunk type: {type(chunk)}")

        texts.append(content)
        chunk_meta_list.append(meta)

    logger.info(
        "Generating embeddings for %d chunks using model=%s",
        len(texts),
        model,
    )

    vectors = embed_texts(
        texts=texts,
        client=client,
        model=model,
        batch_size=batch_size,
        dimensions=dimensions,
    )

    results: list[dict[str, Any]] = []
    for text, meta, vec in zip(texts, chunk_meta_list, vectors):
        results.append({
            "article_id": meta.get("article_id"),
            "chunk_index": meta.get("chunk_index"),
            "content": text,
            "embedding": vec,
            "metadata": meta,
        })

    logger.info("Successfully embedded %d chunks", len(results))
    return results
