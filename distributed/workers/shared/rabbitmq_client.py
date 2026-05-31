from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pika

from .config import RabbitMQConfig


@dataclass(frozen=True, slots=True)
class RabbitMQClient:
    config: RabbitMQConfig

    def connection_parameters(self) -> pika.ConnectionParameters:
        credentials = pika.PlainCredentials(self.config.user, self.config.password)
        return pika.ConnectionParameters(
            host=self.config.host,
            port=self.config.port,
            virtual_host=self.config.vhost,
            credentials=credentials,
        )

    def connect(self) -> pika.BlockingConnection:
        return pika.BlockingConnection(self.connection_parameters())

    @staticmethod
    def encode_message(payload: Any) -> bytes:
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    def publish(self, queue_name: str, payload: Any) -> None:
        connection = self.connect()
        try:
            channel = connection.channel()
            channel.queue_declare(queue=queue_name, durable=True)
            channel.basic_publish(
                exchange="",
                routing_key=queue_name,
                body=self.encode_message(payload),
                properties=pika.BasicProperties(delivery_mode=2),
            )
        finally:
            connection.close()
