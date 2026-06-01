from __future__ import annotations

import json
import os
import time
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
        while True:
            connection = None
            try:
                connection = self.rabbitmq_client.connect()
                channel = connection.channel()
                channel.queue_declare(queue=self.queue_name, durable=True)
                channel.basic_qos(prefetch_count=1)
                self.logger.worker_started(self.worker_name, queue=self.queue_name)

                def on_message(ch, method, properties, body):
                    self.logger.message_received(self.queue_name, worker=self.worker_name)
                    payload: Any = None
                    try:
                        payload = json.loads(body.decode("utf-8"))
                        self.handler(payload)
                        try:
                            ch.basic_ack(method.delivery_tag)
                        except Exception as ack_exc:
                            self.logger.message_failed(
                                self.queue_name,
                                str(ack_exc),
                                worker=self.worker_name,
                                requeued=False,
                                retry_count=0,
                                ack_error=True,
                            )
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
                                try:
                                    ch.basic_ack(method.delivery_tag)
                                except Exception as ack_exc:
                                    self.logger.message_failed(
                                        self.queue_name,
                                        str(ack_exc),
                                        worker=self.worker_name,
                                        requeued=False,
                                        retry_count=retry_count,
                                        ack_error=True,
                                    )
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
                                try:
                                    ch.basic_nack(method.delivery_tag, requeue=True)
                                except Exception:
                                    pass
                                return

                        self.logger.message_failed(
                            self.queue_name,
                            str(exc),
                            worker=self.worker_name,
                            requeued=False,
                            retry_count=retry_count,
                        )
                        try:
                            ch.basic_nack(method.delivery_tag, requeue=False)
                        except Exception:
                            pass

                channel.basic_consume(queue=self.queue_name, on_message_callback=on_message, auto_ack=False)
                channel.start_consuming()
            except Exception as exc:
                self.logger.message_failed(
                    self.queue_name,
                    str(exc),
                    worker=self.worker_name,
                    requeued=False,
                    retry_count=0,
                    consumer_loop=True,
                )
                time.sleep(2)
            finally:
                if connection is not None:
                    try:
                        connection.close()
                    except Exception:
                        pass