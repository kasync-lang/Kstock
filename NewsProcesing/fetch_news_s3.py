#!/usr/bin/env python3
"""Download a news JSON object from S3 (or any S3-compatible store) to local disk.

The script mirrors the S3 object layout on disk. The layout used by the news
uploader (see ``airflow/dags/api/uploader.py``) is::

    news_raw/src=finnhub/AAPL/2026-10-04.json

By default the downloaded file is written under the ``NewsProcesing`` folder
(the folder that contains this script) using the same relative path as the S3
key. You can override the location with ``--output`` (an exact file path or a
directory) or ``--output-root`` (a base directory).

Credentials are supplied on the command line (``--access-key-id`` /
``--secret-access-key``), and fall back to the standard AWS environment
variables (``AWS_ACCESS_KEY_ID`` / ``AWS_SECRET_ACCESS_KEY`` /
``AWS_SESSION_TOKEN``) when omitted.

Examples
--------
Fetch one symbol/date into the default NewsProcesing layout::

    python fetch_news_s3.py \
        --bucket kstock-bucket-dev \
        --endpoint-url https://<account>.r2.cloudflarestorage.com \
        --access-key-id "$AWS_ACCESS_KEY_ID" \
        --secret-access-key "$AWS_SECRET_ACCESS_KEY" \
        --symbol AAPL --date 2026-10-04

  -> writes NewsProcesing/news_raw/src=finnhub/AAPL/2026-10-04.json

Write to an explicit file (or into an explicit directory)::

    python fetch_news_s3.py --bucket ... --symbol AAPL --date 2026-10-04 \
        --output /tmp/AAPL-2026-10-04.json

    python fetch_news_s3.py --bucket ... --symbol AAPL --date 2026-10-04 \
        --output /tmp/landing/        # -> /tmp/landing/news_raw/src=finnhub/AAPL/2026-10-04.json

Discover the objects that exist for a symbol::

    python fetch_news_s3.py --bucket ... --symbol AAPL --list
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, cast

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger("fetch_news_s3")

DEFAULT_BASE_PREFIX = "news_raw"
DEFAULT_SOURCE = "finnhub"
# The folder that contains this script == the NewsProcesing folder.
DEFAULT_OUTPUT_ROOT = Path(__file__).resolve().parent
DOWNLOAD_CHUNK_SIZE = 8 * 1024 * 1024  # 8 MiB

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2


def _env_first(*names: str) -> str | None:
    """Return the first non-empty environment variable among ``names``."""

    for name in names:
        value = (os.getenv(name) or "").strip()
        if value:
            return value
    return None


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "t", "yes", "y", "on"}


def build_object_key(
    *,
    source: str = DEFAULT_SOURCE,
    symbol: str,
    date: str,
    base_prefix: str = DEFAULT_BASE_PREFIX,
) -> str:
    """Build the S3 object key for a news file.

    Layout: ``<base_prefix>/src=<source>/<symbol>/<date>.json``
    (``<base_prefix>/`` is omitted when ``base_prefix`` is empty).
    """

    symbol = (symbol or "").strip().strip("/")
    date = (date or "").strip().strip("/")
    if not symbol:
        raise ValueError("symbol must not be empty")
    if not date:
        raise ValueError("date must not be empty")

    key = f"src={source.strip()}/{symbol}/{date}.json"

    prefix = (base_prefix or "").strip().strip("/")
    return f"{prefix}/{key}" if prefix else key


def resolve_output_path(
    *,
    key: str,
    output: str | None = None,
    output_root: str | os.PathLike[str] | None = None,
) -> Path:
    """Resolve where the downloaded object should be written.

    * ``output`` as an existing directory or with a trailing separator is
      treated as a directory; the S3 key is appended to it.
    * ``output`` as anything else is treated as the exact file path.
    * When ``output`` is not given, ``output_root`` (default: the
      NewsProcesing folder) is used as the base and the full S3 key is appended.
    """

    if output:
        candidate = Path(output).expanduser()
        looks_like_dir = output.endswith(("/", os.sep)) or candidate.is_dir()
        if looks_like_dir:
            return (candidate / key).resolve()
        return candidate.resolve()

    root = Path(output_root).expanduser() if output_root is not None else DEFAULT_OUTPUT_ROOT
    return (root / key).resolve()


@dataclass(slots=True)
class S3FetchConfig:
    """Connection settings for the source bucket.

    ``None`` fields fall back to the standard boto3 credential/configuration
    chain (environment variables, shared config, IAM role, ...).
    """

    bucket: str
    endpoint_url: str | None = None
    region: str | None = None
    access_key_id: str | None = None
    secret_access_key: str | None = None
    session_token: str | None = None
    force_path_style: bool = False
    verify_ssl: bool | str = True

    def client(self) -> Any:
        s3_kwargs: dict[str, Any] = {
            "region_name": self.region,
            "endpoint_url": self.endpoint_url,
            "aws_access_key_id": self.access_key_id,
            "aws_secret_access_key": self.secret_access_key,
            "aws_session_token": self.session_token,
            "verify": self.verify_ssl,
        }
        # Drop None so boto3's own credential chain keeps working.
        s3_kwargs = {k: v for k, v in s3_kwargs.items() if v is not None}

        if self.force_path_style:
            # botocore type stubs are stricter than runtime here.
            s3_kwargs["config"] = BotoConfig(s3=cast(Any, {"addressing_style": "path"}))

        return boto3.client("s3", **s3_kwargs)


def download_object(
    client: Any,
    *,
    bucket: str,
    key: str,
    dest: Path,
    overwrite: bool = False,
) -> int:
    """Stream ``s3://bucket/key`` to ``dest`` and return the number of bytes written.

    The write is atomic: data goes to a ``<name>.part`` sibling which is then
    renamed over ``dest`` so a partial download never replaces a good file.
    """

    if dest.exists() and not overwrite:
        raise FileExistsError(
            f"Output file already exists: {dest} (use --overwrite to replace it)"
        )

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.parent / (dest.name + ".part")

    written = 0
    try:
        response = client.get_object(Bucket=bucket, Key=key)
        body = response["Body"]
        with tmp.open("wb") as fh:
            while True:
                chunk = body.read(DOWNLOAD_CHUNK_SIZE)
                if not chunk:
                    break
                fh.write(chunk)
                written += len(chunk)
        os.replace(tmp, dest)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise

    return written


def list_objects(client: Any, *, bucket: str, prefix: str, limit: int | None = None) -> list[str]:
    """Return object keys under ``prefix`` (optionally capped at ``limit``)."""

    paginator = client.get_paginator("list_objects_v2")
    keys: list[str] = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            name = obj.get("Key")
            if name:
                keys.append(str(name))
                if limit is not None and len(keys) >= limit:
                    return keys
    return keys


def _validate_json(path: Path) -> None:
    """Raise ``ValueError`` if ``path`` does not contain valid JSON."""

    with path.open("rb") as fh:
        json.load(fh)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fetch_news_s3.py",
        description=(
            "Download a news JSON object from S3 (S3-compatible) to disk, "
            "using the layout news_raw/src=finnhub/<SYMBOL>/<DATE>.json."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # ---- Source connection / credentials -----------------------------------
    conn = parser.add_argument_group("S3 connection")
    conn.add_argument("--bucket", required=True, help="Source bucket name")
    conn.add_argument(
        "--endpoint-url",
        default=_env_first("S3_ENDPOINT_URL", "BUCKET_URL", "ENDPOINT_URL"),
        help="S3 endpoint URL (Cloudflare R2 / MinIO / LocalStack)",
    )
    conn.add_argument(
        "--region",
        default=_env_first("S3_REGION", "AWS_REGION", "AWS_DEFAULT_REGION"),
        help="AWS region",
    )
    conn.add_argument(
        "--access-key-id",
        default=_env_first("AWS_ACCESS_KEY_ID"),
        help="Access key id (falls back to AWS_ACCESS_KEY_ID)",
    )
    conn.add_argument(
        "--secret-access-key",
        default=_env_first("AWS_SECRET_ACCESS_KEY"),
        help="Secret access key (falls back to AWS_SECRET_ACCESS_KEY)",
    )
    conn.add_argument(
        "--session-token",
        default=_env_first("AWS_SESSION_TOKEN"),
        help="Session token for temporary credentials",
    )
    conn.add_argument(
        "--force-path-style",
        action="store_true",
        default=_env_bool("S3_FORCE_PATH_STYLE"),
        help="Use path-style addressing (often required for MinIO)",
    )
    conn.add_argument(
        "--no-verify-ssl",
        action="store_true",
        help="Disable TLS certificate verification",
    )

    # ---- Object selection ---------------------------------------------------
    obj = parser.add_argument_group("Object selection")
    obj.add_argument(
        "--symbol",
        help="Ticker symbol, e.g. AAPL (required unless --key is given)",
    )
    obj.add_argument(
        "--date",
        help="Published date in YYYY-MM-DD format (required unless --key is given)",
    )
    obj.add_argument(
        "--source",
        default=DEFAULT_SOURCE,
        help="Data source segment used in the key",
    )
    obj.add_argument(
        "--base-prefix",
        default=DEFAULT_BASE_PREFIX,
        help="Base prefix prepended to the key (empty string for none)",
    )
    obj.add_argument(
        "--key",
        help="Explicit S3 object key; overrides --source/--symbol/--date/--base-prefix",
    )

    # ---- Output -------------------------------------------------------------
    out = parser.add_argument_group("Output")
    out.add_argument(
        "--output",
        help=(
            "Path to write to disk. An existing directory (or a path ending in "
            "a separator) receives the S3 key appended; otherwise it is used as "
            "the exact file path."
        ),
    )
    out.add_argument(
        "--output-root",
        default=str(DEFAULT_OUTPUT_ROOT),
        help="Base directory used when --output is not given",
    )
    out.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace the output file if it already exists",
    )
    out.add_argument(
        "--validate-json",
        action="store_true",
        help="Parse the downloaded bytes as JSON and fail if invalid",
    )

    # ---- Modes --------------------------------------------------------------
    modes = parser.add_argument_group("Modes")
    modes.add_argument(
        "--list",
        action="store_true",
        dest="list_objects",
        help="List matching object keys instead of downloading",
    )
    modes.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of keys returned by --list",
    )
    modes.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be downloaded without writing anything",
    )
    modes.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )

    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # ---- Build/validate the object key -------------------------------------
    base = (args.base_prefix or "").strip().strip("/")
    folder = f"src={args.source.strip()}/{(args.symbol or '').strip()}"
    list_prefix = f"{base}/{folder}/" if base else f"{folder}/"

    key: str | None
    if args.key:
        key = args.key.strip().lstrip("/")
        list_prefix = f"{key.rsplit('/', 1)[0]}/" if "/" in key else ""
    elif args.symbol and args.date:
        key = build_object_key(
            source=args.source,
            symbol=args.symbol,
            date=args.date,
            base_prefix=args.base_prefix,
        )
    elif args.list_objects and args.symbol:
        # List every date available for the symbol.
        key = None
    else:
        parser.error("either --key, or both --symbol and --date, must be provided")

    cfg = S3FetchConfig(
        bucket=args.bucket,
        endpoint_url=args.endpoint_url,
        region=args.region,
        access_key_id=args.access_key_id,
        secret_access_key=args.secret_access_key,
        session_token=args.session_token,
        force_path_style=args.force_path_style,
        verify_ssl=not args.no_verify_ssl,
    )

    logger.debug(
        "S3 config: bucket=%s endpoint=%s region=%s path_style=%s",
        cfg.bucket,
        cfg.endpoint_url,
        cfg.region,
        cfg.force_path_style,
    )

    client = cfg.client()

    # ---- List mode ----------------------------------------------------------
    if args.list_objects:
        try:
            keys = list_objects(client, bucket=cfg.bucket, prefix=list_prefix, limit=args.limit)
        except (ClientError, BotoCoreError) as exc:
            logger.error("Failed to list s3://%s/%s: %s", cfg.bucket, list_prefix, exc)
            return EXIT_ERROR

        if not keys:
            logger.info("No objects found under s3://%s/%s", cfg.bucket, list_prefix)
            return EXIT_OK
        print(f"s3://{cfg.bucket}/{list_prefix}")
        for name in keys:
            print(name)
        logger.info("Found %d object(s)", len(keys))
        return EXIT_OK

    # ---- Resolve destination ------------------------------------------------
    assert key is not None  # set above for all non-list paths
    dest = resolve_output_path(key=key, output=args.output, output_root=args.output_root)

    logger.info("Source: s3://%s/%s", cfg.bucket, key)
    logger.info("Destination: %s", dest)

    if args.dry_run:
        logger.info("Dry run enabled: nothing was downloaded.")
        return EXIT_OK

    # ---- Download -----------------------------------------------------------
    try:
        written = download_object(
            client, bucket=cfg.bucket, key=key, dest=dest, overwrite=args.overwrite
        )
    except FileExistsError as exc:
        logger.error("%s", exc)
        return EXIT_USAGE
    except ClientError as exc:
        code = str(exc.response.get("Error", {}).get("Code", ""))
        if code in {"NoSuchKey", "404", "NotFound"}:
            logger.error("Object not found: s3://%s/%s", cfg.bucket, key)
        else:
            logger.error("Failed to download s3://%s/%s: %s", cfg.bucket, key, exc)
        return EXIT_ERROR
    except (BotoCoreError, OSError) as exc:
        logger.error("Failed to download s3://%s/%s: %s", cfg.bucket, key, exc)
        return EXIT_ERROR

    if args.validate_json:
        try:
            _validate_json(dest)
        except (ValueError, json.JSONDecodeError) as exc:
            logger.error("Downloaded file is not valid JSON: %s (%s)", dest, exc)
            return EXIT_ERROR
        logger.info("Validated JSON: %s", dest)

    logger.info("Wrote %d bytes to %s", written, dest)
    print(str(dest))
    return EXIT_OK


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:  # pragma: no cover - interactive only
        sys.exit(130)
