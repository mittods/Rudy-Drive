from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, BigInteger, Text
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.database import Base


def generate_uuid():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    files = relationship("File", back_populates="user")


class File(Base):
    __tablename__ = "files"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)

    user_id = Column(
        String,
        ForeignKey("users.id"),
        nullable=False
    )

    filename = Column(String(255), nullable=False)
    size = Column(BigInteger, nullable=False)
    content_type = Column(String(100), nullable=False)
    status = Column(String(50), default="pending")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    user = relationship("User", back_populates="files")
    chunks = relationship("FileChunk", back_populates="file")
    tasks = relationship("Task", back_populates="file")


class FileChunk(Base):
    __tablename__ = "file_chunks"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)

    file_id = Column(
        String,
        ForeignKey("files.id"),
        nullable=False
    )

    chunk_index = Column(Integer, nullable=False)

    node_id = Column(
        String,
        ForeignKey("nodes.id"),
        nullable=True
    )

    minio_bucket = Column(String(255), nullable=True)
    object_key = Column(String(500), nullable=True)
    etag = Column(String(255), nullable=True)
    size_bytes = Column(BigInteger, nullable=False)
    status = Column(String(50), default="pending")

    created_at = Column(DateTime, default=datetime.utcnow)

    file = relationship("File", back_populates="chunks")
    node = relationship("Node", back_populates="chunks")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)

    file_id = Column(
        String,
        ForeignKey("files.id"),
        nullable=False
    )

    node_id = Column(
        String,
        ForeignKey("nodes.id"),
        nullable=True
    )

    task_type = Column(String(100), nullable=False)
    status = Column(String(50), default="pending")
    retry_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    file = relationship("File", back_populates="tasks")
    node = relationship("Node", back_populates="tasks")


class Node(Base):
    __tablename__ = "nodes"

    id = Column(String, primary_key=True, index=True, default=generate_uuid)

    hostname = Column(String(255), nullable=False)
    ip_address = Column(String(100), nullable=True)
    status = Column(String(50), default="active")
    last_heartbeat = Column(DateTime, nullable=True)

    chunks = relationship("FileChunk", back_populates="node")
    tasks = relationship("Task", back_populates="node")