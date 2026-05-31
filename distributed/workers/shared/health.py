from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from .minio_client import MinIOClient
from .rabbitmq_client import RabbitMQClient


@dataclass(frozen=True, slots=True)
class DependencyCheck:
    name: str
    ok: bool
    details: dict[str, Any]


def check_rabbitmq(rabbitmq_client: RabbitMQClient) -> DependencyCheck:
    try:
        connection = rabbitmq_client.connect()
        connection.close()
        return DependencyCheck(name="rabbitmq", ok=True, details={"reachable": True})
    except Exception as exc:
        return DependencyCheck(name="rabbitmq", ok=False, details={"reachable": False, "error": str(exc)})


def check_minio(minio_client: MinIOClient) -> DependencyCheck:
    try:
        minio_client.with_client(lambda client: client.list_buckets())
        return DependencyCheck(name="minio", ok=True, details={"reachable": True})
    except Exception as exc:
        return DependencyCheck(name="minio", ok=False, details={"reachable": False, "error": str(exc)})


def build_health_router(rabbitmq_client: RabbitMQClient, minio_client: MinIOClient) -> APIRouter:
    router = APIRouter()

    @router.get("/health")
    def health() -> JSONResponse:
        rabbitmq = check_rabbitmq(rabbitmq_client)
        minio = check_minio(minio_client)
        ok = rabbitmq.ok and minio.ok
        body = {
            "status": "healthy" if ok else "unhealthy",
            "checks": {
                rabbitmq.name: rabbitmq.details,
                minio.name: minio.details,
            },
        }
        return JSONResponse(
            status_code=status.HTTP_200_OK if ok else status.HTTP_503_SERVICE_UNAVAILABLE,
            content=body,
        )

    return router