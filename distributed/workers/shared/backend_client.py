from __future__ import annotations

from dataclasses import dataclass
import os

import requests


@dataclass(frozen=True, slots=True)
class BackendClient:
    base_url: str = os.getenv("BACKEND_URL", "http://backend:8000")
    timeout_seconds: int = int(os.getenv("BACKEND_TIMEOUT_SECONDS", "5"))

    def _post(self, path: str, payload: dict[str, object]) -> None:
        response = requests.post(
            f"{self.base_url.rstrip('/')}{path}",
            json=payload,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()

    def task_success(self, task_id: str) -> None:
        self._post("/internal/tasks/success", {"task_id": task_id})

    def task_failure(self, task_id: str, error_message: str) -> None:
        self._post(
            "/internal/tasks/failure",
            {"task_id": task_id, "error_message": error_message},
        )
