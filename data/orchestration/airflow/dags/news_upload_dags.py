import json
from datetime import datetime, timezone
from typing import Iterable
import logging
import os

logger = logging.getLogger(__name__)
import pendulum
from airflow.sdk import get_current_context, dag, task

from api.api_news_ingester import APIGeter
from api.news_model import NewsRaw
from api.uploader import S3Uploader

# set time zone to New York
tz = pendulum.timezone("America/New_York")


@dag(
    dag_id="upload_news",
    schedule="20 1 * * *",
    default_args={
        "owner": "airflow",
        "depends_on_past": False,
        "start_date": pendulum.datetime(2026, 10, 1, tz=tz),

    },
    catchup=False
)
def upload_news():
    @task()
    def load_symbol():
        with open("/opt/airflow/data/list_symbol.txt", "r") as f:
            list_symbols = f.read().splitlines()
        return list_symbols

    @task()
    def ingest_news(symbol):
        context = get_current_context()
        api_getter = APIGeter()
        today = context['logical_date'].astimezone(timezone.utc).date()
        raw_items = api_getter.fetch_news_raw(symbol=symbol, from_date=today, to_date=today)
        symbol_path = os.path.join("/opt/airflow/data/news", symbol)
        os.makedirs(symbol_path, exist_ok=True)
        json_path = os.path.join(symbol_path, f"{today}.json")
        raws_item2 = [item.to_dict() for item in raw_items]
        with open(json_path, "w") as f:
            json.dump(raws_item2, f, ensure_ascii=False, indent=4)
        return json_path

    @task()
    def upload_news_to_S3_by_path(json_path: str):
        uploader = S3Uploader()
        key_name = uploader.upload_news_to_S3_by_path(json_path)
        logger.info(f"Uploaded {key_name}")

    symbols = load_symbol()
    raw_news = ingest_news.expand(symbol=symbols)
    upload_news_to_S3_by_path.expand(json_path=raw_news)


upload_news()
