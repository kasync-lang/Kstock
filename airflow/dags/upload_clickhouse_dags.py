import clickhouse_connect
from airflow.sdk import dag, task, get_current_context
import pendulum
from datetime import timedelta
import os

# time zone USA
tz = pendulum.timezone("America/New_York")


@dag(
    schedule="20 1 * * *",
    dag_id="upload_clickhouse",
    default_args={
        "owner": "kasync",
        "depends_on_past": False,
    },
    start_date=pendulum.datetime(2024, 6, 1, tz=tz),
    catchup=False
)
def test_upload_clickhouse():
    @task()
    def upload_to_clickhouse():
        context = get_current_context()
        logical_date = context['logical_date']
        process_date = logical_date.date() - timedelta(days=1)
        print(f"Processing date: {process_date}")
        client = clickhouse_connect.get_client(host=os.getenv('CLICKHOUSE_HOST', '192.168.2.100'),
                                               port=int(os.getenv('CLICKHOUSE_PORT', 8123)),
                                               username=os.getenv('CLICKHOUSE_USER', 'dev'),
                                               password=os.getenv('CLICKHOUSE_PASSWORD', 'dev_password'),
                                               database=os.getenv('CLICKHOUSE_DB', 'aggregate_db'))
        # Create the table if it doesn't exist
        data = [457, 'abc', 456.78]
        client.insert('test_table', [data], column_names=['key', 'value', 'metric'])

    upload_to_clickhouse()


test_upload_clickhouse()
