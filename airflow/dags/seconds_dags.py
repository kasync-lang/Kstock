import datetime
from airflow.sdk import dag, task
from airflow.providers.docker.operators.docker import DockerOperator

@dag(
    dag_id="docker_dag",
    default_args={"owner": "airflow"},
    schedule=None,
    tags=["learning_dag"],

)
def docker_taskflow_api():
    @task
    def python_task():
        print("python_task")
        print("hello docker")
    @task
    def docker_task():
        hello_task = DockerOperator(
            task_id="python_task",
            image = "hello-world:latest",
            command=None,
            docker_url="unix://var/run/docker.sock",
            auto_remove="force"
        )