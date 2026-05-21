from datetime import datetime
from airflow import DAG
from airflow.operators.python import PythonOperator

def hello():
    print("hello airflow")

with DAG(
    dag_id="learning_dag",
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,
) as dag:

    t1 = PythonOperator(
        task_id="hello_task",
        python_callable=hello,
    )