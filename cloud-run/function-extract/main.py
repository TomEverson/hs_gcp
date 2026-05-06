"""
Cloud Run Function - Extract
=============================
Source  : Open Library API (https://openlibrary.org)
Trigger : HTTP POST (called by Cloud Scheduler)
Output  : Timestamped CSV to gs://<BUCKET>/books/raw/books_<ts>.csv

Env vars:
  GCS_BUCKET   - GCS bucket name
  GCP_PROJECT  - GCP project ID (optional if ADC is set)
  SUBJECTS     - comma-separated subjects (default: "programming,data science,machine learning")
  PAGE_LIMIT   - pages per subject (default: 5, 100 books/page)
"""

import csv
import io
import logging
import os
import time

import functions_framework
import requests
from datetime import datetime, timezone
from google.cloud import storage

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

GCS_BUCKET = os.environ.get("GCS_BUCKET", "")
GCP_PROJECT = os.environ.get("GCP_PROJECT", "")
SUBJECTS = [
    s.strip()
    for s in os.environ.get(
        "SUBJECTS", "programming,data science,machine learning"
    ).split(",")
]
PAGE_LIMIT = int(os.environ.get("PAGE_LIMIT", "5"))
PAGE_SIZE = 100
SLEEP_SEC = 0.5

BASE_URL = "https://openlibrary.org/search.json"
FIELDS = (
    "key,title,author_name,first_publish_year,publisher,"
    "isbn,subject,number_of_pages_median,language,cover_edition_key"
)
HEADERS = {
    "User-Agent": "etl-pipeline-homework/1.0 (educational)",
    "Accept": "application/json",
}

CSV_COLUMNS = [
    "book_id",
    "title",
    "authors",
    "first_publish_year",
    "publisher",
    "isbn",
    "subjects",
    "page_count",
    "languages",
    "cover_url",
    "search_subject",
    "extracted_at",
]


def fetch_page(subject: str, page: int) -> list[dict]:
    r = requests.get(
        BASE_URL,
        headers=HEADERS,
        params={
            "subject": subject,
            "fields": FIELDS,
            "limit": PAGE_SIZE,
            "page": page,
        },
        timeout=20,
    )
    r.raise_for_status()
    return r.json().get("docs", [])


def normalize(doc: dict, subject: str, ts: str) -> dict:
    cover = doc.get("cover_edition_key", "")
    return {
        "book_id": doc.get("key", "").replace("/works/", ""),
        "title": doc.get("title", ""),
        "authors": "; ".join(doc.get("author_name") or []),
        "first_publish_year": doc.get("first_publish_year", ""),
        "publisher": "; ".join((doc.get("publisher") or [])[:2]),
        "isbn": ((doc.get("isbn") or [""])[0]),
        "subjects": "; ".join((doc.get("subject") or [])[:5]),
        "page_count": doc.get("number_of_pages_median", ""),
        "languages": "; ".join(doc.get("language") or []),
        "cover_url": (
            f"https://covers.openlibrary.org/b/olid/{cover}-M.jpg" if cover else ""
        ),
        "search_subject": subject,
        "extracted_at": ts,
    }


def fetch_all() -> list[dict]:
    rows, seen = [], set()
    ts = datetime.now(timezone.utc).isoformat()

    for subject in SUBJECTS:
        log.info("Subject: '%s'", subject)
        for page in range(1, PAGE_LIMIT + 1):
            try:
                docs = fetch_page(subject, page)
                if not docs:
                    break
                for doc in docs:
                    key = doc.get("key", "")
                    if key and key not in seen:
                        seen.add(key)
                        rows.append(normalize(doc, subject, ts))
                log.info(
                    "  page %d -> +%d  (total %d unique)", page, len(docs), len(rows)
                )
                if len(docs) < PAGE_SIZE:
                    break
            except requests.HTTPError as exc:
                log.warning("  page %d failed: %s", page, exc)
            time.sleep(SLEEP_SEC)

    return rows


def to_csv_bytes(rows: list[dict]) -> bytes:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=CSV_COLUMNS, extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue().encode("utf-8")


def upload_gcs(data: bytes) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    blob_name = f"books/raw/books_{ts}.csv"
    client = storage.Client(project=GCP_PROJECT or None)
    blob = client.bucket(GCS_BUCKET).blob(blob_name)
    blob.upload_from_string(data, content_type="text/csv")
    uri = f"gs://{GCS_BUCKET}/{blob_name}"
    log.info("Uploaded -> %s (%d bytes)", uri, len(data))
    return uri


@functions_framework.http
def extract(request):
    """HTTP entry point - triggered by Cloud Scheduler."""
    log.info("extract() invoked")
    if not GCS_BUCKET:
        return {"error": "GCS_BUCKET not set"}, 500
    try:
        rows = fetch_all()
        if not rows:
            return {"status": "warning", "message": "No rows fetched"}, 200
        uri = upload_gcs(to_csv_bytes(rows))
        return {"status": "success", "rows": len(rows), "gcs_uri": uri}, 200
    except Exception as exc:
        log.exception("extract failed")
        return {"status": "error", "message": str(exc)}, 500
