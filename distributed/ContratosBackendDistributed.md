# Contrato backend -> distributed

Este documento describe la integración interna del backend con el sistema distributed de PC1.

- PC1: RabbitMQ, workers y heartbeat.
- PC2: backend y un nodo MinIO.
- PC3: frontend y un nodo MinIO.
- PC4: un nodo MinIO.

## 1. Lo que el backend consume

### `node.heartbeat`

El backend consume este mensaje desde RabbitMQ para actualizar el estado de los nodos.

**Queue:** `node.heartbeat`

**Formato del mensaje:**
```json
{
  "node": "pc2",
  "timestamp": "2026-05-31T12:00:00Z",
  "status": "alive"
}
```

**Uso en backend:**
- actualizar `NODES.status`
- actualizar `NODES.last_heartbeat`
- marcar nodos como `DOWN` si expira el tiempo de vida

**Ejemplo Python:**
```python
import json
import pika

params = pika.ConnectionParameters(host="10.0.0.1", port=5672)
conn = pika.BlockingConnection(params)
ch = conn.channel()
ch.queue_declare(queue="node.heartbeat", durable=True)

method, properties, body = ch.basic_get(queue="node.heartbeat", auto_ack=False)
if body:
    message = json.loads(body.decode("utf-8"))
    print(message)
    ch.basic_ack(method.delivery_tag)
```

### MinIO

Para descargar archivos, el backend consume directamente los objetos de MinIO usando la metadata guardada en Postgres.

**Lectura:**
- bucket: `minio_bucket`
- key: `object_key`
- orden: `chunk_index`

**Uso en backend:**
- reconstruir el archivo al vuelo
- responder al usuario por HTTP

**Ejemplo Python:**
```python
from minio import Minio

client = Minio(
    endpoint="10.0.0.2:9000",
    access_key="minioadmin",
    secret_key="minioadmin123",
    secure=False,
)

response = client.get_object("rudy-drive", "file-id/chunk_0")
try:
    data = response.read()
finally:
    response.close()
    response.release_conn()

print(len(data))
```

## 2. Lo que el backend publica

### `upload.chunk`

El backend publica este mensaje para que `worker-upload` guarde el archivo en MinIO.

**Queue:** `upload.chunk`

**Formato del mensaje:**
```json
{
  "request_id": "uuid",
  "user_id": "uuid",
  "file_id": "uuid",
  "filename": "reporte.pdf",
  "content_type": "application/pdf",
  "size_bytes": 184233,
  "data_base64": "..."
}
```

**Ejemplo Python:**
```python
import json
import pika

payload = {
    "request_id": "uuid",
    "user_id": "uuid",
    "file_id": "uuid",
    "filename": "reporte.pdf",
    "content_type": "application/pdf",
    "size_bytes": 184233,
    "data_base64": "JVBERi0xLjQKJ...",
}

conn = pika.BlockingConnection(pika.ConnectionParameters(host="10.0.0.1", port=5672))
ch = conn.channel()
ch.queue_declare(queue="upload.chunk", durable=True)
ch.basic_publish(
    exchange="",
    routing_key="upload.chunk",
    body=json.dumps(payload).encode("utf-8"),
    properties=pika.BasicProperties(delivery_mode=2),
)
conn.close()
```

### `delete.chunk`

El backend publica este mensaje para que `worker-delete` elimine el archivo en MinIO.

**Queue:** `delete.chunk`

**Formato del mensaje:**
```json
{
  "request_id": "uuid",
  "user_id": "uuid",
  "file_id": "uuid",
  "upload_id": "uuid"
}
```

**Ejemplo Python:**
```python
import json
import pika

payload = {
    "request_id": "uuid",
    "user_id": "uuid",
    "file_id": "uuid",
    "upload_id": "uuid",
}

conn = pika.BlockingConnection(pika.ConnectionParameters(host="10.0.0.1", port=5672))
ch = conn.channel()
ch.queue_declare(queue="delete.chunk", durable=True)
ch.basic_publish(
    exchange="",
    routing_key="delete.chunk",
    body=json.dumps(payload).encode("utf-8"),
    properties=pika.BasicProperties(delivery_mode=2),
)
conn.close()
```

## 3. Lo que el backend no consume

- `upload.chunk`: lo consume `worker-upload`.
- `delete.chunk`: lo consume `worker-delete`.
- `download.chunk`: lo consume `worker-download` si se usa reconstrucción asíncrona.

## 4. Regla de descarga

La descarga normal no va por RabbitMQ. El backend lee directamente de MinIO y responde al usuario.

Si se necesita una descarga diferida, entonces se puede usar `download.chunk`, pero no es el flujo normal.

## 5. Diccionario de datos (BDD)

| Tabla | Campo | Tipo de dato | PK/FK | Descripción |
|---|---|---|---|---|
| `USERS` | `id` | `UUID` | `PK` | Identificador único del usuario. |
| `USERS` | `email` | `VARCHAR` |  | Correo electrónico único. |
| `USERS` | `password_hash` | `VARCHAR` |  | Hash de la contraseña del usuario. |
| `USERS` | `created_at` | `TIMESTAMP` |  | Fecha de creación del usuario. |
| `FILES` | `id` | `UUID` | `PK` | Identificador único del archivo lógico. |
| `FILES` | `user_id` | `UUID` | `FK` | Referencia al propietario en `USERS.id`. |
| `FILES` | `filename` | `VARCHAR` |  | Nombre original del archivo. |
| `FILES` | `size` | `BIGINT` |  | Tamaño total del archivo en bytes. |
| `FILES` | `content_type` | `VARCHAR` |  | Tipo MIME del archivo. |
| `FILES` | `status` | `VARCHAR` |  | Estado del archivo (`UPLOADING`, `READY`, `DELETED`, `FAILED`). |
| `FILES` | `created_at` | `TIMESTAMP` |  | Fecha de registro del archivo. |
| `FILES` | `updated_at` | `TIMESTAMP` |  | Última actualización del archivo. |
| `FILE_CHUNKS` | `id` | `UUID` | `PK` | Identificador único del chunk. |
| `FILE_CHUNKS` | `file_id` | `UUID` | `FK` | Referencia al archivo lógico en `FILES.id`. |
| `FILE_CHUNKS` | `chunk_index` | `INT` |  | Índice de orden del chunk para reconstrucción. |
| `FILE_CHUNKS` | `node_id` | `UUID` | `FK` | Nodo asociado al chunk en `NODES.id` (trazabilidad). |
| `FILE_CHUNKS` | `minio_bucket` | `VARCHAR` |  | Bucket de MinIO donde está almacenado el chunk. |
| `FILE_CHUNKS` | `object_key` | `VARCHAR` |  | Clave única del objeto en MinIO. |
| `FILE_CHUNKS` | `etag` | `VARCHAR` |  | Hash/etag de integridad del objeto. |
| `FILE_CHUNKS` | `size_bytes` | `BIGINT` |  | Tamaño del chunk en bytes. |
| `FILE_CHUNKS` | `status` | `VARCHAR` |  | Estado del chunk (`AVAILABLE`, `MISSING`, `REPAIRED`). |
| `FILE_CHUNKS` | `created_at` | `TIMESTAMP` |  | Fecha de almacenamiento del chunk. |
| `NODES` | `id` | `UUID` | `PK` | Identificador único del nodo. |
| `NODES` | `hostname` | `VARCHAR` |  | Nombre del nodo. |
| `NODES` | `ip_address` | `VARCHAR` |  | Dirección IP del nodo. |
| `NODES` | `status` | `VARCHAR` |  | Estado operativo del nodo (`UP`, `DOWN`, `REPAIRING`). |
| `NODES` | `last_heartbeat` | `TIMESTAMP` |  | Última señal de actividad del nodo. |
| `TASKS` | `id` | `UUID` | `PK` | Identificador único de la tarea. |
| `TASKS` | `file_id` | `UUID` | `FK` | Referencia al archivo asociado en `FILES.id`. |
| `TASKS` | `node_id` | `UUID` | `FK` | Nodo asignado o ejecutor en `NODES.id`. |
| `TASKS` | `task_type` | `VARCHAR` |  | Tipo de tarea (`UPLOAD`, `DELETE`, `DOWNLOAD`, `REPAIR`). |
| `TASKS` | `status` | `VARCHAR` |  | Estado de la tarea (`PENDING`, `RUNNING`, `COMPLETED`, `FAILED`). |
| `TASKS` | `retry_count` | `INT` |  | Cantidad de reintentos ejecutados. |
| `TASKS` | `error_message` | `TEXT` |  | Mensaje de error en caso de fallo. |
| `TASKS` | `created_at` | `TIMESTAMP` |  | Fecha de creación de la tarea. |
| `TASKS` | `completed_at` | `TIMESTAMP` |  | Fecha de finalización de la tarea. |
