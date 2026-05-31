from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, TypeVar

from minio import Minio

from .config import MinIOConfig


T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class MinIOClient:
    config: MinIOConfig

    def candidate_endpoints(self) -> tuple[str, ...]:
        endpoints = tuple(
            endpoint.strip()
            for endpoint in self.config.endpoints
            if endpoint.strip()
        )
        return endpoints or (self.config.endpoint,)

    def connect(self, endpoint: str | None = None) -> Minio:
        target_endpoint = endpoint or self.config.endpoint
        return Minio(
            endpoint=target_endpoint,
            access_key=self.config.access_key,
            secret_key=self.config.secret_key,
            secure=self.config.secure,
        )

    def with_client(self, operation: Callable[[Minio], T]) -> T:
        last_error: Exception | None = None
        for endpoint in self.candidate_endpoints():
            client = self.connect(endpoint)
            try:
                return operation(client)
            except Exception as exc:
                last_error = exc
        if last_error is not None:
            raise last_error
        raise RuntimeError("No MinIO endpoints configured")

    def ensure_bucket(self) -> None:
        def operation(client: Minio) -> None:
            if not client.bucket_exists(self.config.bucket):
                client.make_bucket(self.config.bucket)

        self.with_client(operation)

    def delete_prefix(self, prefix: str) -> None:
        def operation(client: Minio) -> None:
            for object_info in client.list_objects(self.config.bucket, prefix=prefix, recursive=True):
                client.remove_object(self.config.bucket, object_info.object_name)

        self.with_client(operation)
