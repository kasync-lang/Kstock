import os
import json
import pandas as pd
from glob import glob
from datetime import datetime


def merge_files(input_dir:str, output_path:str, list_symbols):
    for symbol in list_symbols:
        symbol_path = os.path.join(input_dir, symbol)
        if not os.path.exists(symbol_path):
            continue
        today = datetime.now().strftime("%Y-%m-%d")
        today_path = os.path.join(symbol_path, today)
        if not os.path.exists(today_path):
            continue
        output_dir = os.path.join(output_path,symbol)
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, f"{today}.csv")
        part_file = glob(os.path.join(today_path, "part-*.jsonl"))
        record = []
        for part in part_file:
            with open(part, 'r') as f:
                for line in f:
                    record.append(json.loads(line))
        if not record:
            continue
        df = pd.DataFrame(record)
        os.makedirs(output_dir, exist_ok=True)
        df.to_csv(output_file, index=False)
        print(f"Merged {len(record)} records for symbol {symbol} into {output_file}")

if __name__ == "__main__":
    RAW_PATH = './data/raw'
    OUTPUT_PATH = './data/merged'
    list_symbols= []
    with open('./list_symbol.txt', 'r') as f:
        for line in f:
            list_symbols.append(line.strip())
    assert len(list_symbols)>0
    merge_files(RAW_PATH, OUTPUT_PATH, list_symbols)