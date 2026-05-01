"""Tiny S3 connectivity example.

This file intentionally avoids hardcoded credentials.

Required env vars:
  - S3_BUCKET

Optional (for S3-compatible providers like Cloudflare R2 / MinIO):
  - S3_ENDPOINT_URL
  - AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY
  - S3_REGION (or AWS_REGION)
"""

from ingestion.producer.s3client import S3Config, S3NewsUploader


def main() -> None:
    uploader = S3NewsUploader(S3Config.from_env())
    resp = uploader._client.list_objects_v2(Bucket=uploader.config.bucket, MaxKeys=20)
    for obj in resp.get("Contents", []) or []:
        print(obj.get("Key"))


if __name__ == "__main__":
    main()
