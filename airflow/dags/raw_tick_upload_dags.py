from typing import cast
from datetime import timedelta
from airflow.sdk import dag, task
from api.uploader import S3Uploader
import os
from datetime import timezone, datetime
from glob import glob
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import clickhouse_connect
import json
from airflow.sdk import get_current_context
import pendulum

tz_US = pendulum.timezone("America/New_York")


@dag(
    schedule="20 1 * * *",
    dag_id="upload_raw_tick",
    default_args={
        "owner": "kasync",
        "depends_on_past": False,

    },
    start_date=pendulum.datetime(2025, 10, 1, tz=tz_US),
    catchup=False

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
        process_date = logical_date.subtract(days=1)
        yesterday = process_date.astimezone(tz=tz_US).strftime("%Y-%m-%d")
        today_path = os.path.join(symbol_path, yesterday)
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
        logical_date = context['logical_date']
        process_date = logical_date.subtract(days=1)
        yesterday = process_date.astimezone(tz=tz_US).strftime("%Y-%m-%d")
        today_path = os.path.join(symbol_path, yesterday)
        output_dir = os.path.join(OUTPUT_PATH, symbol)
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, f"{yesterday}.parquet")
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

    @task()
    def aggregate_and_upload_to_clickhouse(output_file):
        # Placeholder for aggregation and upload logic
        print(output_file)
        table = pq.read_table(output_file)
        df = table.to_pandas()
        # Perform aggregation (example: count records per symbol)
        volume = df['v'].sum()
        open_price = df['p'].iloc[0] if not df.empty else None
        close_price = df['p'].iloc[-1] if not df.empty else None
        high_price = df['p'].max() if not df.empty else None
        low_price = df['p'].min() if not df.empty else None
        context = get_current_context()
        process_date = context['logical_date'].subtract(days=1)
        timestampss = process_date.astimezone(tz=tz_US)

        aggregated_data = [df['s'].iloc[0], timestampss, open_price, high_price, low_price, close_price, volume]

        client = clickhouse_connect.get_client(host=os.getenv('CLICKHOUSE_HOST', '192.168.2.100'),
                                               port=int(os.getenv('CLICKHOUSE_PORT', 8123)),
                                               username=os.getenv('CLICKHOUSE_USER', 'dev'),
                                               password=os.getenv('CLICKHOUSE_PASSWORD', 'dev_password'),
                                               database=os.getenv('CLICKHOUSE_DB', 'aggregate_db'))
        # Insert aggregated data into ClickHouse
        client.insert('ohlcv_1d', [aggregated_data],
                      column_names=['symbol', 'timestamp', 'open', 'high', 'low', 'close', 'volume'])
        pass

    symbol_list = load_symbol()
    valid_symbols = get_valid_symbol(symbol_list)
    merged = merge_files.expand(symbol=valid_symbols)
    upload_raw_tick.expand(output_file=merged)
    aggregate_and_upload_to_clickhouse.expand(output_file=merged)


task_flow_upload_file()


@dag(
    schedule="20 1 * * *",
    dag_id="upload_raw_tick_test",
    default_args={
        "owner": "kasync",
        "depends_on_past": False,

    },
    start_date=pendulum.datetime(2025, 10, 1, tz=tz_US),
    catchup=False

)
def task_flow_upload_file_test():
    @task()
    def load_symbol():
        with open("/opt/airflow/data/list_symbol.txt", "r") as f:
            list_symbols = f.read().splitlines()
        return ['AAPL']  # Return a specific symbol for testing

    @task()
    def file1_exists_before_merge(symbol):
        context = get_current_context()
        symbol_path = os.path.join("/opt/airflow/data/raw", symbol)
        if not os.path.exists(symbol_path):
            return False
        logical_date = context['logical_date']
        process_date = logical_date.subtract(days=1)
        yesterday = process_date.astimezone(tz=tz_US).strftime("%Y-%m-%d")
        today_path = os.path.join(symbol_path, yesterday)
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
        logical_date = context['logical_date']
        process_date = logical_date.subtract(days=1)
        yesterday = process_date.astimezone(tz=tz_US).strftime("%Y-%m-%d")
        today_path = os.path.join(symbol_path, yesterday)
        output_dir = os.path.join(OUTPUT_PATH, symbol)
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, f"{yesterday}.parquet")
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

    @task()
    def aggregate_and_upload_to_clickhouse(output_file):
        # Placeholder for aggregation and upload logic
        table = pq.read_table(output_file)
        df = table.to_pandas()
        # Perform aggregation (example: count records per symbol)
        volume = df['v'].sum()
        open_price = df['p'].iloc[0] if not df.empty else None
        close_price = df['p'].iloc[-1] if not df.empty else None
        high_price = df['p'].max() if not df.empty else None
        low_price = df['p'].min() if not df.empty else None
        context = get_current_context()
        process_date = context['logical_date'].subtract(days=1)
        timestampss = process_date.astimezone(tz=tz_US)

        aggregated_data = [df['s'].iloc[0], timestampss, open_price, high_price, low_price, close_price, volume]

        client = clickhouse_connect.get_client(host=os.getenv('CLICKHOUSE_HOST', '192.168.2.100'),
                                               port=int(os.getenv('CLICKHOUSE_PORT', 8123)),
                                               username=os.getenv('CLICKHOUSE_USER', 'dev'),
                                               password=os.getenv('CLICKHOUSE_PASSWORD', 'dev_password'),
                                               database=os.getenv('CLICKHOUSE_DB', 'aggregate_db'))
        # Insert aggregated data into ClickHouse

        client.insert('ohlcv_1d', [aggregated_data],
                      column_names=['symbol', 'timestamp', 'open', 'high', 'low', 'close', 'volume'])
        client.close()
        pass

    symbol_list = load_symbol()
    valid_symbols = get_valid_symbol(symbol_list)
    merged = merge_files.expand(symbol=valid_symbols)
    upload_raw_tick.expand(output_file=merged)
    aggregate_and_upload_to_clickhouse.expand(output_file=merged)


task_flow_upload_file_test()
