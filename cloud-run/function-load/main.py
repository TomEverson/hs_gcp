"""
Cloud Run Function - Load
==========================
Trigger : GCS Finalize event (new CSV in gs://<BUCKET>/books/raw/)
Action  : Load CSV into BigQuery table

Env vars:
  GCP_PROJECT  - GCP project ID
  BQ_DATASET   - BigQuery dataset (default: open_library)
  BQ_TABLE     - BigQuery table (default: books)
"""

import logging
import os

import functions_framework
from google.cloud import bigquery

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

GCP_PROJECT = os.environ.get("GCP_PROJECT", "")
BQ_DATASET = os.environ.get("BQ_DATASET", "open_library")
BQ_TABLE = os.environ.get("BQ_TABLE", "books")

BQ_SCHEMA = [
    bigquery.SchemaField("book_id", "STRING"),
    bigquery.SchemaField("title", "STRING"),
    bigquery.SchemaField("authors", "STRING"),
    bigquery.SchemaField("first_publish_year", "INTEGER"),
    bigquery.SchemaField("publisher", "STRING"),
    bigquery.SchemaField("isbn", "STRING"),
    bigquery.SchemaField("subjects", "STRING"),
    bigquery.SchemaField("page_count", "INTEGER"),
    bigquery.SchemaField("languages", "STRING"),
    bigquery.SchemaField("cover_url", "STRING"),
    bigquery.SchemaField("search_subject", "STRING"),
    bigquery.SchemaField("extracted_at", "TIMESTAMP"),
]


def load_to_bigquery(gcs_uri: str) -> str:
    client = bigquery.Client(project=GCP_PROJECT or None)
    full_ds = f"{GCP_PROJECT}.{BQ_DATASET}"
    table_id = f"{full_ds}.{BQ_TABLE}"

    try:
        client.get_dataset(full_ds)
    except Exception:
        ds = bigquery.Dataset(full_ds)
        ds.location = "US"
        client.create_dataset(ds)
        log.info("Created dataset: %s", full_ds)

    job_config = bigquery.LoadJobConfig(
        schema=BQ_SCHEMA,
        source_format=bigquery.SourceFormat.CSV,
        skip_leading_rows=1,
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        allow_quoted_newlines=True,
        ignore_unknown_values=True,
    )

    job = client.load_table_from_uri(gcs_uri, table_id, job_config=job_config)
    job.result()

    rows = client.get_table(table_id).num_rows
    log.info("BigQuery loaded: %s (%d rows)", table_id, rows)
    return table_id


@functions_framework.cloud_event
def load(cloud_event):
    """GCS-triggered entry point - loads CSV into BigQuery."""
    log.info("load() triggered by GCS event")

    data = cloud_event.data
    bucket = data.get("bucket", "")
    name = data.get("name", "")

    if not name.startswith("books/raw/") or not name.endswith(".csv"):
        log.info("Skipping non-CSV or wrong prefix: %s", name)
        return

    gcs_uri = f"gs://{bucket}/{name}"
    log.info("Processing: %s", gcs_uri)

    try:
        table_id = load_to_bigquery(gcs_uri)
        return {"status": "success", "table": table_id, "source": gcs_uri}
    except Exception as exc:
        log.exception("load failed")
        return {"status": "error", "message": str(exc), "source": gcs_uri}
