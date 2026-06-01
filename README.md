 # Rudy-Drive

 Manual de despliegue de Rudy-Drive.

 Este repositorio se divide en dos despliegues principales:

 - `distributed/`: servidor PC1 con RabbitMQ, workers y heartbeat.
 - `distributed/node/`: bundle que debe repetirse en cada nodo de almacenamiento PC2, PC3 y PC4.

 ## Arquitectura

 - PC1: RabbitMQ, workers, heartbeat y backend de integración.
 - PC2, PC3, PC4: cada nodo ejecuta MinIO en su propio host.
 - Toda la conectividad entre máquinas debe pasar por WireGuard.

 ## Requisitos previos

 Antes de desplegar, cada máquina debe tener:

 - Docker instalado.
 - Docker Compose instalado.
 - WireGuard instalado en el host.
 - Su archivo de configuración `wg0.conf` correspondiente.

 Importante:

 - PC1 también necesita WireGuard instalado y su configuración propia.
 - PC2, PC3 y PC4 deben tener WireGuard instalado localmente.
 - Cada nodo debe cargar su propio `.conf` de WireGuard.
 - El servicio de WireGuard no se levanta en Docker; se levanta en el host.

 ## Red y WireGuard

 La red distribuida usa IPs internas como `10.0.0.1`, `10.0.0.2`, `10.0.0.3` y `10.0.0.4`.

 Recomendación de operación:

 1. Instalar WireGuard en cada host.
 2. Copiar el archivo `.conf` correcto a la máquina correspondiente.
 3. Levantar la interfaz `wg0` en el host antes de arrancar los contenedores.
 4. Verificar conectividad entre nodos con `ping`.

 Ejemplo de verificación:

 ```bash
 ping 10.0.0.2
 ping 10.0.0.3
 ping 10.0.0.4
 ```

 ## Variables de entorno

 ### Despliegue PC1: `distributed/.env`

 Variables recomendadas:

 ```env
 RABBITMQ_DEFAULT_USER=guest
 RABBITMQ_DEFAULT_PASS=guest
 RABBITMQ_HOST=rabbitmq
 RABBITMQ_PORT=5672

 MINIO_ENDPOINTS=10.0.0.2:9000,10.0.0.3:9000,10.0.0.4:9000
 MINIO_ENDPOINT=10.0.0.2:9000
 MINIO_ACCESS_KEY=minioadmin
 MINIO_SECRET_KEY=minioadmin123
 MINIO_SECURE=false
 MINIO_BUCKET=rudy-drive

 BACKEND_URL=http://backend:8000
 BACKEND_HEARTBEAT_URL=http://backend:8000/internal/nodes/heartbeat

 HEARTBEAT_INTERVAL_SECONDS=10
 HEARTBEAT_QUEUE=node.heartbeat

 UPLOAD_CHUNK_SIZE_BYTES=5242880
 STORAGE_REPAIR_INTERVAL_SECONDS=300
 ```

 ### Despliegue nodos: `distributed/node/.env`

 Variables recomendadas:

 ```env
 MINIO_ROOT_USER=minioadmin
 MINIO_ROOT_PASSWORD=minioadmin123
 MINIO_BUCKET=rudy-drive
 MINIO_ENDPOINTS=10.0.0.2:9000,10.0.0.3:9000,10.0.0.4:9000
 MINIO_SECURE=false

 # Opcional, si quieres nombrar cada nodo explícitamente
 NODE_HOSTNAME=pc2
 ```

 ## Despliegue PC1

 PC1 ejecuta RabbitMQ, workers y heartbeat.

 Ruta:

 - `distributed/`

 Pasos:

 1. Configura el archivo `distributed/.env`.
 2. Instala WireGuard en el host de PC1.
 3. Carga el perfil de WireGuard del servidor.
 4. Arranca los servicios.

 Comandos:

 ```bash
 cd distributed
 docker compose up -d --build
 docker compose ps
 ```

 Verificación de logs:

 ```bash
 docker compose logs -f rabbitmq
 docker compose logs -f worker-upload
 docker compose logs -f worker-download
 docker compose logs -f worker-delete
 docker compose logs -f heartbeat
 ```

 ## Despliegue de nodos PC2, PC3 y PC4

 Cada nodo de almacenamiento debe desplegarse por separado usando el bundle `distributed/node/`.

 Ruta:

 - `distributed/node/`

 Antes de arrancar:

 1. Instala WireGuard en el host.
 2. Aplica el archivo `wireguard/wg0.conf/wg0.conf` correspondiente al nodo.
 3. Crea o ajusta `.env` en `distributed/node/`.
 4. Verifica que el host vea a los otros nodos por la VPN.

 Comandos:

 ```bash
 cd distributed/node
 docker compose up -d --build
 docker compose ps
 ```

 Verificación del nodo:

 ```bash
 docker compose logs -f minio
 ```

 ## Orden recomendado de arranque

 1. Levantar WireGuard en PC1, PC2, PC3 y PC4.
 2. Arrancar los nodos `distributed/node/`.
 3. Arrancar `distributed/` en PC1.
 4. Levantar backend y frontend del despliegue principal si aplica.

 ## Despliegue de la aplicación principal

 Si además quieres levantar el backend y frontend del proyecto principal, usa el `docker compose` de la raíz del repositorio.

 Comando:

 ```bash
 docker compose up -d --build
 ```

 Verificación:

 ```bash
 docker compose ps
 docker compose logs -f backend
 docker compose logs -f frontend
 ```

 ## Comandos útiles

 Estado general:

 ```bash
 docker ps
 docker compose ps
 ```

 Health del backend:

 ```bash
 curl http://localhost:3000/api/health
 ```

 Inspección de nodos y chunks:

 ```bash
 curl http://localhost:3000/api/nodes
 curl http://localhost:3000/api/nodes/storage-chunks
 ```

 RabbitMQ:

 ```bash
 docker exec -it rudy-drive-rabbitmq-1 rabbitmqctl list_queues name messages_ready messages_unacknowledged consumers
 ```

 ## Flujo funcional esperado

 - Subida: el backend encola en RabbitMQ con `upload.chunk`.
 - Eliminación: el backend encola en RabbitMQ con `delete.chunk`.
 - Descarga: el backend lee directamente desde MinIO.
 - Heartbeat: el servicio `heartbeat` publica latidos y el backend los guarda en la tabla `nodes`.

 ## Problemas comunes

 - Si el backend no responde, revisa primero WireGuard y RabbitMQ.
 - Si un nodo no aparece, revisa su `wg0.conf` y que esté levantado en el host.
 - Si la descarga falla, comprueba que el archivo esté en estado `ready` y que MinIO tenga los chunks.
 - Si los chunks no se replican, revisa la conectividad entre `10.0.0.2`, `10.0.0.3` y `10.0.0.4`.

 ## Estructura de despliegue

 ```text
 Rudy-Drive/
 ├── docker-compose.yml
 ├── distributed/
 │   ├── .env
 │   ├── docker-compose.yml
 │   ├── heartbeat/
 │   ├── rabbitmq/
 │   ├── workers/
 │   └── node/
 └── frontend/
	 └── rudydrive/
 ```

 ## Nota final

 Cada nodo de almacenamiento debe tener WireGuard instalado, su `wg0.conf` correspondiente y el servicio de `distributed/node` levantado localmente para que MinIO sea accesible desde el clúster.
