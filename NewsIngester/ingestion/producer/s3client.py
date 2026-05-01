from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import timezone
from typing import Any, Iterable, cast

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError
from dotenv import load_dotenv

from ingestion.model.news_model import NewsRaw

logger = logging.getLogger(__name__)


def _env_bool(name: str, default: bool = False) -> bool:
	v = os.getenv(name)
	if v is None:
		return default
	return v.strip().lower() in {"1", "true", "t", "yes", "y", "on"}


def _clean_segment(s: str) -> str:
	"""Conservative cleaning for key path segments.

	S3 keys can contain almost any character, but partitioned layouts (source=...)
	work best with a restricted set.
	"""

	s = (s or "").strip()
	out: list[str] = []
	for ch in s:
		if ch.isalnum() or ch in {"-", "_", ".", "=", ":"}:
			out.append(ch)
		else:
			out.append("_")
	return "".join(out) or "_"


@dataclass(slots=True)
class S3Config:
	bucket: str
	prefix: str = ""
	region: str | None = None
	endpoint_url: str | None = None
	access_key_id: str | None = None
	secret_access_key: str | None = None
	session_token: str | None = None
	force_path_style: bool = False
	verify_ssl: bool | str = True

	@staticmethod
	def from_env(*, require_bucket: bool = True) -> "S3Config":
		"""Read S3 configuration from environment variables.

		Required:
		  - S3_BUCKET

		Optional:
		  - S3_PREFIX
		  - S3_ENDPOINT_URL (for MinIO / Cloudflare R2 / LocalStack)
		  - S3_REGION / AWS_REGION / AWS_DEFAULT_REGION
		  - AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_SESSION_TOKEN
		  - S3_FORCE_PATH_STYLE=true (often required for MinIO)
		  - S3_VERIFY_SSL=false (or path to CA bundle)
		"""

		load_dotenv(override=False)

		bucket = (os.getenv("BUCKET_URL") or "").strip()
		if require_bucket and not bucket:
			raise ValueError("Missing required env var: S3_BUCKET")

		prefix = (os.getenv("S3_PREFIX") or "").strip().strip("/")
		endpoint_url = (os.getenv("BUCKET_URL") or "").strip() or None
		region = (
			(os.getenv("S3_REGION") or "").strip()
			or (os.getenv("AWS_REGION") or "").strip()
			or (os.getenv("AWS_DEFAULT_REGION") or "").strip()
			or None
		)

		access_key_id = (os.getenv("AWS_ACCESS_KEY_ID") or "").strip() or None
		secret_access_key = (os.getenv("AWS_SECRET_ACCESS_KEY") or "").strip() or None
		session_token = (os.getenv("AWS_SESSION_TOKEN") or "").strip() or None

		force_path_style = _env_bool("S3_FORCE_PATH_STYLE", default=False)

		verify_ssl_env = os.getenv("S3_VERIFY_SSL")
		verify_ssl: bool | str
		if verify_ssl_env is None:
			verify_ssl = True
		else:
			verify_ssl_env = verify_ssl_env.strip()
			if verify_ssl_env.lower() in {"0", "false", "no", "off"}:
				verify_ssl = False
			else:
				# allow a path to a CA bundle
				verify_ssl = verify_ssl_env

		return S3Config(
			bucket=bucket,
			prefix=prefix,
			region=region,
			endpoint_url=endpoint_url,
			access_key_id=access_key_id,
			secret_access_key=secret_access_key,
			session_token=session_token,
			force_path_style=force_path_style,
			verify_ssl=verify_ssl,
		)


class S3NewsUploader:
	"""Uploads `NewsRaw` items as JSON objects to an S3 (or S3-compatible) bucket."""

	def __init__(self, config: S3Config, *, s3_client: Any | None = None) -> None:
		self.config = config

		if s3_client is not None:
			self._client = s3_client
			return

		s3_kwargs: dict[str, Any] = {
			"region_name": config.region,
			"endpoint_url": config.endpoint_url,
			"aws_access_key_id": config.access_key_id,
			"aws_secret_access_key": config.secret_access_key,
			"aws_session_token": config.session_token,
			"verify": config.verify_ssl,
		}

		# Remove keys with None values to keep boto3 default credential chain working.
		s3_kwargs = {k: v for k, v in s3_kwargs.items() if v is not None}

		botoconfig = None
		if config.force_path_style:
			# botocore type stubs are stricter than runtime here.
			botoconfig = BotoConfig(s3=cast(Any, {"addressing_style": "path"}))
		if botoconfig is not None:
			s3_kwargs["config"] = botoconfig

		self._client = boto3.client("s3", **s3_kwargs)

	@staticmethod
	def from_env() -> "S3NewsUploader":
		return S3NewsUploader(S3Config.from_env())

	def _base_prefix(self) -> str:
		return self.config.prefix.strip("/")

	def build_news_key(self, news: NewsRaw) -> str:
		"""Partitioned key layout for better browsing / lifecycle policies."""

		published = news.published_at
		if published.tzinfo is None:
			published = published.replace(tzinfo=timezone.utc)
		published = published.astimezone(timezone.utc)

		date_part = published.date().isoformat()

		source = _clean_segment(news.source)
		symbol = _clean_segment(news.symbol)
		news_id = _clean_segment(news.id)

		key = f"news_raw/source={source}/symbol={symbol}/date={date_part}/{news_id}.json"
		p = self._base_prefix()
		return f"{p}/{key}" if p else key

	def ensure_bucket_exists(self, *, create_if_missing: bool = False) -> None:
		"""Optionally ensure the configured bucket exists.

		On AWS, creating buckets is region-sensitive. For many S3-compatible
		providers (MinIO/R2), `create_bucket` may behave differently.
		"""

		try:
			self._client.head_bucket(Bucket=self.config.bucket)
			return
		except ClientError as e:
			if not create_if_missing:
				raise
			code = str(e.response.get("Error", {}).get("Code", ""))
			if code not in {"404", "NoSuchBucket", "NotFound"}:
				raise

		kwargs: dict[str, Any] = {"Bucket": self.config.bucket}
		if self.config.region and self.config.region != "us-east-1":
			kwargs["CreateBucketConfiguration"] = {"LocationConstraint": self.config.region}
		self._client.create_bucket(**kwargs)

	def upload_one(self, news: NewsRaw, *, key: str | None = None) -> str:
		"""Upload a single NewsRaw item.

		Returns the S3 object key.
		"""

		object_key = key or self.build_news_key(news)

		metadata = {
			"source": str(news.source),
			"symbol": str(news.symbol),
			"news_id": str(news.id),
			"published_at": news.published_at.astimezone(timezone.utc).isoformat()
			if news.published_at.tzinfo
			else news.published_at.replace(tzinfo=timezone.utc).isoformat(),
		}

		self._client.put_object(
			Bucket=self.config.bucket,
			Key=object_key,
			Body=news.to_json_bytes(),
			ContentType="application/json",
			Metadata=metadata,
		)
		return object_key

	def upload_many(self, items: Iterable[NewsRaw]) -> int:
		n = 0
		for it in items:
			try:
				self.upload_one(it)
				n += 1
			except Exception:
				logger.exception("Failed to upload news id=%s symbol=%s", getattr(it, "id", ""), getattr(it, "symbol", ""))
		return n

