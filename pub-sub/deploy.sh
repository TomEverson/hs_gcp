#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-data-engineering-hs}"
REGION="asia-southeast1"
TOPIC="feedback-topic"
REPO="feedback-pipeline"

echo "==> Project: $PROJECT_ID  Region: $REGION"
gcloud config set project "$PROJECT_ID"

# ── Artifact Registry ──────────────────────────────────────────────────────────
echo "==> Ensuring Artifact Registry repo: $REPO"
gcloud artifacts repositories describe "$REPO" \
  --location="$REGION" --project="$PROJECT_ID" &>/dev/null || \
gcloud artifacts repositories create "$REPO" \
  --repository-format=docker \
  --location="$REGION" \
  --project="$PROJECT_ID"

IMAGE_BASE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}"

# ── Build & push helper ────────────────────────────────────────────────────────
deploy_function() {
  local name="$1"   # folder name == Cloud Run service name
  local dir="$(dirname "$0")/${name}"

  echo ""
  echo "==> Building $name"
  gcloud builds submit "$dir" \
    --tag "${IMAGE_BASE}/${name}:latest" \
    --project "$PROJECT_ID"

  echo "==> Deploying $name to Cloud Run"
  gcloud run deploy "$name" \
    --image "${IMAGE_BASE}/${name}:latest" \
    --region "$REGION" \
    --platform managed \
    --allow-unauthenticated \
    --set-env-vars "GOOGLE_CLOUD_PROJECT=${PROJECT_ID}" \
    --project "$PROJECT_ID"

  # Return the deployed URL
  gcloud run services describe "$name" \
    --region "$REGION" \
    --project "$PROJECT_ID" \
    --format "value(status.url)"
}

INGEST_URL=$(deploy_function "ingest")
POSITIVE_URL=$(deploy_function "positive-handler")
NEGATIVE_URL=$(deploy_function "negative-handler")

echo ""
echo "==> URLs:"
echo "    ingest:           $INGEST_URL"
echo "    positive-handler: $POSITIVE_URL"
echo "    negative-handler: $NEGATIVE_URL"

# ── Pub/Sub push subscriptions ─────────────────────────────────────────────────
create_or_update_sub() {
  local sub="$1"
  local endpoint="$2"

  if gcloud pubsub subscriptions describe "$sub" --project "$PROJECT_ID" &>/dev/null; then
    echo "==> Updating push endpoint for $sub"
    gcloud pubsub subscriptions modify-push-config "$sub" \
      --push-endpoint="$endpoint" \
      --project "$PROJECT_ID"
  else
    echo "==> Creating push subscription: $sub -> $endpoint"
    gcloud pubsub subscriptions create "$sub" \
      --topic "$TOPIC" \
      --push-endpoint "$endpoint" \
      --ack-deadline=60 \
      --project "$PROJECT_ID"
  fi
}

create_or_update_sub "positive-sub" "${POSITIVE_URL}/handle"
create_or_update_sub "negative-sub" "${NEGATIVE_URL}/handle"

# Grant Pub/Sub SA permission to invoke the Cloud Run services
PUBSUB_SA="service-$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')@gcp-sa-pubsub.iam.gserviceaccount.com"
for svc in positive-handler negative-handler; do
  gcloud run services add-iam-policy-binding "$svc" \
    --region "$REGION" \
    --member "serviceAccount:${PUBSUB_SA}" \
    --role "roles/run.invoker" \
    --project "$PROJECT_ID" 2>/dev/null || true
done

echo ""
echo "==> Deployment complete!"
echo "    Send a test message:"
echo "    curl -X POST ${INGEST_URL}/handle -H 'Content-Type: application/json' \\"
echo "         -d '{\"user_id\": \"alice\", \"message\": \"Great product!\"}'"
