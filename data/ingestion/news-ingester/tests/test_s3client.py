from __future__ import annotations

import unittest
from datetime import datetime, timezone

import boto3
from botocore.stub import Stubber

from ingestion.model.news_model import NewsRaw
from ingestion.producer.s3client import S3Config, S3NewsUploader


class TestS3NewsUploader(unittest.TestCase):
    def test_build_news_key_partitioned(self) -> None:
        cfg = S3Config(bucket="kstock-bucket-dev", prefix="my-prefix")
        uploader = S3NewsUploader(cfg, s3_client=object())  # client not used for key building

        news = NewsRaw(
            id="abc123",
            source="finnhub",
            title="t",
            content="c",
            url="https://example.com",
            symbol="AAPL",
            published_at=datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc),
        )
        key = uploader.build_news_key(news)
        self.assertEqual(key, "my-prefix/news_raw/source=finnhub/symbol=AAPL/date=2026-05-01/abc123.json")

    def test_upload_one_put_object(self) -> None:
        # Use a real boto3 client but stub requests.
        client = boto3.client("s3", region_name="us-east-1")
        stubber = Stubber(client)

        cfg = S3Config(bucket="kstock-bucket-dev", prefix="")
        uploader = S3NewsUploader(cfg, s3_client=client)

        published = datetime(2026, 5, 2, 1, 2, 3, tzinfo=timezone.utc)
        news = NewsRaw(
            id="deadbeef",
            source="finnhub",
            title="headline",
            content="summary",
            url="https://example.com/x",
            symbol="TSLA",
            published_at=published,
        )

        expected_key = "news_raw/source=finnhub/symbol=TSLA/date=2026-05-02/deadbeef.json"
        expected_params = {
            "Bucket": "kstock-bucket-dev",
            "Key": expected_key,
            "Body": news.to_json_bytes(),
            "ContentType": "application/json",
            "Metadata": {
                "source": "finnhub",
                "symbol": "TSLA",
                "news_id": "deadbeef",
                "published_at": published.isoformat(),
            },
        }

        stubber.add_response("put_object", service_response={}, expected_params=expected_params)
        with stubber:
            out_key = uploader.upload_one(news)

        self.assertEqual(out_key, expected_key)
    def test_upload_one_list_symbol(self) -> None:
        # Test that symbols with special characters are cleaned in the key.
        cfg = S3Config(bucket="kstock-bucket-dev", prefix="")
        uploader = S3NewsUploader.from_env()  # client not used for key building

        news1 = NewsRaw(
            id="id123",
            source="finnhub",
            title="t",
            content="c",
            url="https://example.com",
            symbol="BRK_B",  # dot should be cleaned
            published_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
        )
        news2 = NewsRaw(
            id="id1234",
            source="finnhub",
            title="t2",
            content="c",
            url="https://example.com",
            symbol="BRK_B",
            published_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
        )
        list_news = [news1, news2]
        key = uploader.build_news_list_keys(list_news)
        out_key = uploader.upload_list(list_news)
        self.assertEqual(out_key, "news_raw/source=finnhub/symbol=BRK_B/date=2026-05-01.json")


if __name__ == "__main__":
    unittest.main()

