from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Iterable

from dotenv import load_dotenv

load_dotenv()


def _split_endpoints(value: str | None, default: Iterable[str]) -> tuple[str, ...]:
	if value is None or not value.strip():
		return tuple(default)

	endpoints = tuple(
		endpoint.strip()
		for endpoint in value.replace(" ", ",").split(",")
		if endpoint.strip()
	)
	return endpoints or tuple(default)


@dataclass(frozen=True, slots=True)
class RabbitMQConfig:
	host: str = os.getenv("RABBITMQ_HOST", "rabbitmq")
	port: int = int(os.getenv("RABBITMQ_PORT", "5672"))
	user: str = os.getenv("RABBITMQ_DEFAULT_USER", "guest")
	password: str = os.getenv("RABBITMQ_DEFAULT_PASS", "guest")
	vhost: str = os.getenv("RABBITMQ_VHOST", "/")


@dataclass(frozen=True, slots=True)
class MinIOConfig:
	endpoint: str = os.getenv("MINIO_ENDPOINT", "10.0.0.2:9000")
	endpoints: tuple[str, ...] = _split_endpoints(
		os.getenv("MINIO_ENDPOINTS") or os.getenv("MINIO_ENDPOINT"),
		("10.0.0.2:9000", "10.0.0.3:9000", "10.0.0.4:9000"),
	)
	access_key: str = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
	secret_key: str = os.getenv("MINIO_SECRET_KEY", "minioadmin123")
	secure: bool = os.getenv("MINIO_SECURE", "false").lower() == "true"
	bucket: str = os.getenv("MINIO_BUCKET", "rudy-drive")


@dataclass(frozen=True, slots=True)
class PostgresConfig:
	host: str = os.getenv("POSTGRES_HOST", "localhost")
	port: int = int(os.getenv("POSTGRES_PORT", "5432"))
	db: str = os.getenv("POSTGRES_DB", "rudy_drive")
	user: str = os.getenv("POSTGRES_USER", "postgres")
	password: str = os.getenv("POSTGRES_PASSWORD", "postgres")

	@property
	def url(self) -> str:
		database_url = os.getenv("DATABASE_URL")
		if database_url:
			return database_url
		return (
			f"postgresql://{self.user}:{self.password}"
			f"@{self.host}:{self.port}/{self.db}"
		)


@dataclass(frozen=True, slots=True)
class AppConfig:
	rabbitmq: RabbitMQConfig = RabbitMQConfig()
	minio: MinIOConfig = MinIOConfig()
	postgres: PostgresConfig = PostgresConfig()
	secret_key: str = os.getenv("SECRET_KEY", "clave_secreta_temporal")
	algorithm: str = os.getenv("ALGORITHM", "HS256")
	access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
	upload_chunk_size_bytes: int = int(os.getenv("UPLOAD_CHUNK_SIZE_BYTES", "5242880"))
	backend_url: str = os.getenv("BACKEND_URL", "http://backend:8000")


def load_settings() -> AppConfig:
	return AppConfig()