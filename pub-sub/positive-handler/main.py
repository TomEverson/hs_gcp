import base64
import json
import os

import functions_framework
from google.cloud import language_v2, secretmanager
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


def _get_slack_token() -> str:
    client = secretmanager.SecretManagerServiceClient()
    project_id = os.environ["GOOGLE_CLOUD_PROJECT"]
    name = f"projects/{project_id}/secrets/slack-bot-token/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("utf-8")


def _analyze_sentiment(text: str) -> float:
    client = language_v2.LanguageServiceClient()
    document = language_v2.Document(
        content=text, type_=language_v2.Document.Type.PLAIN_TEXT
    )
    result = client.analyze_sentiment(request={"document": document})
    return result.document_sentiment.score


@functions_framework.http
def handle(request):
    envelope = request.get_json(silent=True)
    if not envelope or "message" not in envelope:
        return "Bad Request: missing Pub/Sub envelope", 400

    raw = base64.b64decode(envelope["message"]["data"]).decode("utf-8")
    payload = json.loads(raw)
    user_id = payload["user_id"]
    message = payload["message"]

    score = _analyze_sentiment(message)

    # score >= -0.25 covers POSITIVE and NEUTRAL
    if score >= -0.25:
        slack = WebClient(token=_get_slack_token())
        try:
            slack.chat_postMessage(
                channel="#followup",
                text=f"✅ Positive feedback from {user_id}: {message}",
            )
        except SlackApiError as e:
            return f"Slack error: {e.response['error']}", 500

    return "OK", 200
