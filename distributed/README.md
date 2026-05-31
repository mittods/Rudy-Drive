# Rudy-Drive — Especificación de despliegue para la infraestructura distribuida (PC1)

1. Propósito
----------
Documento que especifica el despliegue y operación de los servicios en `distributed/` (PC1) y del bundle de nodos `distributed/node/` (PC2..PC4).

2. Alcance
---------
Instrucciones operativas para levantar y verificar el servidor (PC1) y los nodos de almacenamiento. No incluye desarrollo del backend o frontend, salvo los contratos de integración del SDK compartido (`workers/shared/`).

3. Arquitectura
---------------

- PC1 (servidor):
  - `rabbitmq`: broker AMQP (puertos 5672, 15672).
  - `worker-upload`, `worker-download`, `worker-delete`: consumidores de colas.
  - `heartbeat`: publica latidos en `node.heartbeat`.
  - WireGuard instalado localmente en el host del servidor (ej. `10.0.0.1`).

- PC2..PC4 (nodos de almacenamiento):
  - WireGuard instalado localmente en cada host con IP en `10.0.0.0/24`.
  - `minio`: servidor de objetos; cada nodo monta rutas locales (p. ej. `/data`, `/data2`) que se exponen como endpoints para el clúster.

La comunicación inter-nodo y servidor se realiza por la red WireGuard instalada en cada host; MinIO forma el clúster usando endpoints HTTP accesibles por las IPs internas de la VPN.

4. Componentes y responsabilidades
---------------------------------

- `rabbitmq`: encola trabajos y soporta colas durables.
- `worker-upload`: almacena chunks en MinIO.
- `worker-download`: reconstruye objetos desde MinIO.
- `worker-delete`: elimina prefijos relacionados a un `upload_id`.
- `heartbeat`: monitor de liveness en `node.heartbeat`.
- WireGuard del host: conectividad VPN.
- `minio` (nodos): backend de objetos con despliegue distribuido.

5. Requisitos previos
---------------------

- Docker y Docker Compose para RabbitMQ, workers y MinIO.
- WireGuard instalado localmente en cada máquina.
- Archivos `wg0.conf` (servidor y peers) con claves generadas para entregar a cada dispositivo.

6. Variables de entorno
-----------------------

Defínalas en `.env` dentro de `distributed/` o `distributed/node/` según corresponda.

- `RABBITMQ_DEFAULT_USER` — usuario RabbitMQ (default: `rudy`).
- `RABBITMQ_DEFAULT_PASS` — contraseña RabbitMQ (default: `rudy123`).
- `RABBITMQ_HOST` — host broker (default: `rabbitmq`).
- `RABBITMQ_PORT` — puerto AMQP (default: `5672`).

- `MINIO_ROOT_USER` — access key MinIO (default: `minioadmin`).
- `MINIO_ROOT_PASSWORD` — secret key MinIO (default: `minioadmin123`).
- `MINIO_BUCKET` — bucket por defecto (default: `rudy-drive`).
- `MINIO_ENDPOINT` — endpoint único (compatibilidad), ej. `10.0.0.2:9000`.
- `MINIO_ENDPOINTS` — CSV de endpoints probados por los clientes en orden; default: `10.0.0.2:9000`.
- `MINIO_SECURE` — `true|false` (default: `false`).

- `UPLOAD_CHUNK_SIZE_BYTES` — tamaño de chunk (default: `5242880`).
- `QUEUE_MAX_RETRIES` — reintentos para mensajes fallidos (default: `3`).

- `NODE_HOSTNAME` — nombre opcional del nodo.
- `MINIO_CLUSTER_ENDPOINTS` — lista space-separated de URIs para arrancar MinIO en modo distribuido (ej.: `http://10.0.0.2/data http://10.0.0.2/data2 ...`).

7. Procedimiento de despliegue
-----------------------------

7.1 PC1 (servidor)

1. Colocar/editar `distributed/.env` con los valores necesarios.
2. Instalar WireGuard en el host y cargar el perfil local del servidor usando `distributed/wireguard/server/wg0.conf`.
3. Arrancar Docker:

```bash
cd distributed
docker compose up -d
```

Esto inicia RabbitMQ, workers y heartbeat.

7.2 PC2..PC4 (nodos)

1. Instalar WireGuard en el host del nodo y cargar el perfil local correspondiente.
2. Mantener disponible el archivo `distributed/node/wireguard/wg0.conf/wg0.conf` como entrega para ese dispositivo.
3. Crear `distributed/node/.env` desde `distributed/node/.env.example` y ajustar `MINIO_CLUSTER_ENDPOINTS` y `NODE_HOSTNAME`.
4. Arrancar en la máquina del nodo:

```bash
cd distributed/node
docker compose up -d
```

Cada nodo levantará `minio`; WireGuard corre en el host.

8. Verificaciones operativas
---------------------------

Comprobaciones básicas:

```bash
# En PC1
docker compose ps
docker compose logs -f rabbitmq

# En un nodo
docker compose ps
docker compose logs -f minio

# Health demo (si aplica)
curl http://localhost:8000/health
```

9. Ejemplo: flujo de subida
--------------------------

1. El backend publica en RabbitMQ un mensaje `upload.chunk` con `upload_id` y `data_base64`.
2. `worker-upload` consume, fragmenta en chunks y escribe objetos `upload_id/chunk_<n>` en MinIO.

Publicación mínima (Python):

```python
from workers.shared.config import load_settings
from workers.shared.rabbitmq_client import RabbitMQClient

settings = load_settings()
client = RabbitMQClient(settings.rabbitmq)
client.publish('upload.chunk', {'upload_id': 'upload-uuid', 'data_base64': 'YWJj'})
```

10. Tolerancia a fallos y recuperación
------------------------------------

- MinIO: usa erasure coding; la capacidad de recuperación depende de configuración (número de drives/paridad). Perder un nodo no implica pérdida inmediata si se mantiene redundancia suficiente.
- Workers/clients: el cliente implementa fallback probando `MINIO_ENDPOINTS` en orden hasta encontrar un endpoint operativo.
- Mensajería: los workers republican mensajes fallidos hasta `QUEUE_MAX_RETRIES`; si el contador se excede, el mensaje queda registrado y se descarta.

11. Operaciones comunes
-----------------------

- Añadir nodo: provisionar máquina, registrar su clave pública en el servidor WireGuard, instalar el perfil local correcto, actualizar `MINIO_CLUSTER_ENDPOINTS` y arrancar MinIO.
- Reemplazar nodo: añadir nodo nuevo y seguir las rutinas de reparación/rebalance de MinIO si procede.

12. Referencias
--------------

- Código y contratos: `workers/shared/config.py`, `workers/shared/rabbitmq_client.py`, `workers/shared/minio_client.py`, `workers/shared/chunk_storage.py`, `workers/shared/chunk_recovery.py`, `workers/shared/health.py`.
- Bundle nodos: `distributed/node/docker-compose.yml`, `distributed/node/.env.example`, `distributed/node/wireguard/wg0.conf/wg0.conf`.
