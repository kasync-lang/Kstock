from airflow.sdk import dag, task
from api.uploader import S3Uploader
import os
from datetime import  timezone
from glob import glob
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

import json
from airflow.sdk import get_current_context


@dag(
    schedule=None,
    dag_id="upload_raw_tick",
    default_args = {
        "owner": "kasync",
        "depends_on_past": False,

    },
)
def task_flow_upload_file():

    @task()
    def load_symbol():
        with open("/opt/airflow/data/list_symbol.txt", "r") as f:
            list_symbols = f.read().splitlines()
        return list_symbols
    @task()
    def file1_exists_before_merge(symbol):
        context = get_current_context()
        symbol_path = os.path.join("/opt/airflow/data/raw", symbol)
        if not os.path.exists(symbol_path):
            return False
        logical_date = context['logical_date']
        today = logical_date.astimezone(timezone.utc).strftime("%Y-%m-%d")
        today_path = os.path.join(symbol_path, today)
        if not os.path.exists(today_path):
            return False
        return True
    @task()
    def get_valid_symbol(symbols):
        result = []
        for symbol in symbols:
            if file1_exists_before_merge(symbol):
                result.append(symbol)
        return result
    @task()
    def merge_files(symbol):
        context = get_current_context()
        batch_size = 10000
        symbol_path = os.path.join("/opt/airflow/data/raw", symbol)
        OUTPUT_PATH = "/opt/airflow/data/merged"
        today = context['logical_date'].astimezone(timezone.utc).strftime("%Y-%m-%d")
        today_path = os.path.join(symbol_path, today)
        output_dir = os.path.join(OUTPUT_PATH, symbol)
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, f"{today}.parquet")
        part_file = glob(os.path.join(today_path, "part-*.jsonl"))

        writer = None
        schema = None
        total_records = 0
        batch = []

        for part in part_file:
            with open(part, 'r') as f:
                for line in f:
                    record = json.loads(line)
                    batch.append(record)
                    total_records += 1

                    # Write batch to parquet when it reaches batch_size
                    if len(batch) >= batch_size:
                        df_batch = pd.DataFrame(batch)
                        if writer is None:
                            schema = pa.Table.from_pandas(df_batch).schema
                            writer = pq.ParquetWriter(output_file, schema)

                        table = pa.Table.from_pandas(df_batch)
                        writer.write_table(table)
                        batch = []

        # Write remaining records
        if batch:
            df_batch = pd.DataFrame(batch)
            if writer is None:
                schema = pa.Table.from_pandas(df_batch).schema
                writer = pq.ParquetWriter(output_file, schema)

            table = pa.Table.from_pandas(df_batch)
            writer.write_table(table)

        if writer is not None:
            writer.close()
            print(f"Merged {total_records} records for symbol {symbol} into {output_file}")
        return output_file
    @task()
    def upload_raw_tick(output_file):
        uploader = S3Uploader()
        uploader.upload_local_file(output_file)

    symbol_list = load_symbol()
    valid_symbols = get_valid_symbol(symbol_list)
    merged = merge_files.expand(symbol=valid_symbols)
    upload_raw_tick.expand(output_file=merged)




task_flow_upload_file()