from __future__ import annotations

from workers.shared.backend_client import BackendClient
from workers.shared.config import load_settings
from workers.shared.minio_client import MinIOClient
from workers.shared.queue_worker import QueueWorker
from workers.shared.rabbitmq_client import RabbitMQClient
from workers.shared.worker_logger import WorkerLogger


def handle_delete(payload: dict[str, object], minio_client: MinIOClient, logger: WorkerLogger) -> None:
    upload_id = str(payload["upload_id"])
    task_id = str(payload["task_id"])
    backend_client = BackendClient()

    try:
        minio_client.delete_prefix_all(f"{upload_id}/")
        backend_client.task_success(task_id)
        logger.upload_success(upload_id, deleted=True)
    except Exception as exc:
        try:
            backend_client.task_failure(task_id, str(exc))
        except Exception:
            pass
        logger.upload_failed(upload_id, str(exc))
        raise


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