from datetime import datetime
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi.responses import StreamingResponse


from app.services.message_bus import publish_message, get_file_stream
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
from app.database import engine, Base, get_db
from app.models import User, File, Task, FileChunk, Node
from app.database import Base, get_db
from app.services.health_service import (
    check_database,
    check_rabbitmq,
    check_minio,
    check_workers
)

app = FastAPI(
    title="Rudy Drive API",
    description="Backend/API Gateway para sistema de almacenamiento distribuido",
    version="1.0.0"
)

Base.metadata.create_all(bind=engine)
security = HTTPBearer()

@app.get("/")
def home():
    return {"message": "Rudy Drive API funcionando"}

@app.get("/me")
def get_me(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):

    token = credentials.credentials

    email = verify_token(token)

    return {
        "email": email,
        "message": "Token válido"
    }

@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    database_status = "down"
    rabbitmq_status = "pending"
    minio_status = "pending"
    workers_status = "pending"

    try:
        db.execute(text("SELECT 1"))
        database_status = "up"
    except Exception:
        database_status = "down"

    overall_status = "healthy" if database_status == "up" else "unhealthy"

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
        "token_type": "bearer"
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
    ).first()

    if not chunk:
        raise HTTPException(
            status_code=404,
            detail="No existe metadata de almacenamiento para este archivo"
        )

    try:
        file_stream = get_file_stream(
            bucket=chunk.minio_bucket,
            object_key=chunk.object_key
        )

        return StreamingResponse(
            file_stream,
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

    elif task.task_type == "delete":
        file.status = "deleted"

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