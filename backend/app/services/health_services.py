# app/services/health_service.py

import os
from datetime import datetime, timedelta

import pika
from dotenv import load_dotenv
from minio import Minio
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import load_settings
from app.models import Node

load_dotenv()

settings = load_settings()


def check_database(db: Session) -> str:
    try:
        db.execute(text("SELECT 1"))
        return "up"
    except Exception:
        return "down"


def check_rabbitmq() -> str:
    try:
        credentials = pika.PlainCredentials(
            settings.rabbitmq.user,
            settings.rabbitmq.password,
        )

        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=settings.rabbitmq.host,
                port=settings.rabbitmq.port,
                credentials=credentials,
                connection_attempts=2,
                retry_delay=1,
                blocked_connection_timeout=10,
            )
        )

        connection.close()
        return "up"

    except Exception:
        return "down"


def check_minio() -> str:
    try:
        for endpoint in settings.minio.endpoints:
            client = Minio(
                endpoint=endpoint,
                access_key=settings.minio.access_key,
                secret_key=settings.minio.secret_key,
                secure=settings.minio.secure,
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