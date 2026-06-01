from __future__ import annotations

import base64

from workers.shared.chunk_storage import ChunkStorage
from workers.shared.backend_client import BackendClient
from workers.shared.config import load_settings
from workers.shared.minio_client import MinIOClient
from workers.shared.queue_worker import QueueWorker
from workers.shared.rabbitmq_client import RabbitMQClient
from workers.shared.worker_logger import WorkerLogger


def handle_upload(payload: dict[str, object], storage: ChunkStorage, logger: WorkerLogger) -> None:
    upload_id_value = payload.get("upload_id") or payload.get("file_id")
    if not upload_id_value:
        raise KeyError("upload_id")
    upload_id = str(upload_id_value)
    task_id = str(payload["task_id"])
    backend_client = BackendClient()
    if "data_base64" in payload:
        raw_data = base64.b64decode(str(payload["data_base64"]))
    else:
        raw_data = str(payload.get("data", "")).encode("utf-8")

    try:
        storage.store_bytes(upload_id, raw_data)
        backend_client.task_success(task_id)
        logger.upload_success(upload_id, size_bytes=len(raw_data))
    except Exception as exc:
        try:
            backend_client.task_failure(task_id, str(exc))
        except Exception:
            pass
        logger.upload_failed(upload_id, str(exc))
        raise


def main() -> None:
    settings = load_settings()
    logger = WorkerLogger(name="upload-worker")
    minio_client = MinIOClient(settings.minio)
    storage = ChunkStorage(minio_client=minio_client, chunking=settings.chunking)

    worker = QueueWorker(
        worker_name="upload-worker",
        queue_name="upload.chunk",
        rabbitmq_client=RabbitMQClient(settings.rabbitmq),
        logger=logger,
        handler=lambda payload: handle_upload(payload, storage, logger),
    )
    worker.run()


if __name__ == "__main__":
    main()