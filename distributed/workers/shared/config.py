from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Iterable


DEFAULT_RABBITMQ_HOST = "127.0.0.1"
DEFAULT_RABBITMQ_PORT = 5672
DEFAULT_RABBITMQ_USER = "guest"
DEFAULT_RABBITMQ_PASSWORD = "guest"
DEFAULT_RABBITMQ_VHOST = "/"

DEFAULT_MINIO_ENDPOINT = "10.0.0.2:9000"
DEFAULT_MINIO_ENDPOINTS = ("10.0.0.2:9000",)
DEFAULT_MINIO_ACCESS_KEY = "minioadmin"
DEFAULT_MINIO_SECRET_KEY = "minioadmin123"
DEFAULT_MINIO_SECURE = False
DEFAULT_MINIO_BUCKET = "rudy-drive"

DEFAULT_UPLOAD_CHUNK_SIZE_BYTES = 5 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class RabbitMQConfig:
    host: str = DEFAULT_RABBITMQ_HOST
    port: int = DEFAULT_RABBITMQ_PORT
    user: str = DEFAULT_RABBITMQ_USER
    password: str = DEFAULT_RABBITMQ_PASSWORD
    vhost: str = DEFAULT_RABBITMQ_VHOST


@dataclass(frozen=True, slots=True)
class MinIOConfig:
    endpoint: str = DEFAULT_MINIO_ENDPOINT
    endpoints: tuple[str, ...] = DEFAULT_MINIO_ENDPOINTS
    access_key: str = DEFAULT_MINIO_ACCESS_KEY
    secret_key: str = DEFAULT_MINIO_SECRET_KEY
    secure: bool = DEFAULT_MINIO_SECURE
    bucket: str = DEFAULT_MINIO_BUCKET


@dataclass(frozen=True, slots=True)
class ChunkingConfig:
    size_bytes: int = DEFAULT_UPLOAD_CHUNK_SIZE_BYTES


@dataclass(frozen=True, slots=True)
class Settings:
    rabbitmq: RabbitMQConfig = RabbitMQConfig()
    minio: MinIOConfig = MinIOConfig()
    chunking: ChunkingConfig = ChunkingConfig()


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _split_endpoints(value: str | None, default: Iterable[str]) -> tuple[str, ...]:
    if value is None or not value.strip():
        return tuple(default)

    endpoints = tuple(
        endpoint.strip()
        for endpoint in value.replace(" ", ",").split(",")
        if endpoint.strip()
    )
    return endpoints or tuple(default)


def load_settings() -> Settings:
    return Settings(
        rabbitmq=RabbitMQConfig(
            host=os.getenv("RABBITMQ_HOST", DEFAULT_RABBITMQ_HOST),
            port=int(os.getenv("RABBITMQ_PORT", str(DEFAULT_RABBITMQ_PORT))),
            user=os.getenv("RABBITMQ_DEFAULT_USER", DEFAULT_RABBITMQ_USER),
            password=os.getenv("RABBITMQ_DEFAULT_PASS", DEFAULT_RABBITMQ_PASSWORD),
            vhost=os.getenv("RABBITMQ_VHOST", DEFAULT_RABBITMQ_VHOST),
        ),
        minio=MinIOConfig(
            endpoint=_split_endpoints(os.getenv("MINIO_ENDPOINTS") or os.getenv("MINIO_ENDPOINT"), DEFAULT_MINIO_ENDPOINTS)[0],
            endpoints=_split_endpoints(os.getenv("MINIO_ENDPOINTS") or os.getenv("MINIO_ENDPOINT"), DEFAULT_MINIO_ENDPOINTS),
            access_key=os.getenv("MINIO_ROOT_USER", DEFAULT_MINIO_ACCESS_KEY),
            secret_key=os.getenv("MINIO_ROOT_PASSWORD", DEFAULT_MINIO_SECRET_KEY),
            secure=_get_bool("MINIO_SECURE", DEFAULT_MINIO_SECURE),
            bucket=os.getenv("MINIO_BUCKET", DEFAULT_MINIO_BUCKET),
        ),
        chunking=ChunkingConfig(
            size_bytes=int(os.getenv("UPLOAD_CHUNK_SIZE_BYTES", str(DEFAULT_UPLOAD_CHUNK_SIZE_BYTES))),
        ),
    )
