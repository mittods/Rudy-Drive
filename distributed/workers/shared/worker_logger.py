from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class WorkerLogger:
    name: str = "rudy-drive.worker"
    log_file: Path = Path("logs/worker.log")

    def __post_init__(self) -> None:
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def _logger(self) -> logging.Logger:
        logger = logging.getLogger(self.name)
        if not logger.handlers:
            logger.setLevel(logging.INFO)
            logger.propagate = False

            formatter = logging.Formatter("%(message)s")

            file_handler = logging.FileHandler(self.log_file, encoding="utf-8")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        return logger

    def _write(self, event: str, **details: Any) -> None:
        payload = {
            "timestamp": _utc_timestamp(),
            "event": event,
            **details,
        }
        self._logger().info(payload)

    def worker_started(self, worker_name: str, **details: Any) -> None:
        self._write("worker.started", worker=worker_name, **details)

    def message_received(self, queue_name: str, **details: Any) -> None:
        self._write("message.received", queue=queue_name, **details)

    def message_failed(self, queue_name: str, error: str, **details: Any) -> None:
        self._write("message.failed", queue=queue_name, error=error, **details)

    def upload_success(self, upload_id: str, **details: Any) -> None:
        self._write("upload.success", upload_id=upload_id, **details)

    def upload_failed(self, upload_id: str, error: str, **details: Any) -> None:
        self._write("upload.failed", upload_id=upload_id, error=error, **details)