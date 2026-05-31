# app/services/health_service.py

import os
from datetime import datetime, timedelta

import pika
from dotenv import load_dotenv
from minio import Minio
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import Node

load_dotenv()


def check_database(db: Session) -> str:
    try:
        db.execute(text("SELECT 1"))
        return "up"
    except Exception:
        return "down"


def check_rabbitmq() -> str:
    try:
        credentials = pika.PlainCredentials(
            os.getenv("RABBITMQ_DEFAULT_USER", "guest"),
            os.getenv("RABBITMQ_DEFAULT_PASS", "guest")
        )

        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=os.getenv("RABBITMQ_HOST", "10.0.0.1"),
                port=int(os.getenv("RABBITMQ_PORT", "5672")),
                credentials=credentials
            )
        )

        connection.close()
        return "up"

    except Exception:
        return "down"


def check_minio() -> str:
    try:
        endpoint = os.getenv("MINIO_ENDPOINT", "10.0.0.2:9000")

        client = Minio(
            endpoint=endpoint,
            access_key=os.getenv("MINIO_ROOT_USER", "minioadmin"),
            secret_key=os.getenv("MINIO_ROOT_PASSWORD", "minioadmin123"),
            secure=os.getenv("MINIO_SECURE", "false").lower() == "true"
        )

        client.list_buckets()
        return "up"

    except Exception:
        return "down"


def check_workers(db: Session) -> str:
    try:
        limit_time = datetime.utcnow() - timedelta(seconds=30)

        active_workers = db.query(Node).filter(
            Node.last_heartbeat >= limit_time,
            Node.status == "alive"
        ).count()

        if active_workers > 0:
            return "up"

        return "down"

    except Exception:
        return "down"