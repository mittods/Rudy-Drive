# app/services/message_bus.py

import json
import pika

from minio import Minio
from app.config import (
    RABBITMQ_HOST,
    RABBITMQ_PORT,
    MINIO_ENDPOINT,
    MINIO_ACCESS_KEY,
    MINIO_SECRET_KEY,
    MINIO_SECURE
)


def publish_message(
    routing_key: str,
    payload: dict
):

    connection = pika.BlockingConnection(
        pika.ConnectionParameters(
            host=settings.RABBITMQ_HOST,
            port=settings.RABBITMQ_PORT
        )
    )

    channel = connection.channel()

    channel.queue_declare(
        queue=routing_key,
        durable=True
    )

    channel.basic_publish(
        exchange="",
        routing_key=routing_key,
        body=json.dumps(payload).encode("utf-8"),
        properties=pika.BasicProperties(
            delivery_mode=2
        )
    )

    connection.close()

    return True


def get_file_stream(
    bucket: str,
    object_key: str
):

    client = Minio(
        endpoint=settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE
    )

    response = client.get_object(
        bucket,
        object_key
    )

    return response.stream(32 * 1024)