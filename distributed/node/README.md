# Node Bundle

Este directorio contiene el despliegue de cada PC de almacenamiento.

Úsalo en PC2, PC3 y PC4. Cada máquina necesita su propio `wireguard/wg0.conf` y el mismo `docker-compose.yml`.

## Qué Levanta

- `wireguard-peer`: inicializa la VPN con el archivo `wg0.conf` local
- `minio`: ejecuta un nodo de MinIO dentro de esa red privada

## Antes De Arrancar

1. Copia el `wg0.conf` correspondiente a `node/wireguard/wg0.conf`.
2. Copia `.env.example` a `.env` y revisa credenciales si hace falta.
3. Asegúrate de que `MINIO_CLUSTER_ENDPOINTS` apunte a los endpoints de todos los nodos.

## Arranque

Desde este directorio:

```bash
docker compose up -d
```

## Puertos

- `localhost:9000` expone la API de MinIO del nodo local
- `localhost:9001` expone la consola de MinIO del nodo local

## Notas

- PC2, PC3 y PC4 pueden compartir el mismo layout.
- Si más adelante agregas backend o frontend en estas máquinas, conéctalos a la misma red WireGuard y usa el RabbitMQ de PC1.