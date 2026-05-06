#!/usr/bin/env bash
# =============================================================================
# create_scheduler.sh — Create a Cloud Scheduler job to trigger etl-extract
#
# Runs daily at 02:00 UTC.
#
# Usage:
#   export GCP_PROJECT=your-project-id
#   bash scripts/create_scheduler.sh
# =============================================================================
set -euo pipefail

GCP_PROJECT=${GCP_PROJECT:?Set GCP_PROJECT}
REGION=${REGION:-asia-southeast1}
SCHEDULER_SA="etl-scheduler-sa@$GCP_PROJECT.iam.gserviceaccount.com"
JOB_NAME="etl-extract-daily"
SCHEDULE="0 2 * * *"   # 02:00 UTC every day

# Get the function URL
FUNCTION_URL=$(gcloud functions describe etl-extract \
  --region="$REGION" --gen2 --format="value(serviceConfig.uri)")

if [[ -z "$FUNCTION_URL" ]]; then
  echo "ERROR: etl-extract not deployed yet. Run deploy.sh first."
  exit 1
fi

echo "Function URL: $FUNCTION_URL"
echo "Schedule    : $SCHEDULE  (daily at 02:00 UTC)"

# Delete existing job if present (for idempotency)
if gcloud scheduler jobs describe "$JOB_NAME" --location="$REGION" &>/dev/null; then
  echo "Deleting existing scheduler job..."
  gcloud scheduler jobs delete "$JOB_NAME" --location="$REGION" --quiet
fi

gcloud scheduler jobs create http "$JOB_NAME" \
  --location="$REGION" \
  --schedule="$SCHEDULE" \
  --uri="$FUNCTION_URL" \
  --http-method=POST \
  --message-body='{"trigger":"scheduler"}' \
  --headers="Content-Type=application/json" \
  --oidc-service-account-email="$SCHEDULER_SA" \
  --oidc-token-audience="$FUNCTION_URL" \
  --time-zone="UTC" \
  --description="Triggers the ETL extract function daily at 02:00 UTC"

echo ""
echo "✅ Cloud Scheduler job created: $JOB_NAME"
echo ""
echo "To trigger manually right now:"
echo "  gcloud scheduler jobs run $JOB_NAME --location=$REGION"
