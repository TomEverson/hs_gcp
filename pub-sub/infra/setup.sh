#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-data-engineering-hs}"
REGION="asia-southeast1"
TOPIC="feedback-topic"

echo "==> Setting project to $PROJECT_ID"
gcloud config set project "$PROJECT_ID"

echo "==> Enabling required APIs"
gcloud services enable \
  pubsub.googleapis.com \
  run.googleapis.com \
  language.googleapis.com \
  secretmanager.googleapis.com \
  cloudbuild.googleapis.com \
  --project "$PROJECT_ID"

echo "==> Creating Pub/Sub topic: $TOPIC"
gcloud pubsub topics create "$TOPIC" \
  --project "$PROJECT_ID" 2>/dev/null || echo "  (topic already exists)"

echo "==> Storing Slack bot token in Secret Manager"
echo -n "Paste your Slack bot token (xoxb-...): "
read -rs SLACK_TOKEN
echo

if gcloud secrets describe slack-bot-token --project "$PROJECT_ID" &>/dev/null; then
  echo "  Adding new version to existing secret"
  echo -n "$SLACK_TOKEN" | gcloud secrets versions add slack-bot-token \
    --data-file=- --project "$PROJECT_ID"
else
  echo "  Creating new secret"
  echo -n "$SLACK_TOKEN" | gcloud secrets create slack-bot-token \
    --data-file=- --replication-policy=automatic --project "$PROJECT_ID"
fi

echo ""
echo "==> Setup complete."
echo "    Run deploy.sh next to build and deploy the Cloud Run functions."
echo "    Pub/Sub push subscriptions will be created by deploy.sh once URLs are known."
