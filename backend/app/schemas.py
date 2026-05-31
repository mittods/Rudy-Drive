from pydantic import BaseModel, EmailStr
from datetime import datetime


class UserRegister(BaseModel):
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str

class FileCreate(BaseModel):
    filename: str
    size: int
    content_type: str


class FileResponse(BaseModel):
    id: str
    user_id: str
    filename: str
    size: int
    content_type: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class TaskResponse(BaseModel):
    id: str
    file_id: str
    task_type: str
    status: str

    class Config:
        from_attributes = True

class NodeResponse(BaseModel):
    id: str
    hostname: str
    status: str

    class Config:
        from_attributes = True

class FileUploadRequest(BaseModel):
    request_id: str
    user_id: str
    file_id: str
    filename: str
    content_type: str
    size_bytes: int
    data_base64: str

class FileDeleteRequest(BaseModel):
    request_id: str
    user_id: str
    file_id: str
    upload_id: str

class TaskSuccessRequest(BaseModel):
    task_id: str


class TaskFailureRequest(BaseModel):
    task_id: str
    error_message: str

class NodeHeartbeatRequest(BaseModel):
    node: str
    status: str = "alive"
    ip_address: str | None = None 