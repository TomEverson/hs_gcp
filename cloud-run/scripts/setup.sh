#!/usr/bin/env bash
# =============================================================================
# setup.sh — Bootstrap all GCP resources needed for the ETL pipeline
#
# Usage:
#   export GCP_PROJECT=your-project-id
#   export GCS_BUCKET=your-bucket-name     # must be globally unique
#   bash scripts/setup.sh
# =============================================================================
set -euo pipefail

GCP_PROJECT=${GCP_PROJECT:?Set GCP_PROJECT}
GCS_BUCKET=${GCS_BUCKET:?Set GCS_BUCKET}
REGION=${REGION:-asia-southeast1}
BQ_DATASET=${BQ_DATASET:-open_library}
SCHEDULER_SA="etl-scheduler-sa"
FUNCTIONS_SA="etl-functions-sa"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " ETL Pipeline Setup"
echo " Project : $GCP_PROJECT"
echo " Bucket  : $GCS_BUCKET"
echo " Region  : $REGION"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

gcloud config set project "$GCP_PROJECT"

# ── Enable APIs ──────────────────────────────────────────────────────────────
echo ""
echo "▶ Enabling required GCP APIs..."
gcloud services enable \
  cloudfunctions.googleapis.com \
  cloudbuild.googleapis.com \
  run.googleapis.com \
  eventarc.googleapis.com \
  storage.googleapis.com \
  bigquery.googleapis.com \
  cloudscheduler.googleapis.com \
  iam.googleapis.com \
  --quiet

# ── GCS Bucket ───────────────────────────────────────────────────────────────
echo ""
echo "▶ Creating GCS bucket: gs://$GCS_BUCKET ..."
if ! gsutil ls "gs://$GCS_BUCKET" &>/dev/null; then
  gsutil mb -p "$GCP_PROJECT" -l "$REGION" "gs://$GCS_BUCKET"
  echo "  Created bucket."
else
  echo "  Bucket already exists."
fi

# Enable versioning
gsutil versioning set on "gs://$GCS_BUCKET"

# Lifecycle: delete files older than 90 days
cat > /tmp/lifecycle.json <<EOF
{
  "rule": [{
    "action": {"type": "Delete"},
    "condition": {"age": 90}
  }]
}
EOF
gsutil lifecycle set /tmp/lifecycle.json "gs://$GCS_BUCKET"
echo "  Lifecycle rule set (delete after 90 days)."

# ── Service Account: Functions ───────────────────────────────────────────────
echo ""
echo "▶ Creating service account: $FUNCTIONS_SA ..."
if ! gcloud iam service-accounts describe "$FUNCTIONS_SA@$GCP_PROJECT.iam.gserviceaccount.com" &>/dev/null; then
  gcloud iam service-accounts create "$FUNCTIONS_SA" \
    --display-name="ETL Cloud Functions SA" \
    --description="Used by etl-extract and etl-load functions"
fi

# Grant roles
for ROLE in \
  roles/storage.objectAdmin \
  roles/bigquery.dataEditor \
  roles/bigquery.jobUser \
  roles/eventarc.eventReceiver; do
  gcloud projects add-iam-policy-binding "$GCP_PROJECT" \
    --member="serviceAccount:$FUNCTIONS_SA@$GCP_PROJECT.iam.gserviceaccount.com" \
    --role="$ROLE" \
    --condition=None \
    --quiet
done
echo "  Roles granted."

# ── Service Account: Scheduler ───────────────────────────────────────────────
echo ""
echo "▶ Creating service account: $SCHEDULER_SA ..."
if ! gcloud iam service-accounts describe "$SCHEDULER_SA@$GCP_PROJECT.iam.gserviceaccount.com" &>/dev/null; then
  gcloud iam service-accounts create "$SCHEDULER_SA" \
    --display-name="ETL Cloud Scheduler SA"
fi
gcloud projects add-iam-policy-binding "$GCP_PROJECT" \
  --member="serviceAccount:$SCHEDULER_SA@$GCP_PROJECT.iam.gserviceaccount.com" \
  --role="roles/run.invoker" \
  --condition=None \
  --quiet
echo "  Roles granted."

# ── BigQuery Dataset ─────────────────────────────────────────────────────────
echo ""
echo "▶ Creating BigQuery dataset: $BQ_DATASET ..."
if ! bq show --dataset "$GCP_PROJECT:$BQ_DATASET" &>/dev/null; then
  bq mk --dataset \
    --location=US \
    --description="Open Library ETL data" \
    "$GCP_PROJECT:$BQ_DATASET"
  echo "  Dataset created."
else
  echo "  Dataset already exists."
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Setup complete."
echo ""
echo "Next steps:"
echo "  1. Deploy functions:  bash scripts/deploy.sh"
echo "  2. Create scheduler:  bash scripts/create_scheduler.sh"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
