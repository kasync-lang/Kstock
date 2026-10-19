import os
import json
import pandas as pd
from glob import glob
from datetime import datetime, timezone
import pyarrow as pa
import pyarrow.parquet as pq


def merge_files(input_dir:str, output_path:str, list_symbols):
    batch_size = 10000  # Process records in batches to minimize RAM usage

    for symbol in list_symbols:
        symbol_path = os.path.join(input_dir, symbol)
        if not os.path.exists(symbol_path):
            continue
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        today_path = os.path.join(symbol_path, today)
        if not os.path.exists(today_path):
            continue
        output_dir = os.path.join(output_path, symbol)
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


if __name__ == "__main__":
    RAW_PATH = './data/raw'
    OUTPUT_PATH = './data/merged'
    list_symbols= []
    with open('list_symbol.txt', 'r') as f:
        for line in f:
            list_symbols.append(line.strip())
    assert len(list_symbols)>0
    merge_files(RAW_PATH, OUTPUT_PATH, list_symbols)