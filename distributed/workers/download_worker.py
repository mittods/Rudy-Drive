from __future__ import annotations

from workers.shared.chunk_metadata import ChunkMetadata
from workers.shared.chunk_recovery import ChunkRecoveryWorker
from workers.shared.config import load_settings
from workers.shared.minio_client import MinIOClient
from workers.shared.queue_worker import QueueWorker
from workers.shared.rabbitmq_client import RabbitMQClient
from workers.shared.worker_logger import WorkerLogger


def handle_download(payload: dict[str, object], recovery: ChunkRecoveryWorker) -> None:
    chunks = [
        ChunkMetadata(
            id=str(item["id"]),
            file_id=str(item["file_id"]),
            node=str(item["node"]),
            chunk_index=int(item["chunk_index"]),
            object_name=str(item["object_name"]),
        )
        for item in payload.get("chunks", [])
    ]
    recovery.recover_bytes(chunks)


def main() -> None:
    settings = load_settings()
    logger = WorkerLogger(name="download-worker")
    recovery = ChunkRecoveryWorker(minio_client=MinIOClient(settings.minio))

    worker = QueueWorker(
        worker_name="download-worker",
        queue_name="download.chunk",
        rabbitmq_client=RabbitMQClient(settings.rabbitmq),
        logger=logger,
        handler=lambda payload: handle_download(payload, recovery),
    )
    worker.run()


if __name__ == "__main__":
    main()