from __future__ import annotations

import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import boto3
from botocore.stub import Stubber

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fetch_news_s3 as m  # noqa: E402


class TestBuildObjectKey(unittest.TestCase):
    def test_default_layout(self) -> None:
        key = m.build_object_key(symbol="AAPL", date="2026-10-04")
        self.assertEqual(key, "news_raw/src=finnhub/AAPL/2026-10-04.json")

    def test_custom_source_and_prefix(self) -> None:
        key = m.build_object_key(
            source="finnhub", symbol="TSLA", date="2026-01-02", base_prefix="landing/raw"
        )
        self.assertEqual(key, "landing/raw/src=finnhub/TSLA/2026-01-02.json")

    def test_empty_prefix(self) -> None:
        key = m.build_object_key(symbol="MSFT", date="2026-03-09", base_prefix="")
        self.assertEqual(key, "src=finnhub/MSFT/2026-03-09.json")

    def test_missing_symbol_raises(self) -> None:
        with self.assertRaises(ValueError):
            m.build_object_key(symbol="", date="2026-10-04")


class TestResolveOutputPath(unittest.TestCase):
    def test_default_root_is_script_folder(self) -> None:
        dest = m.resolve_output_path(key="news_raw/src=finnhub/AAPL/2026-10-04.json")
        self.assertEqual(
            dest,
            (m.DEFAULT_OUTPUT_ROOT / "news_raw/src=finnhub/AAPL/2026-10-04.json").resolve(),
        )

    def test_explicit_file_path(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "out.json"
            dest = m.resolve_output_path(key="k/x.json", output=str(target))
            self.assertEqual(dest, target.resolve())

    def test_existing_directory_appends_key(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            dest = m.resolve_output_path(key="news_raw/src=finnhub/AAPL/2026-10-04.json", output=td)
            self.assertEqual(
                dest,
                (Path(td) / "news_raw/src=finnhub/AAPL/2026-10-04.json").resolve(),
            )

    def test_trailing_separator_treated_as_directory(self) -> None:
        dest = m.resolve_output_path(key="news_raw/a.json", output="landing/")
        self.assertTrue(str(dest).endswith("/news_raw/a.json"))


class TestDownloadAndMain(unittest.TestCase):
    @staticmethod
    def _client() -> object:
        return boto3.client(
            "s3",
            region_name="us-east-1",
            aws_access_key_id="x",
            aws_secret_access_key="y",
        )

    def test_download_object_writes_bytes_and_refuses_overwrite(self) -> None:
        client = self._client()
        stubber = Stubber(client)
        payload = b'[{"id": "1"}]'
        stubber.add_response(
            "get_object",
            {"Body": io.BytesIO(payload)},
            {"Bucket": "bkt", "Key": "news_raw/src=finnhub/AAPL/2026-10-04.json"},
        )

        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / "2026-10-04.json"
            with stubber:
                written = m.download_object(
                    client,
                    bucket="bkt",
                    key="news_raw/src=finnhub/AAPL/2026-10-04.json",
                    dest=dest,
                )
            self.assertEqual(written, len(payload))
            self.assertEqual(dest.read_bytes(), payload)
            self.assertFalse((Path(td) / "2026-10-04.json.part").exists())
            with self.assertRaises(FileExistsError):
                m.download_object(
                    client,
                    bucket="bkt",
                    key="news_raw/src=finnhub/AAPL/2026-10-04.json",
                    dest=dest,
                )

    def test_main_downloads_to_explicit_output(self) -> None:
        client = self._client()
        stubber = Stubber(client)
        payload = b'[{"id": "42"}]'
        stubber.add_response(
            "get_object",
            {"Body": io.BytesIO(payload)},
            {"Bucket": "bkt", "Key": "news_raw/src=finnhub/AAPL/2026-10-04.json"},
        )

        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "AAPL-2026-10-04.json"
            with stubber, mock.patch.object(m.boto3, "client", return_value=client):
                rc = m.main(
                    [
                        "--bucket", "bkt",
                        "--access-key-id", "x",
                        "--secret-access-key", "y",
                        "--symbol", "AAPL",
                        "--date", "2026-10-04",
                        "--output", str(target),
                        "--validate-json",
                    ]
                )
            self.assertEqual(rc, m.EXIT_OK)
            self.assertEqual(target.read_bytes(), payload)

    def test_main_list_mode(self) -> None:
        client = self._client()
        stubber = Stubber(client)
        stubber.add_response(
            "list_objects_v2",
            {
                "Contents": [
                    {"Key": "news_raw/src=finnhub/AAPL/2026-10-03.json"},
                    {"Key": "news_raw/src=finnhub/AAPL/2026-10-04.json"},
                ],
                "KeyCount": 2,
                "IsTruncated": False,
            },
            {"Bucket": "bkt", "Prefix": "news_raw/src=finnhub/AAPL/"},
        )

        with stubber, mock.patch.object(m.boto3, "client", return_value=client):
            rc = m.main(
                [
                    "--bucket", "bkt",
                    "--access-key-id", "x",
                    "--secret-access-key", "y",
                    "--symbol", "AAPL",
                    "--list",
                ]
            )
        self.assertEqual(rc, m.EXIT_OK)


if __name__ == "__main__":
    unittest.main()
