from __future__ import annotations

import argparse
import logging
import os
from datetime import date, datetime, timezone

from ingestion.model.news_model import NewsRaw
from ingestion.producer.s3client import S3NewsUploader
from ingestion.source.api_ingester import APIGeter, load_symbols


def _parse_date(s: str) -> date:
    return date.fromisoformat(s)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logger = logging.getLogger(__name__)

    parser = argparse.ArgumentParser(description="Fetch Finnhub news and upload to S3 (or print to stdout).")
    parser.add_argument("--from-date", type=_parse_date, default=datetime.now(timezone.utc).date(), help="Start date (inclusive) in YYYY-MM-DD format")
    parser.add_argument("--to-date", type=_parse_date, default=datetime.now(timezone.utc).date(), help="End date (inclusive) in YYYY-MM-DD format")
    parser.add_argument(
        "--sink",
        choices=["s3", "stdout"],
        default=(os.getenv("NEWS_SINK") or "s3").strip().lower(),
        help="Where to send fetched news (default: s3; override with NEWS_SINK).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch/parse but do not upload (useful to validate API & parsing).",
    )
    args = parser.parse_args()

    symbols = load_symbols()
    if not symbols:
        logger.warning("No symbols loaded. Exiting.")
        return

    api_getter = APIGeter()
    uploader: S3NewsUploader | None = None
    if args.sink == "s3" and not args.dry_run:
        uploader = S3NewsUploader.from_env()

    logger.info("Fetching news for %d symbols from %s to %s", len(symbols), args.from_date, args.to_date)
    all_news: list[NewsRaw] = []
    # for s in symbols:
    #     try:
    #         news_items = api_getter.fetch_news_raw(s, from_date=args.from_date, to_date=args.to_date)
    #         all_news.extend(news_items)
    #         logger.info("Fetched %d news items for symbol %s", len(news_items), s)
    #     except Exception:
    #         logger.exception("Failed to fetch news for symbol %s", s)

    if args.dry_run:
        logger.info("Dry run enabled: fetched %d items; not uploading.", len(all_news))
        return

    if args.sink == "stdout":
        for it in all_news:
            # One JSON object per line.
            print(it.to_json_bytes().decode("utf-8"))
        logger.info("Printed %d news items", len(all_news))
        return

    # if args.sink == "s3":
    #     assert uploader is not None
    #     logger.info("Uploading %d news items to S3 bucket %s", len(all_news), uploader.config.bucket)
    #     try:
    #         n_uploaded = uploader.upload_many(all_news)
    #         logger.info("Successfully uploaded %d/%d news items", n_uploaded, len(all_news))
    #     except Exception:
    #         logger.exception("Failed to upload news items to S3")
    #     return
    if args.sink == "s3":
        assert uploader is not None
        logger.info("Uploading news items to S3 bucket %s",  uploader.config.bucket)
        for s in symbols:
            try:
                news_items = api_getter.fetch_news_raw(s, from_date=args.from_date, to_date=args.to_date)
                logger.info("Fetched %d news items for symbol %s", len(news_items), s)
                uploader.upload_list(news_items)
            except Exception:
                logger.exception("Failed to upload %s news item to S3",s)
        return

    raise ValueError(f"Unsupported sink: {args.sink!r}")


if __name__ == "__main__":
    main()