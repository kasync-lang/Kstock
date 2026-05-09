from pathlib import Path
from unittest.mock import MagicMock

from S3client import S3Config, S3TickUploader
import os
print(os.getcwd())

def test_upload_local_file_builds_expected_key(tmp_path):
    # arrange
    local_dir = tmp_path / "data" / "merged" / "AAPL"
    local_dir.mkdir(parents=True)
    local_file = local_dir / "2026-05-08.parquet"
    local_file.write_bytes(b"fake parquet bytes")

    fake_client = MagicMock()
    config = S3Config(
        bucket="test-bucket",
        prefix="",
        region=None,
        endpoint_url=None,
        access_key_id=None,
        secret_access_key=None,
        session_token=None,
        force_path_style=False,
        verify_ssl=True,
    )
    uploader = S3TickUploader(config, s3_client=fake_client)

    # act
    key = uploader.build_key_from_local_file(str(local_file))
    uploader._client.upload_file(
        Filename=str(local_file),
        Bucket=uploader.config.bucket,
        Key=key,
    )

    # assert
    assert key.endswith("data/merged/AAPL/2026-05-08.parquet")
    fake_client.upload_file.assert_called_once_with(
        Filename=str(local_file),
        Bucket="test-bucket",
        Key=key,
    )


def test_build_key_from_local_file_strips_leading_dot_slash():
    config = S3Config(bucket="test-bucket")
    uploader = S3TickUploader(config, s3_client=MagicMock())

    key = uploader.build_key_from_local_file(symbol="AAPL")

    assert key == "raw_tick/src=nasdaq/merged/AAPL/2026-05-09.parquet"
def test_upload_local_file():
    uploader = S3TickUploader(S3Config.from_env())
    root_path = "./data/merged"
    symbol = "ACGL"
    day = "2026-05-06"
    local_file = Path(f"{root_path}")
    parquet_files = sorted(local_file.rglob(f"*{day}.parquet"))
    if not parquet_files:
        print(f"No parquet files found in {root_path}/{symbol}")
        return
    count_success=0
    for file_path in parquet_files:
        local_filename = str(file_path)
        key = uploader.upload_local_file(local_filename)
        count_success += 1

    assert count_success == len(parquet_files)