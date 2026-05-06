import os
from datetime import datetime

import pandas as pd
from google.cloud import bigquery, storage

from reverse_engineering.config import Config


def save_csv(df: pd.DataFrame, path: str) -> None:
    df.to_csv(path, index=False, encoding="utf-8")
    kb = os.path.getsize(path) / 1024
    print(f"CSV saved: {path}  ({len(df):,} rows, {kb:.1f} KB)")


def upload_gcs(config: Config, local_path: str) -> str:
    client = storage.Client(project=config.gcp_project_id)
    bucket = client.bucket(config.gcs_bucket_name)
    if not bucket.exists():
        bucket = client.create_bucket(config.gcs_bucket_name, location=config.bq_location)
        print(f"Created bucket: {config.gcs_bucket_name}")

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    blob_name = f"{config.gcs_folder}/coursera_courses_{ts}.csv"
    bucket.blob(blob_name).upload_from_filename(local_path, content_type="text/csv")

    uri = f"gs://{config.gcs_bucket_name}/{blob_name}"
    print(f"GCS upload: {uri}")
    return uri


def load_bigquery(config: Config, gcs_uri: str) -> str:
    client = bigquery.Client(project=config.gcp_project_id)
    full_ds = f"{config.gcp_project_id}.{config.bq_dataset}"
    table_id = f"{full_ds}.{config.bq_table}"

    try:
        client.get_dataset(full_ds)
    except Exception:
        ds = bigquery.Dataset(full_ds)
        ds.location = config.bq_location
        client.create_dataset(ds)
        print(f"Created dataset: {full_ds}")

    job = client.load_table_from_uri(
        gcs_uri,
        table_id,
        job_config=bigquery.LoadJobConfig(
            schema=config.bq_schema,
            source_format=bigquery.SourceFormat.CSV,
            skip_leading_rows=1,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
            allow_quoted_newlines=True,
            ignore_unknown_values=True,
        ),
    )
    job.result()

    rows = client.get_table(table_id).num_rows
    print(f"BigQuery loaded: {table_id}  ({rows:,} rows)")
    return table_id
