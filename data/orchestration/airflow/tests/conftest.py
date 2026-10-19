import os
import sys

# DAG modules import each other as top-level packages, like inside /opt/airflow/dags
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "dags"))
