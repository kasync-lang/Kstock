from __future__ import annotations

import logging
import os
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
import psycopg
import tiktoken
from langchain_core.documents import Document
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)

# Pre-load tiktoken encoder for efficient token count calculation
_TIKTOKEN_ENCODER = tiktoken.get_encoding("cl100k_base")


def get_db_connection_params() -> dict[str, Any] | str:
    """Retrieve PostgreSQL connection parameters from environment variables."""
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url

    return {
        "host": os.getenv("POSTGRES_HOST", os.getenv("DB_HOST", "localhost")),
        "port": int(os.getenv("POSTGRES_PORT", os.getenv("DB_PORT", "5432"))),
        "dbname": os.getenv("POSTGRES_DB", os.getenv("DB_NAME", "postgres")),
        "user": os.getenv("POSTGRES_USER", os.getenv("DB_USER", "postgres")),
        "password": os.getenv("POSTGRES_PASSWORD", os.getenv("DB_PASSWORD", "")),
    }


def parse_date_range(target_date: str | date | datetime) -> tuple[datetime, datetime]:
    """Parse target date into start_time and end_time range (UTC).

    Args:
        target_date: Target date string ('YYYY-MM-DD'), date, or datetime.

    Returns:
        Tuple of (start_of_day, start_of_next_day) as timezone-aware datetimes.
    """
    if isinstance(target_date, str):
        # Support both 'YYYY-MM-DD' and ISO strings
        d = datetime.fromisoformat(target_date.split("T")[0]).date()
    elif isinstance(target_date, datetime):
        d = target_date.date()
    elif isinstance(target_date, date):
        d = target_date
    else:
        raise TypeError(f"Unsupported date type: {type(target_date)}")

    start_of_day = datetime.combine(d, time.min, tzinfo=timezone.utc)
    end_of_day = start_of_day + timedelta(days=1)
    return start_of_day, end_of_day


def fetch_articles(
    symbol: str,
    target_date: str | date | datetime,
    connection_params: dict[str, Any] | str | None = None,
) -> list[dict[str, Any]]:
    """Fetch news articles from the database for a specific symbol and date.

    Queries the 'news_articles' table within the time range of target_date.

    Args:
        symbol: Stock ticker symbol (e.g., 'AAPL').
        target_date: Target date ('YYYY-MM-DD', date, or datetime).
        connection_params: Optional PostgreSQL connection dict or connection string.

    Returns:
        List of article dicts matching the news_articles schema.
    """
    conn_info = connection_params or get_db_connection_params()
    start_time, end_time = parse_date_range(target_date)

    query = """
        SELECT
            id,
            source,
            title,
            content,
            url,
            published_at,
            image_url,
            category,
            symbol,
            ingested_at
        FROM news_articles
        WHERE symbol = %(symbol)s
          AND published_at >= %(start_time)s
          AND published_at < %(end_time)s
        ORDER BY published_at ASC;
    """

    params = {
        "symbol": symbol.strip().upper(),
        "start_time": start_time,
        "end_time": end_time,
    }

    logger.info(
        "Fetching articles for symbol=%s between %s and %s",
        params["symbol"],
        start_time.isoformat(),
        end_time.isoformat(),
    )

    if isinstance(conn_info, str):
        with psycopg.connect(conn_info, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return cur.fetchall()

    with psycopg.connect(**conn_info, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()


def _normalize_chunk_record(
    chunk: Document | dict[str, Any],
    default_index: int = 0,
) -> dict[str, Any]:
    """Normalize a LangChain Document or dict into an 'article_chunks' record."""
    if isinstance(chunk, Document):
        meta = chunk.metadata or {}
        content = chunk.page_content or ""
        article_id = meta.get("article_id") or meta.get("id") or meta.get("articles_id")
        chunk_index = meta.get("chunk_index", default_index)
        token_count = meta.get("token_count")
        if token_count is None and content:
            token_count = len(_TIKTOKEN_ENCODER.encode(content))
    elif isinstance(chunk, dict):
        meta = chunk.get("metadata", {}) or {}
        content = chunk.get("content") or chunk.get("page_content") or ""
        article_id = (
            chunk.get("article_id")
            or meta.get("article_id")
            or chunk.get("id")
            or meta.get("id")
        )
        chunk_index = chunk.get("chunk_index", meta.get("chunk_index", default_index))
        token_count = chunk.get("token_count", meta.get("token_count"))
        if token_count is None and content:
            token_count = len(_TIKTOKEN_ENCODER.encode(content))
    else:
        raise TypeError(f"Unsupported chunk type: {type(chunk)}")

    if not article_id:
        raise ValueError("Chunk record must contain a valid 'article_id'")

    return {
        "article_id": str(article_id),
        "chunk_index": int(chunk_index),
        "content": str(content),
        "token_count": int(token_count) if token_count is not None else None,
    }


def save_article_chunks(
    chunks: list[Document | dict[str, Any]],
    connection_params: dict[str, Any] | str | None = None,
    replace_existing: bool = True,
) -> list[dict[str, Any]]:
    """Save article chunk text into the PostgreSQL 'article_chunks' table.

    Chunk *text* lives in PostgreSQL while the matching vectors are stored in
    Qdrant by :mod:`vector_store`. The generated primary keys returned here are
    used as Qdrant point ids, keeping both stores linked.

    DDL reference:
        create table article_chunks (
            id bigserial primary key,
            article_id text not null references news_articles,
            chunk_index integer not null,
            content text not null,
            token_count integer,
            created_at timestamp with time zone default now() not null
        );

    Args:
        chunks: List of LangChain Documents or dicts.
        connection_params: Optional PostgreSQL connection parameters or URI string.
        replace_existing: If True, deletes existing chunks for the target article_ids
                          before inserting new chunks to prevent duplicates.

    Returns:
        List of saved records (in input order) enriched with the generated 'id'.
    """
    if not chunks:
        logger.info("No chunks provided to save.")
        return []

    records: list[dict[str, Any]] = []
    # Track per-article index if not already present
    article_index_counter: dict[str, int] = {}

    for chunk in chunks:
        # Pre-inspect article_id to maintain sequence if needed
        art_id = None
        if isinstance(chunk, Document):
            art_id = chunk.metadata.get("article_id")
        elif isinstance(chunk, dict):
            art_id = chunk.get("article_id") or (chunk.get("metadata") or {}).get("article_id")

        curr_idx = article_index_counter.get(str(art_id), 0)
        rec = _normalize_chunk_record(chunk, default_index=curr_idx)
        records.append(rec)
        article_index_counter[rec["article_id"]] = rec["chunk_index"] + 1

    conn_info = connection_params or get_db_connection_params()
    distinct_article_ids = sorted({r["article_id"] for r in records})

    insert_query = """
        INSERT INTO article_chunks (
            article_id,
            chunk_index,
            content,
            token_count
        ) VALUES (
            %(article_id)s,
            %(chunk_index)s,
            %(content)s,
            %(token_count)s
        ) RETURNING id;
    """

    delete_query = """
        DELETE FROM article_chunks
        WHERE article_id = ANY(%(article_ids)s);
    """

    def _execute(conn: psycopg.Connection) -> list[int]:
        with conn.cursor() as cur:
            if replace_existing and distinct_article_ids:
                cur.execute(delete_query, {"article_ids": distinct_article_ids})
                logger.info(
                    "Cleaned up previous chunks for %d article(s) before insert",
                    len(distinct_article_ids),
                )

            cur.executemany(insert_query, records, returning=True)
            inserted_ids: list[int] = []
            while True:
                inserted_ids.extend(row[0] for row in cur)
                if not cur.nextset():
                    break
        conn.commit()
        return inserted_ids

    if isinstance(conn_info, str):
        with psycopg.connect(conn_info) as conn:
            saved_ids = _execute(conn)
    else:
        with psycopg.connect(**conn_info) as conn:
            saved_ids = _execute(conn)

    if len(saved_ids) != len(records):
        raise RuntimeError(
            f"Expected {len(records)} chunk ids from insert, got {len(saved_ids)}"
        )

    for record, chunk_id in zip(records, saved_ids):
        record["id"] = int(chunk_id)

    logger.info("Successfully saved %d chunks into article_chunks table", len(records))
    return records


def save_chunks(
    chunks: list[Document | dict[str, Any]],
    connection_params: dict[str, Any] | str | None = None,
    replace_existing: bool = True,
) -> list[dict[str, Any]]:
    """Alias of :func:`save_article_chunks` kept for backwards compatibility."""
    return save_article_chunks(
        chunks=chunks,
        connection_params=connection_params,
        replace_existing=replace_existing,
    )


def fetch_chunks_by_article_id(
    article_id: str,
    connection_params: dict[str, Any] | str | None = None,
) -> list[dict[str, Any]]:
    """Retrieve saved chunk text for a specific article from the database."""
    conn_info = connection_params or get_db_connection_params()
    query = """
        SELECT
            id,
            article_id,
            chunk_index,
            content,
            token_count,
            created_at
        FROM article_chunks
        WHERE article_id = %(article_id)s
        ORDER BY chunk_index ASC;
    """

    if isinstance(conn_info, str):
        with psycopg.connect(conn_info, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(query, {"article_id": article_id})
                return cur.fetchall()

    with psycopg.connect(**conn_info, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(query, {"article_id": article_id})
            return cur.fetchall()
