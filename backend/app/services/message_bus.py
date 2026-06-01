import json
import os

import pika

from minio import Minio
from app.config import load_settings


settings = load_settings()


def publish_message(
    routing_key: str,
    payload: dict
):

    connection = pika.BlockingConnection(
        pika.ConnectionParameters(
            host=settings.rabbitmq.host,
            port=settings.rabbitmq.port,
            credentials=pika.PlainCredentials(
                settings.rabbitmq.user,
                settings.rabbitmq.password,
            ),
            virtual_host=settings.rabbitmq.vhost,
            connection_attempts=3,
            retry_delay=2,
            blocked_connection_timeout=30,
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
        endpoint=settings.minio.endpoint,
        access_key=settings.minio.access_key,
        secret_key=settings.minio.secret_key,
        secure=settings.minio.secure
    )

    response = client.get_object(
        bucket,
        object_key
    )

    return response.stream(32 * 1024)