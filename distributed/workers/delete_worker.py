from __future__ import annotations

from workers.shared.config import load_settings
from workers.shared.minio_client import MinIOClient
from workers.shared.queue_worker import QueueWorker
from workers.shared.rabbitmq_client import RabbitMQClient
from workers.shared.worker_logger import WorkerLogger


def handle_delete(payload: dict[str, object], minio_client: MinIOClient, logger: WorkerLogger) -> None:
    upload_id = str(payload["upload_id"])
    minio_client.delete_prefix(f"{upload_id}/")
    logger.upload_success(upload_id, deleted=True)


def main() -> None:
    settings = load_settings()
    logger = WorkerLogger(name="delete-worker")
    minio_client = MinIOClient(settings.minio)

    worker = QueueWorker(
        worker_name="delete-worker",
        queue_name="delete.chunk",
        rabbitmq_client=RabbitMQClient(settings.rabbitmq),
        logger=logger,
        handler=lambda payload: handle_delete(payload, minio_client, logger),
    )
    worker.run()


if __name__ == "__main__":
    main()