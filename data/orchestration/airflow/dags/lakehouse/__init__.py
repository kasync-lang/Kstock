"""Tick lakehouse: bronze -> silver -> gold layers and their data-quality checks.

Pure Python (pandas / pyarrow) so every rule can be unit-tested without Airflow.
"""
