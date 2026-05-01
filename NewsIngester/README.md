# NewsIngester

Fetches company news from Finnhub and writes each `NewsRaw` item to S3 (or any S3-compatible storage like MinIO / Cloudflare R2).

## Quick start (local)

1) Create a `.env` file (or export env vars):

```bash
# Finnhub
export SECRET_KEY_HUB="<finnhub_token_1>,<finnhub_token_2>"

# S3
export S3_BUCKET="my-news-bucket"
# Optional for S3-compatible providers:
# export S3_ENDPOINT_URL="https://<accountid>.r2.cloudflarestorage.com"  # Cloudflare R2
# export S3_REGION="auto"  # R2 uses "auto"; AWS uses e.g. us-east-1
# export AWS_ACCESS_KEY_ID="..."
# export AWS_SECRET_ACCESS_KEY="..."
# export S3_FORCE_PATH_STYLE=true  # often required for MinIO
```

2) Run the ingester:

```bash
python main.py --from-date 2026-05-01 --to-date 2026-05-02
```

## CLI options

- `--sink s3|stdout` (default: `s3`, can be overridden with `NEWS_SINK`)
- `--dry-run` fetch & parse only

## S3 key layout

Objects are stored with a partitioned prefix:

```
news_raw/source=<source>/symbol=<symbol>/date=<YYYY-MM-DD>/<news_id>.json
```

If `S3_PREFIX` is set, it is prepended (e.g. `prod/` or `dev/`).

