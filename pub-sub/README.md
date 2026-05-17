# GCP Feedback Sentiment Pipeline

Receives user feedback via HTTP, publishes to Pub/Sub, analyzes sentiment with the Google Cloud Natural Language API, and sends Slack alerts to the appropriate channel.

## Architecture

```
POST /handle (ingest)
        │
        ▼
  feedback-topic (Pub/Sub)
        │
        ├──► positive-sub ──► positive-handler ──► #followup (Slack)
        │                     (POSITIVE / NEUTRAL)
        │
        └──► negative-sub ──► negative-handler ──► #support  (Slack)
                              (NEGATIVE)
```

| Component | Type | Trigger |
|-----------|------|---------|
| `ingest` | Cloud Run (HTTP) | Public HTTPS |
| `positive-handler` | Cloud Run (HTTP) | Pub/Sub push (`positive-sub`) |
| `negative-handler` | Cloud Run (HTTP) | Pub/Sub push (`negative-sub`) |

## Prerequisites

- `gcloud` CLI authenticated (`gcloud auth login`)
- Docker installed and authenticated to Artifact Registry (`gcloud auth configure-docker asia-southeast1-docker.pkg.dev`)
- A Slack Bot Token with `chat:write` scope, added to the `#followup` and `#support` channels

## Setup

### 1. Set your project

```bash
export GOOGLE_CLOUD_PROJECT=data-engineering-hs
```

### 2. Run infra setup (once)

This enables APIs, creates the Pub/Sub topic, and stores your Slack token in Secret Manager.

```bash
bash infra/setup.sh
```

You will be prompted to paste your Slack bot token (`xoxb-...`).

### 3. Deploy all functions

```bash
bash deploy.sh
```

This will:
- Build and push Docker images to Artifact Registry
- Deploy three Cloud Run services
- Create/update the `positive-sub` and `negative-sub` push subscriptions
- Print the ingest URL when done

### 4. Test with Postman

Import `tests/postman_collection.json` into Postman, set the `ingest_url` collection variable to your ingest Cloud Run URL, then run the three requests.

Or test with curl:

```bash
INGEST_URL=https://your-ingest-url

# Positive
curl -X POST "${INGEST_URL}/handle" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "alice", "message": "This product is absolutely fantastic!"}'

# Neutral
curl -X POST "${INGEST_URL}/handle" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "bob", "message": "The package arrived on time."}'

# Negative
curl -X POST "${INGEST_URL}/handle" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "carol", "message": "Terrible experience. Completely broken."}'
```

## Sentiment thresholds

Uses the Natural Language API document sentiment score (`-1.0` to `+1.0`):

| Score | Classification | Handler |
|-------|---------------|---------|
| ≥ −0.25 | POSITIVE / NEUTRAL | positive-handler → #followup |
| < −0.25 | NEGATIVE | negative-handler → #support |

## Project structure

```
pub-sub/
├── ingest/               # HTTP ingest function
│   ├── main.py
│   ├── pyproject.toml
│   ├── uv.lock
│   └── Dockerfile
├── positive-handler/     # Handles positive + neutral feedback
│   ├── main.py
│   ├── pyproject.toml
│   ├── uv.lock
│   └── Dockerfile
├── negative-handler/     # Handles negative feedback
│   ├── main.py
│   ├── pyproject.toml
│   ├── uv.lock
│   └── Dockerfile
├── infra/
│   └── setup.sh          # One-time GCP resource setup
├── tests/
│   └── postman_collection.json
└── deploy.sh             # Build, push, deploy, wire subscriptions
```

## Configuration

| Setting | Value |
|---------|-------|
| Project ID | `data-engineering-hs` |
| Region | `asia-southeast1` |
| Pub/Sub topic | `feedback-topic` |
| Slack secret | `slack-bot-token` (Secret Manager) |
| Artifact Registry | `feedback-pipeline` |
