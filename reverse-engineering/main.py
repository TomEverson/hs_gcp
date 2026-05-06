import json
import os
import time
from datetime import datetime

import pandas as pd
import requests
from google.cloud import bigquery, storage
from tqdm import tqdm

# ─────────────────────────────────────────────────────────────────
# CONFIGURATION  ← fill these in before running
# ─────────────────────────────────────────────────────────────────
GCP_PROJECT_ID = "data-engineering-hs"
GCS_BUCKET_NAME = "de-hs-ws-bucket"
GCS_FOLDER = "coursera/raw"
BQ_DATASET = "coursera_data"
BQ_TABLE = "courses"
BQ_LOCATION = "US"

TOTAL_PAGES = 10  # pages to fetch (100 courses each)
SLEEP_BETWEEN = 1.2  # seconds between requests
CSV_FILENAME = "coursera_courses.csv"

# ─────────────────────────────────────────────────────────────────
# API CONSTANTS  (reverse-engineered from DevTools)
# ─────────────────────────────────────────────────────────────────
GRAPHQL_URL = "https://www.coursera.org/graphql-gateway/v2"
# Public REST API lives on api.coursera.org, not www.coursera.org
COURSES_V1_URL = "https://api.coursera.org/api/courses.v1"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
}

# Headers used only for the internal GraphQL endpoint
GRAPHQL_HEADERS = {
    **HEADERS,
    "Content-Type": "application/json",
    "X-Coursera-Application-Name": "browse",
    "Referer": "https://www.coursera.org/browse",
    "Origin": "https://www.coursera.org",
}

GRAPHQL_QUERY = """
query DiscoveryCollections(
  $contextType: String
  $contextId: String
  $start: Int
  $limit: Int
) {
  DiscoveryCollections(
    input: {
      contextType: $contextType
      contextId: $contextId
      start: $start
      limit: $limit
    }
  ) {
    elements {
      id
      label
      productType
      slug
      name
      tagline
      averageFiveStarRating
      ratingCount
      enrolledCount
      photoUrl
      difficultyLevel
      isCourseFree
      partners { id name shortName }
    }
    paging { total next }
  }
}
"""

COURSES_V1_FIELDS = (
    "id,name,slug,photoUrl,courseStatus,startDate,workload,"
    "previewLink,isGeorestricted,partnerIds,"
    "primaryLanguages,subtitleLanguages,certificates,description"
)

BQ_SCHEMA = [
    bigquery.SchemaField("course_id", "STRING"),
    bigquery.SchemaField("name", "STRING"),
    bigquery.SchemaField("slug", "STRING"),
    bigquery.SchemaField("description", "STRING"),
    bigquery.SchemaField("course_status", "STRING"),
    bigquery.SchemaField("workload", "STRING"),
    bigquery.SchemaField("start_date", "STRING"),
    bigquery.SchemaField("primary_languages", "STRING"),
    bigquery.SchemaField("subtitle_languages", "STRING"),
    bigquery.SchemaField("certificates", "STRING"),
    bigquery.SchemaField("partner_ids", "STRING"),
    bigquery.SchemaField("partner_count", "INTEGER"),
    bigquery.SchemaField("photo_url", "STRING"),
    bigquery.SchemaField("preview_link", "STRING"),
    bigquery.SchemaField("is_georestricted", "BOOLEAN"),
    bigquery.SchemaField("extracted_at", "TIMESTAMP"),
]


# ─────────────────────────────────────────────────────────────────
# 1. FETCH  (REST v1 – easiest to paginate)
# ─────────────────────────────────────────────────────────────────
def fetch_page(start: int = 0, limit: int = 100) -> dict:
    """One page from the public REST v1 courses endpoint."""
    resp = requests.get(
        COURSES_V1_URL,
        headers=HEADERS,
        params={
            "fields": COURSES_V1_FIELDS,
            "start": start,
            "limit": limit,
            "includes": "partnerIds",
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def graphql_sample(start: int = 0, limit: int = 12) -> dict:
    """
    One request to the GraphQL gateway (kept for demonstration).
    Discovered by: DevTools → Network → filter 'graphql' on coursera.org/browse
    """
    resp = requests.post(
        GRAPHQL_URL,
        headers=GRAPHQL_HEADERS,
        params={"opname": "DiscoveryCollections"},
        json={
            "operationName": "DiscoveryCollections",
            "variables": {
                "contextType": "TOPIC",
                "contextId": "data-science",
                "start": start,
                "limit": limit,
            },
            "query": GRAPHQL_QUERY,
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_all_courses(total_pages: int = 10, page_size: int = 100) -> list[dict]:
    """Paginate through REST v1 and return raw records."""
    all_courses, errors = [], []

    with tqdm(total=total_pages, desc="Fetching pages") as bar:
        for page in range(total_pages):
            try:
                data = fetch_page(start=page * page_size, limit=page_size)
                elements = data.get("elements", [])
                all_courses.extend(elements)
                bar.set_postfix(total=len(all_courses))
                if len(elements) < page_size:
                    print(f"\n  Last page at {page} ({len(elements)} items)")
                    bar.update(1)
                    break
            except requests.HTTPError as exc:
                errors.append((page, str(exc)))
                print(f"\n  Page {page} failed: {exc}")
            finally:
                bar.update(1)
                time.sleep(SLEEP_BETWEEN)

    print(f"Fetched {len(all_courses)} courses | {len(errors)} errors")
    return all_courses


# ─────────────────────────────────────────────────────────────────
# 2. TRANSFORM
# ─────────────────────────────────────────────────────────────────
def normalize(course: dict) -> dict:
    partner_ids = course.get("partnerIds", [])
    return {
        "course_id": course.get("id", ""),
        "name": course.get("name", ""),
        "slug": course.get("slug", ""),
        "description": (course.get("description") or "")[:500],
        "course_status": course.get("courseStatus", ""),
        "workload": course.get("workload", ""),
        "start_date": course.get("startDate", ""),
        "primary_languages": ", ".join(course.get("primaryLanguages", [])),
        "subtitle_languages": ", ".join(course.get("subtitleLanguages", [])),
        "certificates": ", ".join(course.get("certificates", [])),
        "partner_ids": ", ".join(str(p) for p in partner_ids),
        "partner_count": len(partner_ids),
        "photo_url": course.get("photoUrl", ""),
        "preview_link": course.get("previewLink", ""),
        "is_georestricted": course.get("isGeorestricted", False),
        "extracted_at": datetime.utcnow().isoformat() + "Z",
    }


def build_dataframe(raw: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame([normalize(c) for c in raw])
    before = len(df)
    df.drop_duplicates(subset="course_id", inplace=True)
    print(f"Dedup: {before} → {len(df)} rows")
    return df


# ─────────────────────────────────────────────────────────────────
# 3. CSV
# ─────────────────────────────────────────────────────────────────
def save_csv(df: pd.DataFrame, path: str) -> None:
    df.to_csv(path, index=False, encoding="utf-8")
    kb = os.path.getsize(path) / 1024
    print(f"CSV saved: {path}  ({len(df):,} rows, {kb:.1f} KB)")


# ─────────────────────────────────────────────────────────────────
# 4. GCS UPLOAD
# ─────────────────────────────────────────────────────────────────
def upload_gcs(local_path: str) -> str:
    """Upload CSV to GCS, return gs:// URI."""
    client = storage.Client(project=GCP_PROJECT_ID)
    bucket = client.bucket(GCS_BUCKET_NAME)
    if not bucket.exists():
        bucket = client.create_bucket(GCS_BUCKET_NAME, location=BQ_LOCATION)
        print(f"Created bucket: {GCS_BUCKET_NAME}")

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    blob_name = f"{GCS_FOLDER}/coursera_courses_{ts}.csv"
    bucket.blob(blob_name).upload_from_filename(local_path, content_type="text/csv")

    uri = f"gs://{GCS_BUCKET_NAME}/{blob_name}"
    print(f"GCS upload: {uri}")
    return uri


# ─────────────────────────────────────────────────────────────────
# 5. BIGQUERY LOAD
# ─────────────────────────────────────────────────────────────────
def load_bigquery(gcs_uri: str) -> str:
    """Load GCS CSV into BigQuery, return full table ref."""
    client = bigquery.Client(project=GCP_PROJECT_ID)
    full_ds = f"{GCP_PROJECT_ID}.{BQ_DATASET}"
    table_id = f"{full_ds}.{BQ_TABLE}"

    # Create dataset if needed
    try:
        client.get_dataset(full_ds)
    except Exception:
        ds = bigquery.Dataset(full_ds)
        ds.location = BQ_LOCATION
        client.create_dataset(ds)
        print(f"Created dataset: {full_ds}")

    job = client.load_table_from_uri(
        gcs_uri,
        table_id,
        job_config=bigquery.LoadJobConfig(
            schema=BQ_SCHEMA,
            source_format=bigquery.SourceFormat.CSV,
            skip_leading_rows=1,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
            allow_quoted_newlines=True,
            ignore_unknown_values=True,
        ),
    )
    job.result()  # wait

    rows = client.get_table(table_id).num_rows
    print(f"BigQuery loaded: {table_id}  ({rows:,} rows)")
    return table_id


# ─────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────
def main():
    print("=" * 55)
    print("  HW06 — Coursera API Extraction")
    print("=" * 55)

    # (A) Demo GraphQL call
    print("\n[1/5] GraphQL sample request (DevTools-discovered)...")
    try:
        gql_data = graphql_sample(start=0, limit=3)
        elements = (
            gql_data.get("data", {}).get("DiscoveryCollections", {}).get("elements", [])
        )
        print(f"  GraphQL returned {len(elements)} sample elements")
        if elements:
            print(f"  First: {elements[0].get('name')} | {elements[0].get('slug')}")
    except Exception as exc:
        print(f"  GraphQL demo skipped: {exc}")

    # (B) Bulk REST fetch
    print("\n[2/5] Bulk fetch via REST v1 API...")
    raw = fetch_all_courses(total_pages=TOTAL_PAGES)

    # (C) Transform
    print("\n[3/5] Normalizing & building DataFrame...")
    df = build_dataframe(raw)
    if df.empty:
        print("  No courses fetched – all pages failed. Check network/auth.")
        return
    print(
        df[["course_id", "name", "course_status", "primary_languages"]]
        .head(5)
        .to_string()
    )

    # (D) CSV
    print("\n[4/5] Saving CSV...")
    save_csv(df, CSV_FILENAME)

    # (E) GCS + BigQuery
    print("\n[5/5] Uploading to GCS & BigQuery...")
    if GCP_PROJECT_ID == "YOUR_PROJECT_ID":
        print("  ⚠️  GCP_PROJECT_ID not set – skipping cloud upload.")
        print("  Update the config at the top of this file and rerun.")
    else:
        gcs_uri = upload_gcs(CSV_FILENAME)
        table_id = load_bigquery(gcs_uri)
        print(f"\n  Query your data:")
        print(f"  SELECT * FROM `{table_id}` LIMIT 10")

    print("\n✅ Done.")


if __name__ == "__main__":
    main()
