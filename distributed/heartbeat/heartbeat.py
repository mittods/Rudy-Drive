import json
import os
import socket
import time
from datetime import datetime, timezone
from urllib import error, request

import pika


HOST = os.getenv("RABBITMQ_HOST", "127.0.0.1")
PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
USER = os.getenv("RABBITMQ_DEFAULT_USER", "guest")
PASSWORD = os.getenv("RABBITMQ_DEFAULT_PASS", "guest")
QUEUE = os.getenv("HEARTBEAT_QUEUE", "node.heartbeat")
INTERVAL_SECONDS = int(os.getenv("HEARTBEAT_INTERVAL_SECONDS", "10"))
NODE_NAME = os.getenv("HEARTBEAT_NODE_NAME", socket.gethostname())
BACKEND_HEARTBEAT_URL = os.getenv("BACKEND_HEARTBEAT_URL", "http://backend:8000/internal/nodes/heartbeat")


def notify_backend(payload: dict) -> None:
    req = request.Request(
        BACKEND_HEARTBEAT_URL,
        data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=5) as response:
            response.read()
    except (error.HTTPError, error.URLError, TimeoutError) as exc:
        print(f"backend heartbeat error: {exc}", flush=True)


def connect() -> pika.BlockingConnection:
    credentials = pika.PlainCredentials(USER, PASSWORD)
    parameters = pika.ConnectionParameters(host=HOST, port=PORT, credentials=credentials, heartbeat=30)
    return pika.BlockingConnection(parameters)


def main() -> None:
    while True:
        try:
            connection = connect()
            channel = connection.channel()
            channel.queue_declare(queue=QUEUE, durable=True)

            while True:
                payload = {
                    "node": NODE_NAME,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "status": "alive",
                }
                body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
                channel.basic_publish(
                    exchange="",
                    routing_key=QUEUE,
                    body=body,
                    properties=pika.BasicProperties(delivery_mode=2),
                )
                notify_backend(payload)
                print(body.decode("utf-8"), flush=True)
                time.sleep(INTERVAL_SECONDS)
        except Exception as exc:
            print(f"heartbeat error: {exc}", flush=True)
            time.sleep(5)


if __name__ == "__main__":
    main()
