import clickhouse_connect
import dotenv
from dotenv import load_dotenv
import os
load_dotenv()


if __name__ == "__main__":
    clickhouse_clien = clickhouse_connect.get_client(
        host=os.getenv("CLICKHOUSE_HOST", "localhost"),
        port=int(os.getenv("CLICKHOUSE_PORT", "8123")),
        user=os.getenv("CLICKHOUSE_USER", "default"),
        password=os.getenv("CLICKHOUSE_PASSWORD", ""),
        database=os.getenv("CLICKHOUSE_DB", "default"),
    )

    try:
        result = clickhouse_clien.query("SELECT 1")
        print("ClickHouse connection successful:", result.result_rows)
    except Exception as e:
        print("ClickHouse connection failed:", str(e))