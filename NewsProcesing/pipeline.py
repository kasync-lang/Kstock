from __future__ import annotations

import argparse
import logging
from datetime import date, datetime
from typing import Any

import chunker
import dedup
import embedder
import repository
import vector_store

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("news_pipeline")


def run_pipeline(
    symbol: str,
    target_date: str | date | datetime,
    deduplicate_threshold: int = 3,
    store_vectors: bool = True,
) -> dict[str, Any]:
    """Orchestrate and execute the news processing pipeline.

    Steps:
        1. Fetch articles for the given symbol and date from the database.
        2. Deduplicate articles using SimHash.
        3. Chunk each unique article into section-aware documents.
        4. Save chunk text into the 'article_chunks' PostgreSQL table.
        5. Embed chunks with OpenAI and upsert the vectors into Qdrant.

    Args:
        symbol: Stock ticker symbol (e.g., 'AAPL').
        target_date: Target date string ('YYYY-MM-DD') or date object.
        deduplicate_threshold: Maximum Hamming distance for near-duplicate articles.
        store_vectors: When False, chunk text is still stored but no embeddings
                       are generated and no vectors are pushed to Qdrant.

    Returns:
        Summary dict containing statistics of the execution.
    """
    logger.info("Starting news pipeline for symbol=%s, date=%s", symbol, target_date)

    # Step 1: Fetch articles from repository
    raw_articles = repository.fetch_articles(symbol=symbol, target_date=target_date)
    logger.info("Fetched %d articles from database", len(raw_articles))

    if not raw_articles:
        logger.info("No articles found for processing. Exiting pipeline.")
        return {
            "symbol": symbol,
            "date": str(target_date),
            "fetched_articles": 0,
            "deduped_articles": 0,
            "total_chunks": 0,
            "saved_chunks": 0,
            "vectors_stored": 0,
            "vector_error": None,
        }

    # Step 2: Deduplication using SimHash
    articles = dedup.remove_duplicates(raw_articles, threshold=deduplicate_threshold)
    dropped_count = len(raw_articles) - len(articles)
    logger.info(
        "Deduplication completed: %d unique articles retained (%d near-duplicates dropped)",
        len(articles),
        dropped_count,
    )

    # Step 3: Chunking
    all_chunks = []
    for article in articles:
        chunks = chunker.chunk_article(article)
        all_chunks.extend(chunks)

    logger.info(
        "Chunking completed: generated %d total chunks from %d articles",
        len(all_chunks),
        len(articles),
    )

    if not all_chunks:
        logger.info("No text chunks generated. Skipping database storage.")
        return {
            "symbol": symbol,
            "date": str(target_date),
            "fetched_articles": len(raw_articles),
            "deduped_articles": len(articles),
            "total_chunks": 0,
            "saved_chunks": 0,
            "vectors_stored": 0,
            "vector_error": None,
        }

    # Step 4: Save chunk text into the PostgreSQL article_chunks table
    saved_chunks = repository.save_article_chunks(all_chunks)
    logger.info("Database store completed: saved %d chunks", len(saved_chunks))

    # Step 5: Embed chunks with OpenAI and upsert the vectors into Qdrant
    vectors_stored = 0
    vector_error: str | None = None
    if store_vectors:
        # Map (article_id, chunk_index) -> article_chunks.id so Qdrant points
        # stay linked to the relational chunk rows.
        chunk_ids = {
            (str(record["article_id"]), int(record["chunk_index"])): record["id"]
            for record in saved_chunks
        }
        try:
            vectors = embedder.embed_chunks(all_chunks)
            vectors_stored = vector_store.upsert_vectors(vectors, chunk_ids=chunk_ids)
            logger.info("Vector store completed: upserted %d vectors", vectors_stored)
        except Exception as exc:  # keep stored chunks even if Qdrant fails
            vector_error = f"{type(exc).__name__}: {exc}"
            logger.error("Vector store step failed: %s", vector_error)
    else:
        logger.info("Vector storage skipped (store_vectors=False)")

    return {
        "symbol": symbol,
        "date": str(target_date),
        "fetched_articles": len(raw_articles),
        "deduped_articles": len(articles),
        "total_chunks": len(all_chunks),
        "saved_chunks": len(saved_chunks),
        "vectors_stored": vectors_stored,
        "vector_error": vector_error,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run News Processing Pipeline")
    parser.add_argument(
        "--symbol",
        type=str,
        required=True,
        help="Stock ticker symbol (e.g., AAPL)",
    )
    parser.add_argument(
        "--date",
        type=str,
        required=True,
        help="Target date in YYYY-MM-DD format (e.g., 2026-10-14)",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=3,
        help="SimHash Hamming distance threshold for deduplication (default: 3)",
    )
    parser.add_argument(
        "--skip-vectors",
        action="store_true",
        help="Only store chunk text in PostgreSQL, skip OpenAI embeddings and Qdrant upsert",
    )

    args = parser.parse_args()
    summary = run_pipeline(
        symbol=args.symbol,
        target_date=args.date,
        deduplicate_threshold=args.threshold,
        store_vectors=not args.skip_vectors,
    )
    print(f"\nPipeline execution summary: {summary}")


if __name__ == "__main__":
    main()
