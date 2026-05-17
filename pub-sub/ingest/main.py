import json
import os

import functions_framework
from google.cloud import pubsub_v1

PROJECT_ID = os.environ["GOOGLE_CLOUD_PROJECT"]
TOPIC_ID = "feedback-topic"

publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)


@functions_framework.http
def handle(request):
    payload = request.get_json(silent=True)
    if not payload or "user_id" not in payload or "message" not in payload:
        return {"error": "Invalid payload: expected user_id and message"}, 400

    data = json.dumps(payload).encode("utf-8")
    future = publisher.publish(topic_path, data)
    message_id = future.result()
    return {"message_id": message_id}, 200
