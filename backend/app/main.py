from base64 import b64decode
from datetime import datetime
import io
import os
import threading
import time
from typing import Iterable

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from minio import Minio
from minio.error import S3Error
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
import urllib3


from app.services.message_bus import publish_message, get_file_stream
from app.config import load_settings
from app.schemas import (
    UserRegister, 
    UserLogin,
    FileCreate,
    FileResponse,
    FileUploadRequest,
    FileDeleteRequest,
    TaskResponse,
    NodeResponse,
    TaskSuccessRequest,
    TaskFailureRequest,
    NodeHeartbeatRequest
)
from app.auth import (
    hash_password,
    verify_password,
    create_access_token,
    verify_token,
    get_current_user
)
from app.database import engine, Base, get_db, SessionLocal
from app.models import User, File, Task, FileChunk, Node
from app.services.health_services import (
    check_database,
    check_rabbitmq,
    check_minio,
    check_workers
)


settings = load_settings()

app = FastAPI(
    title="Rudy Drive API",
    description="Backend/API Gateway para sistema de almacenamiento distribuido",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)
security = HTTPBearer()


def _chunk_object_name(file_id: str, chunk_index: int) -> str:
    return f"{file_id}/chunk_{chunk_index}"


def _build_file_chunks(file_id: str, raw_data: bytes) -> list[FileChunk]:
    records: list[FileChunk] = []
    for chunk_index, start in enumerate(range(0, len(raw_data), settings.upload_chunk_size_bytes)):
        chunk = raw_data[start : start + settings.upload_chunk_size_bytes]
        records.append(
            FileChunk(
                file_id=file_id,
                chunk_index=chunk_index,
                minio_bucket=settings.minio.bucket,
                object_key=_chunk_object_name(file_id, chunk_index),
                size_bytes=len(chunk),
                status="pending",
            )
        )
    return records


def _build_minio_client(endpoint: str) -> Minio:
    http_client = urllib3.PoolManager(
        timeout=urllib3.Timeout(connect=2, read=8),
        retries=False,
    )
    return Minio(
        endpoint=endpoint,
        access_key=settings.minio.access_key,
        secret_key=settings.minio.secret_key,
        secure=settings.minio.secure,
        http_client=http_client,
    )


def _collect_known_chunks(db: Session) -> list[FileChunk]:
    return db.query(FileChunk).filter(
        FileChunk.object_key.isnot(None),
        FileChunk.minio_bucket.isnot(None)
    ).order_by(
        FileChunk.file_id.asc(),
        FileChunk.chunk_index.asc()
    ).all()


def _repair_minio_endpoint(
    target_endpoint: str,
    chunks: list[FileChunk],
    candidate_endpoints: tuple[str, ...]
) -> dict[str, int | str]:
    target_client = _build_minio_client(target_endpoint)
    source_endpoints = [endpoint for endpoint in candidate_endpoints if endpoint != target_endpoint]

    copied = 0
    skipped = 0
    errors = 0

    for chunk in chunks:
        try:
            target_client.stat_object(chunk.minio_bucket, chunk.object_key)
            continue
        except S3Error as exc:
            if exc.code != "NoSuchKey":
                errors += 1
                continue

        repaired = False
        for source_endpoint in source_endpoints:
            source_client = _build_minio_client(source_endpoint)
            try:
                response = source_client.get_object(chunk.minio_bucket, chunk.object_key)
                try:
                    payload = response.read()
                finally:
                    response.close()
                    response.release_conn()

                target_client.put_object(
                    bucket_name=chunk.minio_bucket,
                    object_name=chunk.object_key,
                    data=io.BytesIO(payload),
                    length=len(payload),
                    content_type="application/octet-stream",
                )
                copied += 1
                repaired = True
                break
            except Exception:
                continue

        if not repaired:
            skipped += 1

    return {
        "endpoint": target_endpoint,
        "copied": copied,
        "skipped": skipped,
        "errors": errors,
    }


def _repair_storage_cluster(db: Session, target_endpoint: str | None = None) -> dict:
    chunks = _collect_known_chunks(db)
    candidate_endpoints = tuple(settings.minio.endpoints) or (settings.minio.endpoint,)

    endpoints = [target_endpoint] if target_endpoint else list(candidate_endpoints)
    reports = []
    for endpoint in endpoints:
        if endpoint not in candidate_endpoints:
            continue
        try:
            reports.append(_repair_minio_endpoint(endpoint, chunks, candidate_endpoints))
        except Exception as exc:
            reports.append({
                "endpoint": endpoint,
                "copied": 0,
                "skipped": len(chunks),
                "errors": len(chunks),
                "error": str(exc),
            })

    return {
        "known_chunks": len(chunks),
        "repairs": reports,
    }


def _storage_repair_daemon() -> None:
    interval_seconds = int(os.getenv("STORAGE_REPAIR_INTERVAL_SECONDS", "300"))
    while True:
        time.sleep(interval_seconds)
        _run_storage_repair_job()


def _run_storage_repair_job(target_endpoint: str | None = None) -> dict:
    db = SessionLocal()
    try:
        result = _repair_storage_cluster(db, target_endpoint=target_endpoint)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@app.on_event("startup")
def start_storage_repair_daemon() -> None:
    thread = threading.Thread(target=_storage_repair_daemon, daemon=True)
    thread.start()

@app.get("/")
def home():
    return {"message": "Rudy Drive API funcionando"}

@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    database_status = check_database(db)
    rabbitmq_status = check_rabbitmq()
    minio_status = check_minio()
    workers_status = check_workers(db)

    overall_status = "healthy"

    if (
        database_status == "down"
        or rabbitmq_status == "down"
        or minio_status == "down"
        or workers_status == "down"
    ):
        overall_status = "unhealthy"

    return {
        "status": overall_status,
        "database": database_status,
        "rabbitmq": rabbitmq_status,
        "minio": minio_status,
        "workers": workers_status
    }

@app.post("/register")
def register(
    user: UserRegister,
    db: Session = Depends(get_db)
):

    existing_user = db.query(User).filter(
        User.email == user.email
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="El usuario ya existe"
        )

    new_user = User(
        email=user.email,
        password_hash=hash_password(user.password)
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "user_id": new_user.id,
        "message": "Usuario registrado correctamente"
    }


@app.post("/login")
def login(
    user: UserLogin,
    db: Session = Depends(get_db)
):

    db_user = db.query(User).filter(
        User.email == user.email
    ).first()

    if not db_user:
        raise HTTPException(
            status_code=401,
            detail="Credenciales incorrectas"
        )

    if not verify_password(
        user.password,
        db_user.password_hash
    ):
        raise HTTPException(
            status_code=401,
            detail="Credenciales incorrectas"
        )

    token = create_access_token(
        data={"sub": db_user.email}
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": db_user.id,
        "email": db_user.email,
    }

@app.post("/files")
def create_file(
    file_data: FileUploadRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if file_data.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="No puedes subir archivos para otro usuario"
        )

    new_file = File(
        id=file_data.file_id,
        user_id=current_user.id,
        filename=file_data.filename,
        size=file_data.size_bytes,
        content_type=file_data.content_type,
        status="pending"
    )

    db.add(new_file)
    db.commit()
    db.refresh(new_file)

    raw_data = b64decode(file_data.data_base64)
    file_chunks = _build_file_chunks(new_file.id, raw_data)
    db.add_all(file_chunks)
    db.commit()

    new_task = Task(
        file_id=new_file.id,
        task_type="upload",
        status="pending"
    )

    db.add(new_task)
    db.commit()
    db.refresh(new_task)
    publish_message(
        "upload.chunk",
        {
            "task_id": new_task.id,
            "request_id": file_data.request_id,
            "user_id": current_user.id,
            "file_id": new_file.id,
            "filename": new_file.filename,
            "content_type": new_file.content_type,
            "size_bytes": new_file.size,
            "data_base64": file_data.data_base64
        }
    )    
    return {
        "task_id": new_task.id,
        "status": "queued"
    }

@app.get("/me")
def get_me(
    current_user: User = Depends(get_current_user)
):

    return {
        "user_id": current_user.id,
        "email": current_user.email,
        "message": "Token válido"
    }

@app.get("/files")
def list_files(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    files = db.query(File).filter(
        File.user_id == current_user.id
    ).all()

    return files

@app.get("/files/{file_id}")
def get_file(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    file = db.query(File).filter(
        File.id == file_id,
        File.user_id == current_user.id
    ).first()

    if not file:
        raise HTTPException(
            status_code=404,
            detail="Archivo no encontrado"
        )

    return file

@app.get("/files/{file_id}/download")
def download_file(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    file = db.query(File).filter(
        File.id == file_id,
        File.user_id == current_user.id
    ).first()

    if not file:
        raise HTTPException(
            status_code=404,
            detail="Archivo no encontrado"
        )

    if file.status != "ready":
        raise HTTPException(
            status_code=409,
            detail="Archivo no disponible para descarga"
        )

    chunk = db.query(FileChunk).filter(
        FileChunk.file_id == file.id
    ).order_by(
        FileChunk.chunk_index.asc()
    ).all()

    if not chunk:
        raise HTTPException(
            status_code=404,
            detail="No existe metadata de almacenamiento para este archivo"
        )

    try:
        candidate_endpoints = tuple(settings.minio.endpoints) or (settings.minio.endpoint,)
        chunk_endpoints: list[str] = []

        for item in chunk:
            selected_endpoint: str | None = None
            last_error: Exception | None = None

            for endpoint in candidate_endpoints:
                client = _build_minio_client(endpoint)
                try:
                    client.stat_object(item.minio_bucket, item.object_key)
                    selected_endpoint = endpoint
                    break
                except S3Error as exc:
                    if exc.code == "NoSuchKey":
                        continue
                    last_error = exc
                except Exception as exc:
                    last_error = exc

            if selected_endpoint is None:
                if last_error is not None:
                    raise last_error
                raise HTTPException(
                    status_code=404,
                    detail=f"Chunk no encontrado para el archivo {file.id}"
                )

            chunk_endpoints.append(selected_endpoint)

        def stream_file():
            for item, endpoint in zip(chunk, chunk_endpoints):
                client = _build_minio_client(endpoint)
                response = client.get_object(item.minio_bucket, item.object_key)
                try:
                    for part in response.stream(32 * 1024):
                        yield part
                finally:
                    response.close()
                    response.release_conn()

        return StreamingResponse(
            stream_file(),
            media_type=file.content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{file.filename}"'
            }
        )

    except NotImplementedError as e:
        raise HTTPException(
            status_code=501,
            detail=str(e)
        )

@app.delete("/files/{file_id}")
def delete_file(
    file_id: str,
    delete_data: FileDeleteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if delete_data.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="No puedes borrar archivos de otro usuario"
        )

    if delete_data.file_id != file_id:
        raise HTTPException(
            status_code=400,
            detail="El file_id del body no coincide con el file_id de la URL"
        )

    file = db.query(File).filter(
        File.id == file_id,
        File.user_id == current_user.id
    ).first()

    if not file:
        raise HTTPException(
            status_code=404,
            detail="Archivo no encontrado"
        )

    file.status = "deleting"

    new_task = Task(
        file_id=file.id,
        task_type="delete",
        status="pending"
    )

    db.add(new_task)
    db.commit()
    db.refresh(new_task)

    publish_message(
        "delete.chunk",
        {
            "task_id": new_task.id,
            "request_id": delete_data.request_id,
            "user_id": current_user.id,
            "file_id": file.id,
            "upload_id": delete_data.upload_id
        }
    )

    return {
        "task_id": new_task.id,
        "status": "queued"
    }

@app.get("/tasks/{task_id}")
def get_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    task = db.query(Task).join(File).filter(
        Task.id == task_id,
        File.user_id == current_user.id
    ).first()

    if not task:
        raise HTTPException(
            status_code=404,
            detail="Task no encontrada"
        )

    return {
        "task_id": task.id,
        "file_id": task.file_id,
        "task_type": task.task_type,
        "status": task.status,
        "retry_count": task.retry_count,
        "error_message": task.error_message
    }

@app.post("/internal/tasks/success")
def task_success(
    result: TaskSuccessRequest,
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(
        Task.id == result.task_id
    ).first()

    if not task:
        raise HTTPException(
            status_code=404,
            detail="Task no encontrada"
        )

    file = db.query(File).filter(
        File.id == task.file_id
    ).first()

    if not file:
        raise HTTPException(
            status_code=404,
            detail="Archivo asociado no encontrado"
        )

    task.status = "completed"
    task.completed_at = datetime.utcnow()

    if task.task_type == "upload":
        file.status = "ready"
        for chunk in db.query(FileChunk).filter(FileChunk.file_id == file.id).all():
            chunk.status = "ready"

    elif task.task_type == "delete":
        file.status = "deleted"
        db.query(FileChunk).filter(FileChunk.file_id == file.id).delete(synchronize_session=False)

    db.commit()

    return {
        "task_id": task.id,
        "task_status": task.status,
        "file_id": file.id,
        "file_status": file.status
    }

@app.post("/internal/tasks/failure")
def task_failure(
    result: TaskFailureRequest,
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(
        Task.id == result.task_id
    ).first()

    if not task:
        raise HTTPException(
            status_code=404,
            detail="Task no encontrada"
        )

    file = db.query(File).filter(
        File.id == task.file_id
    ).first()

    if not file:
        raise HTTPException(
            status_code=404,
            detail="Archivo asociado no encontrado"
        )

    task.status = "failed"
    task.error_message = result.error_message
    task.retry_count = task.retry_count + 1

    file.status = "failed"
    for chunk in db.query(FileChunk).filter(FileChunk.file_id == file.id).all():
        chunk.status = "failed"

    db.commit()

    return {
        "task_id": task.id,
        "task_status": task.status,
        "file_id": file.id,
        "file_status": file.status,
        "retry_count": task.retry_count,
        "error_message": task.error_message
    }

@app.get("/tasks")
def list_tasks(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    tasks = db.query(Task).join(File).filter(
        File.user_id == current_user.id
    ).all()

    return [
        {
            "task_id": task.id,
            "file_id": task.file_id,
            "task_type": task.task_type,
            "status": task.status,
            "retry_count": task.retry_count,
            "error_message": task.error_message,
            "created_at": task.created_at,
            "completed_at": task.completed_at
        }
        for task in tasks
    ]

@app.post("/internal/nodes/heartbeat")
def node_heartbeat(
    heartbeat: NodeHeartbeatRequest,
    db: Session = Depends(get_db)
):
    node = db.query(Node).filter(
        Node.hostname == heartbeat.node
    ).first()

    if not node:
        node = Node(
            hostname=heartbeat.node,
            ip_address=heartbeat.ip_address,
            status=heartbeat.status,
            last_heartbeat=datetime.utcnow()
        )

        db.add(node)

    else:
        node.status = heartbeat.status
        node.ip_address = heartbeat.ip_address or node.ip_address
        node.last_heartbeat = datetime.utcnow()

    db.commit()
    db.refresh(node)

    return {
        "node_id": node.id,
        "hostname": node.hostname,
        "ip_address": node.ip_address,
        "status": node.status,
        "last_heartbeat": node.last_heartbeat
    }

@app.get("/nodes")
def list_nodes(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    nodes = db.query(Node).all()

    return [
        {
            "node_id": node.id,
            "hostname": node.hostname,
            "ip_address": node.ip_address,
            "status": node.status,
            "last_heartbeat": node.last_heartbeat
        }
        for node in nodes
    ]


@app.get("/nodes/storage-chunks")
def list_storage_nodes_chunks(
    db: Session = Depends(get_db)
):
    known_chunks = db.query(FileChunk).filter(
        FileChunk.object_key.isnot(None),
        FileChunk.minio_bucket.isnot(None)
    ).order_by(FileChunk.file_id.asc(), FileChunk.chunk_index.asc()).all()

    candidate_endpoints = tuple(settings.minio.endpoints) or (settings.minio.endpoint,)
    nodes: list[dict] = []

    for endpoint in candidate_endpoints:
        node_report = {
            "endpoint": endpoint,
            "status": "up",
            "chunk_count": 0,
            "chunks": []
        }

        try:
            client = _build_minio_client(endpoint)
            for chunk in known_chunks:
                try:
                    stat = client.stat_object(chunk.minio_bucket, chunk.object_key)
                except S3Error as exc:
                    if exc.code == "NoSuchKey":
                        continue
                    raise

                node_report["chunks"].append(
                    {
                        "chunk_id": chunk.id,
                        "file_id": chunk.file_id,
                        "chunk_index": chunk.chunk_index,
                        "bucket": chunk.minio_bucket,
                        "object_key": chunk.object_key,
                        "size_bytes": stat.size,
                        "etag": stat.etag,
                    }
                )
        except Exception as exc:
            node_report["status"] = "down"
            node_report["error"] = str(exc)
            node_report["chunks"] = []

        node_report["chunk_count"] = len(node_report["chunks"])
        nodes.append(node_report)

    return {
        "total_known_chunks": len(known_chunks),
        "nodes": nodes
    }


@app.post("/internal/storage/repair")
def repair_storage_nodes(
    target_endpoint: str | None = None,
):
    thread = threading.Thread(
        target=_run_storage_repair_job,
        kwargs={"target_endpoint": target_endpoint},
        daemon=True,
    )
    thread.start()
    return {
        "status": "accepted",
        "target_endpoint": target_endpoint,
        "message": "Storage repair started in background",
    }