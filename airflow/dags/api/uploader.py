from datetime import timezone
from typing import Iterable

from pathlib import Path
import json
from api.news_model import NewsRaw

try:
    from airflow.providers.amazon.aws.hooks.base_aws import AwsBaseHook
except ModuleNotFoundError:  # pragma: no cover - keeps local imports testable
    AwsBaseHook = None


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
class S3Uploader:
    def __init__(self, aws_conn_id='upload_con_default', bucket='kstock-bucket-dev'):
        if AwsBaseHook is None:
            raise RuntimeError("apache-airflow-providers-amazon is required to upload files")
        hook = AwsBaseHook(aws_conn_id=aws_conn_id)
        session = hook.get_session()
        assert hook.conn_config.endpoint_url is not None
        self._client = session.client("s3", endpoint_url=hook.conn_config.endpoint_url)
        self.bucket = bucket
    def build_key_from_local_file(self, local_path: str) -> str:
        path = Path(local_path)
        key = path.as_posix().lstrip("./").split("data/")[-1]
        return f"raw_tick/src=nasdaq/{key}"

    def build_news_key_from_local_file(self, local_path: str, *, source: str = "finnhub") -> str:

        path = Path(local_path)
        key = path.as_posix().lstrip("./").split("data/news/")[-1]
        return f"news_raw/src=finnhub/{key}"

    def _base_prefix(self):
        return "news_raw"
    @staticmethod
    def from_connect() -> "S3Uploader":
        return S3Uploader(aws_conn_id='upload_con_default')


    def upload_local_file(self, local_file: str) -> str:
        key = self.build_key_from_local_file(local_file)
        self._client.upload_file(
            Filename=local_file,
            Bucket=self.bucket,
            Key=key,
        )
        return key

    def build_news_list_keys(self, news: Iterable[NewsRaw]) -> str:
        """Partitioned key layout for better browsing / lifecycle policies."""
        news_list = list(news)
        if not news_list:
            raise ValueError("news must not be empty")

        news0 = news_list[0]
        published = news0.published_at
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        published = published.astimezone(timezone.utc)

        date_part = published.date().isoformat()

        source = _clean_segment(news0.source)
        symbol = _clean_segment(news0.symbol)

        key = f"source={source}/symbol={symbol}/date={date_part}.json"
        p = self._base_prefix()
        return f"{p}/{key}" if p else key


    def upload_list(self, items: Iterable[NewsRaw], *, key: str | None = None) -> str | None:
        list_items = list(items)
        if not list_items:
            return
        news0 = list_items[0]
        list_objects_key = key or self.build_news_list_keys(list_items)
        metadata = {
            "source": str(news0.source),
            "symbol": str(news0.symbol),
            "published_at": news0.published_at.astimezone(timezone.utc).isoformat()
            if news0.published_at.tzinfo
            else news0.published_at.replace(tzinfo=timezone.utc).isoformat(),
        }
        list_news = [item.to_dict() for item in list_items]
        self._client.put_object(
            Bucket=self.bucket,
            Key=list_objects_key,
            Body=json.dumps(list_news).encode("utf-8"),
            ContentType="application/json",
            Metadata=metadata,
        )
        return list_objects_key
    def upload_news_to_S3_by_path(self, path:str):
        key = self.build_news_key_from_local_file(path)
        self._client.upload_file(
            Filename=path,
            Bucket=self.bucket,
            Key=key,
        )
        return key

