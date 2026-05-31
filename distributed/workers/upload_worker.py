from __future__ import annotations

import base64

from workers.shared.chunk_storage import ChunkStorage
from workers.shared.config import load_settings
from workers.shared.minio_client import MinIOClient
from workers.shared.queue_worker import QueueWorker
from workers.shared.rabbitmq_client import RabbitMQClient
from workers.shared.worker_logger import WorkerLogger


def handle_upload(payload: dict[str, object], storage: ChunkStorage, logger: WorkerLogger) -> None:
    upload_id = str(payload["upload_id"])
    if "data_base64" in payload:
        raw_data = base64.b64decode(str(payload["data_base64"]))
    else:
        raw_data = str(payload.get("data", "")).encode("utf-8")

    storage.store_bytes(upload_id, raw_data)
    logger.upload_success(upload_id, size_bytes=len(raw_data))


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