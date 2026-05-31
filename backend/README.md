# Rudy Drive - Contratos de Integración Backend

## 1. Arquitectura General

```text
PC1: RabbitMQ, workers y heartbeat
PC2: Backend FastAPI y nodo MinIO
PC3: Frontend y nodo MinIO
PC4: Nodo MinIO
```

El backend es responsable de:

```text
- API REST
- Autenticación JWT
- Metadata en PostgreSQL
- Estados de archivos
- Estados de tareas
- Estados de nodos
- Publicación de mensajes RabbitMQ
- Descarga directa desde MinIO
```

Los workers son responsables de:

```text
- Consumir RabbitMQ
- Procesar subida
- Procesar eliminación
- Operar sobre MinIO
- Informar éxito o fallo al backend
- Enviar heartbeat
```

---

# 2. Variables de Entorno

Archivo `.env`:

```env
RABBITMQ_HOST=10.0.0.1
RABBITMQ_PORT=5672

MINIO_ENDPOINT=10.0.0.2:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin123
MINIO_SECURE=false
```

---

# 3. Subida de Archivos

## Endpoint

```http
POST /files
```

## Header

```http
Authorization: Bearer <TOKEN>
```

## Payload HTTP

```json
{
  "request_id": "uuid",
  "user_id": "uuid",
  "file_id": "uuid",
  "filename": "reporte.pdf",
  "content_type": "application/pdf",
  "size_bytes": 184233,
  "data_base64": "JVBERi0xLjQKJ..."
}
```

## Acción del Backend

El backend:

```text
1. Valida usuario JWT
2. Crea registro en files
3. Deja FILE.status = pending
4. Crea task de tipo upload
5. Deja TASK.status = pending
6. Publica mensaje RabbitMQ en upload.chunk
```

## Mensaje RabbitMQ

Queue:

```text
upload.chunk
```

Payload:

```json
{
  "task_id": "uuid",
  "request_id": "uuid",
  "user_id": "uuid",
  "file_id": "uuid",
  "filename": "reporte.pdf",
  "content_type": "application/pdf",
  "size_bytes": 184233,
  "data_base64": "JVBERi0xLjQKJ..."
}
```

## Respuesta HTTP

```json
{
  "task_id": "uuid",
  "status": "queued"
}
```

---

# 4. Eliminación de Archivos

## Endpoint

```http
DELETE /files/{file_id}
```

## Header

```http
Authorization: Bearer <TOKEN>
```

## Payload HTTP

```json
{
  "request_id": "uuid",
  "user_id": "uuid",
  "file_id": "uuid",
  "upload_id": "uuid"
}
```

## Acción del Backend

El backend:

```text
1. Valida usuario JWT
2. Verifica que file_id del body coincida con file_id de la URL
3. Cambia FILE.status = deleting
4. Crea task de tipo delete
5. Deja TASK.status = pending
6. Publica mensaje RabbitMQ en delete.chunk
```

## Mensaje RabbitMQ

Queue:

```text
delete.chunk
```

Payload:

```json
{
  "task_id": "uuid",
  "request_id": "uuid",
  "user_id": "uuid",
  "file_id": "uuid",
  "upload_id": "uuid"
}
```

## Respuesta HTTP

```json
{
  "task_id": "uuid",
  "status": "queued"
}
```

---

# 5. Descarga de Archivos

## Endpoint

```http
GET /files/{file_id}/download
```

## Header

```http
Authorization: Bearer <TOKEN>
```

## Acción del Backend

El backend:

```text
1. Valida usuario JWT
2. Busca archivo en PostgreSQL
3. Verifica que FILE.status = ready
4. Busca metadata en file_chunks
5. Lee bucket y object_key
6. Descarga desde MinIO
7. Devuelve archivo por StreamingResponse
```

## Metadata utilizada

Tabla:

```text
file_chunks
```

Campos:

```text
minio_bucket
object_key
chunk_index
```

## Regla

```text
La descarga normal NO usa RabbitMQ.
El backend lee directamente desde MinIO.
```

---

# 6. Éxito de Tarea

## Endpoint interno

```http
POST /internal/tasks/success
```

## Payload

```json
{
  "task_id": "uuid"
}
```

## Acción del Backend

Si la tarea es `upload`:

```text
TASK.status = completed
FILE.status = ready
```

Si la tarea es `delete`:

```text
TASK.status = completed
FILE.status = deleted
```

## Respuesta

```json
{
  "task_id": "uuid",
  "task_status": "completed",
  "file_id": "uuid",
  "file_status": "ready"
}
```

---

# 7. Fallo de Tarea

## Endpoint interno

```http
POST /internal/tasks/failure
```

## Payload

```json
{
  "task_id": "uuid",
  "error_message": "detalle del error"
}
```

## Acción del Backend

```text
TASK.status = failed
TASK.error_message = error_message
TASK.retry_count += 1
FILE.status = failed
```

## Regla de reintentos

```text
Los reintentos son responsabilidad del worker/RabbitMQ.
El backend solo registra el fallo final informado por el worker.
```

## Respuesta

```json
{
  "task_id": "uuid",
  "task_status": "failed",
  "file_id": "uuid",
  "file_status": "failed",
  "retry_count": 1,
  "error_message": "detalle del error"
}
```

---

# 8. Heartbeat de Nodos

## Endpoint interno

```http
POST /internal/nodes/heartbeat
```

## Payload

```json
{
  "node": "pc2",
  "status": "alive",
  "ip_address": "10.0.0.2"
}
```

## Acción del Backend

Si el nodo no existe:

```text
Crea registro en nodes
```

Si el nodo existe:

```text
Actualiza status
Actualiza ip_address
Actualiza last_heartbeat
```

## Respuesta

```json
{
  "node_id": "uuid",
  "hostname": "pc2",
  "ip_address": "10.0.0.2",
  "status": "alive",
  "last_heartbeat": "2026-05-31T12:00:00"
}
```

---

# 9. Listado de Nodos

## Endpoint

```http
GET /nodes
```

## Header

```http
Authorization: Bearer <TOKEN>
```

## Respuesta

```json
[
  {
    "node_id": "uuid",
    "hostname": "pc2",
    "ip_address": "10.0.0.2",
    "status": "alive",
    "last_heartbeat": "2026-05-31T12:00:00"
  }
]
```

---

# 10. Consulta de Estado de Tareas

## Endpoint

```http
GET /tasks/{task_id}
```

## Header

```http
Authorization: Bearer <TOKEN>
```

## Respuesta

```json
{
  "task_id": "uuid",
  "file_id": "uuid",
  "task_type": "upload",
  "status": "pending",
  "retry_count": 0,
  "error_message": null
}
```

---

# 11. Health Check

## Endpoint

```http
GET /health
```

## Respuesta

```json
{
  "status": "healthy",
  "database": "up",
  "rabbitmq": "pending",
  "minio": "pending",
  "workers": "pending"
}
```

---

# 12. Ejemplo Python - Upload

```python
import requests

url = "http://10.0.0.2:8000/files"

payload = {
    "request_id": "uuid",
    "user_id": "uuid",
    "file_id": "uuid",
    "filename": "reporte.pdf",
    "content_type": "application/pdf",
    "size_bytes": 184233,
    "data_base64": "JVBERi0xLjQKJ..."
}

resp = requests.post(
    url,
    json=payload,
    headers={
        "Authorization": "Bearer <TOKEN>"
    }
)

print(resp.json())
```

---

# 13. Ejemplo Python - Delete

```python
import requests

url = "http://10.0.0.2:8000/files/uuid-del-archivo"

payload = {
    "request_id": "uuid",
    "user_id": "uuid",
    "file_id": "uuid-del-archivo",
    "upload_id": "uuid"
}

resp = requests.delete(
    url,
    json=payload,
    headers={
        "Authorization": "Bearer <TOKEN>"
    }
)

print(resp.json())
```

---

# 14. Ejemplo Python - Worker informa éxito

```python
import requests

url = "http://10.0.0.2:8000/internal/tasks/success"

payload = {
    "task_id": "uuid"
}

resp = requests.post(
    url,
    json=payload
)

print(resp.json())
```

---

# 15. Ejemplo Python - Worker informa fallo

```python
import requests

url = "http://10.0.0.2:8000/internal/tasks/failure"

payload = {
    "task_id": "uuid",
    "error_message": "No se pudo guardar el archivo en MinIO"
}

resp = requests.post(
    url,
    json=payload
)

print(resp.json())
```

---

# 16. Ejemplo Python - Heartbeat Nodo

```python
import requests

url = "http://10.0.0.2:8000/internal/nodes/heartbeat"

payload = {
    "node": "pc2",
    "status": "alive",
    "ip_address": "10.0.0.2"
}

resp = requests.post(
    url,
    json=payload
)

print(resp.json())
```
