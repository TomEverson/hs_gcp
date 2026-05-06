#!/usr/bin/env bash
# =============================================================================
# deploy.sh — Deploy both Cloud Run Functions manually
#
# Usage:
#   export GCP_PROJECT=your-project-id
#   export GCS_BUCKET=your-bucket-name
#   bash scripts/deploy.sh
# =============================================================================
set -euo pipefail

GCP_PROJECT=${GCP_PROJECT:?Set GCP_PROJECT}
GCS_BUCKET=${GCS_BUCKET:?Set GCS_BUCKET}
REGION=${REGION:-asia-southeast1}
BQ_DATASET=${BQ_DATASET:-open_library}
BQ_TABLE=${BQ_TABLE:-books}
SA="etl-functions-sa@$GCP_PROJECT.iam.gserviceaccount.com"

echo "▶ Deploying etl-extract..."
gcloud functions deploy etl-extract \
  --gen2 \
  --runtime=python312 \
  --region="$REGION" \
  --source=./function-extract \
  --entry-point=extract \
  --trigger-http \
  --no-allow-unauthenticated \
  --service-account="$SA" \
  --set-env-vars="GCS_BUCKET=$GCS_BUCKET,GCP_PROJECT=$GCP_PROJECT,PAGE_LIMIT=5" \
  --memory=512Mi \
  --timeout=540s

echo ""
echo "▶ Deploying etl-load..."
gcloud functions deploy etl-load \
  --gen2 \
  --runtime=python312 \
  --region="$REGION" \
  --source=./function-load \
  --entry-point=load \
  --trigger-event-filters="type=google.cloud.storage.object.v1.finalized" \
  --trigger-event-filters="bucket=$GCS_BUCKET" \
  --service-account="$SA" \
  --set-env-vars="GCP_PROJECT=$GCP_PROJECT,BQ_DATASET=$BQ_DATASET,BQ_TABLE=$BQ_TABLE" \
  --memory=512Mi \
  --timeout=300s

echo ""
echo "✅ Both functions deployed."
echo ""
echo "etl-extract URL:"
gcloud functions describe etl-extract \
  --region="$REGION" --gen2 --format="value(serviceConfig.uri)"
