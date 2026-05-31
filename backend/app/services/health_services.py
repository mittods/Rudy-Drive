from sqlalchemy import text
from sqlalchemy.orm import Session


def check_database(db: Session) -> str:
    try:
        db.execute(text("SELECT 1"))
        return "up"
    except Exception:
        return "down"


def check_rabbitmq() -> str:
    # Pendiente hasta integrar RabbitMQ real
    return "pending"


def check_minio() -> str:
    # Pendiente hasta integrar MinIO real
    return "pending"


def check_workers() -> str:
    # Pendiente hasta tener workers registrados
    return "pending"