from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Callable

from .rabbitmq_client import RabbitMQClient
from .worker_logger import WorkerLogger


MessageHandler = Callable[[dict[str, Any]], None]


@dataclass(frozen=True, slots=True)
class QueueWorker:
    worker_name: str
    queue_name: str
    rabbitmq_client: RabbitMQClient
    logger: WorkerLogger
    handler: MessageHandler

    def max_retries(self) -> int:
        return max(0, int(os.getenv("QUEUE_MAX_RETRIES", "3")))

    def run(self) -> None:
        connection = self.rabbitmq_client.connect()
        channel = connection.channel()
        channel.queue_declare(queue=self.queue_name, durable=True)
        self.logger.worker_started(self.worker_name, queue=self.queue_name)

        def on_message(ch, method, properties, body):
            self.logger.message_received(self.queue_name, worker=self.worker_name)
            payload: Any = None
            try:
                payload = json.loads(body.decode("utf-8"))
                self.handler(payload)
                ch.basic_ack(method.delivery_tag)
            except Exception as exc:
                retry_count = 0
                if isinstance(payload, dict):
                    retry_count = int(payload.get("_retry_count", 0))

                if isinstance(payload, dict) and retry_count < self.max_retries():
                    retry_payload = dict(payload)
                    retry_payload["_retry_count"] = retry_count + 1
                    try:
                        self.rabbitmq_client.publish(self.queue_name, retry_payload)
                        self.logger.message_failed(
                            self.queue_name,
                            str(exc),
                            worker=self.worker_name,
                            requeued=True,
                            retry_count=retry_count,
                        )
                        ch.basic_ack(method.delivery_tag)
                        return
                    except Exception as republish_exc:
                        self.logger.message_failed(
                            self.queue_name,
                            str(exc),
                            worker=self.worker_name,
                            requeued=False,
                            retry_count=retry_count,
                            republish_error=str(republish_exc),
                        )
                        ch.basic_nack(method.delivery_tag, requeue=True)
                        return

                self.logger.message_failed(
                    self.queue_name,
                    str(exc),
                    worker=self.worker_name,
                    requeued=False,
                    retry_count=retry_count,
                )
                ch.basic_nack(method.delivery_tag, requeue=False)

        channel.basic_consume(queue=self.queue_name, on_message_callback=on_message, auto_ack=False)
        channel.start_consuming()