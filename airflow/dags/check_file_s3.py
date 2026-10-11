from airflow.sdk import dag, task

from airflow.providers.amazon.aws.hooks.base_aws import AwsBaseHook


@dag(
    schedule="20 1 * * *",
    dag_id="check_connect_s3",
    default_args={
        "owner": "kasync",
        "depends_on_past": False,
    },
    catchup=False
)
def test_s3_connection():
    @task()
    def check_s3_connection(aws_conn_id='upload_con_default'):
        hook = AwsBaseHook(aws_conn_id=aws_conn_id)
        session = hook.get_session()
        client = session.client("s3", endpoint_url=hook.conn_config.endpoint_url)
        response = client.list_objects_v2(Bucket='kstock-bucket-dev')
        if 'Contents' in response:
            for obj in response['Contents']:
                print(obj['Key'])  # Prints the file path/name
        else:
            print("The bucket is empty.")

    check_s3_connection()


test_s3_connection()
