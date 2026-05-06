# Open Library ETL Pipeline

Event-driven ETL pipeline that extracts book data from the [Open Library API](https://openlibrary.org/developers/api), stores it in Google Cloud Storage, and automatically loads it into BigQuery. Deployed as two Cloud Run Functions with CI/CD via GitHub Actions and scheduled via Cloud Scheduler.

## Architecture

```
Cloud Scheduler (daily 02:00 UTC)
        |
        |  HTTP POST
        v
+-------------------+       CSV file       +---------------------------+
|   etl-extract     |  ----------------->  |   Google Cloud Storage    |
|  (Cloud Run Fn)   |                       |  gs://<bucket>/           |
|                   |                       |  books/raw/books_*.csv    |
|  Open Library API |                       +------------+--------------+
|  -> normalize     |                                    |
|  -> upload CSV    |                         GCS Finalize Event
+-------------------+                                    |
                                                         v
                                             +---------------------+
                                             |    etl-load         |
                                             |  (Cloud Run Fn)     |
                                             |                     |
                                             |  CSV -> BigQuery    |
                                             |  WRITE_APPEND       |
                                             +----------+----------+
                                                        |
                                                        v
                                             +---------------------+
                                             |      BigQuery       |
                                             |  open_library.books |
                                             +---------------------+
```

## Data Source

**Open Library API** - `https://openlibrary.org/search.json`

| Property | Value |
|---|---|
| Auth required | No |
| Rate limit | Polite (0.5s delay between pages) |
| Default subjects | `programming`, `data science`, `machine learning` |
| Records per run | ~1,500 (5 pages x 100 x 3 subjects) |

## Project Structure

```
.
├── function-extract/
│   ├── main.py                 # HTTP-triggered: fetch -> GCS
│   └── requirements.txt
├── function-load/
│   ├── main.py                 # GCS-triggered: CSV -> BigQuery
│   └── requirements.txt
├── scripts/
│   ├── setup.sh                # Create GCP resources (run once)
│   ├── deploy.sh               # Deploy both functions manually
│   └── create_scheduler.sh     # Create Cloud Scheduler job
├── .github/
│   └── workflows/
│       └── deploy.yml          # CI/CD: deploy on push to main
├── .gitignore
└── README.md
```

## Prerequisites

- GCP project with billing enabled
- `gcloud` CLI authenticated (`gcloud auth login`)
- Python 3.12+ (local testing only)
- GitHub repository with Actions enabled

## Quickstart

### 1. Clone and configure

```bash
git clone https://github.com/<your-username>/open-library-etl.git
cd open-library-etl

export GCP_PROJECT=your-project-id
export GCS_BUCKET=your-bucket-name
```

### 2. Bootstrap GCP resources (run once)

```bash
bash scripts/setup.sh
```

Creates: GCS bucket with lifecycle rules, service accounts, IAM bindings, BigQuery dataset.

### 3. Deploy functions

**Option A - GitHub Actions (recommended)**

Push to `main` and the workflow deploys automatically.

Required GitHub secrets/variables:

| Name | Where | Value |
|---|---|---|
| `WIF_PROVIDER` | Secret | Workload Identity Provider resource name |
| `WIF_SERVICE_ACCOUNT` | Secret | `etl-functions-sa@<project>.iam.gserviceaccount.com` |
| `GCP_PROJECT` | Variable | Your GCP project ID |
| `GCS_BUCKET` | Variable | Your bucket name |

**Option B - Manual**

```bash
bash scripts/deploy.sh
```

### 4. Create Cloud Scheduler job

```bash
bash scripts/create_scheduler.sh
```

Runs daily at 02:00 UTC. Trigger immediately:

```bash
gcloud scheduler jobs run etl-extract-daily --location=asia-southeast1
```

## Local Testing

```bash
cd function-extract
pip install -r requirements.txt
functions-framework --target=extract --debug
curl -X POST http://localhost:8080
```

## GitHub Actions - Workload Identity Federation

Keyless authentication (no JSON key files in GitHub secrets):

```bash
gcloud iam workload-identity-pools create "github-pool" \
  --project="$GCP_PROJECT" \
  --location="global" \
  --display-name="GitHub Actions Pool"

gcloud iam workload-identity-pools providers create-oidc "github-provider" \
  --project="$GCP_PROJECT" \
  --location="global" \
  --workload-identity-pool="github-pool" \
  --display-name="GitHub provider" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --issuer-uri="https://token.actions.githubusercontent.com"

export REPO="your-github-username/open-library-etl"
export WIF_POOL=$(gcloud iam workload-identity-pools describe github-pool \
  --location=global --format="value(name)")

gcloud iam service-accounts add-iam-policy-binding \
  "etl-functions-sa@$GCP_PROJECT.iam.gserviceaccount.com" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/$WIF_POOL/attribute.repository/$REPO"

gcloud iam workload-identity-pools providers describe github-provider \
  --location=global \
  --workload-identity-pool="github-pool" \
  --format="value(name)"
```

Add the output as the `WIF_PROVIDER` secret in your GitHub repo settings.

## BigQuery Queries

```sql
-- Latest run
SELECT * FROM `<project>.open_library.books`
WHERE DATE(extracted_at) = CURRENT_DATE()
ORDER BY title LIMIT 20;

-- Books per subject
SELECT search_subject, COUNT(*) AS total
FROM `<project>.open_library.books`
GROUP BY 1 ORDER BY 2 DESC;

-- Most prolific authors
SELECT authors, COUNT(*) AS books
FROM `<project>.open_library.books`
WHERE authors != ''
GROUP BY 1 ORDER BY 2 DESC LIMIT 10;

-- Average page count by subject
SELECT search_subject, ROUND(AVG(page_count), 0) AS avg_pages
FROM `<project>.open_library.books`
WHERE page_count > 0 GROUP BY 1;
```

## IAM Permissions

| Service Account | Role | Purpose |
|---|---|---|
| `etl-functions-sa` | `roles/storage.objectAdmin` | Read/write GCS |
| `etl-functions-sa` | `roles/bigquery.dataEditor` | Write to BQ tables |
| `etl-functions-sa` | `roles/bigquery.jobUser` | Run BQ load jobs |
| `etl-functions-sa` | `roles/eventarc.eventReceiver` | Receive GCS events |
| `etl-scheduler-sa` | `roles/run.invoker` | Invoke Cloud Run function |
