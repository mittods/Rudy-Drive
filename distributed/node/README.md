# Node Bundle

Este directorio contiene el despliegue de cada PC de almacenamiento.

Úsalo en PC2, PC3 y PC4. Cada máquina necesita su propio archivo de WireGuard instalado localmente y el mismo `docker-compose.yml`.

## Qué Levanta

- `minio`: ejecuta un nodo de MinIO standalone en el host local

## Antes De Arrancar

1. Instala WireGuard en el host y carga el `wg0.conf` correspondiente.
2. Conserva `wireguard/wg0.conf/wg0.conf` como archivo de entrega para ese dispositivo.
3. Copia `.env.example` a `.env` y revisa credenciales si hace falta.
4. Cada nodo usa su propio almacenamiento local en `/data` y `/data2`.

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
- Si más adelante agregas backend o frontend en estas máquinas, conéctalos a la misma red WireGuard local y usa el RabbitMQ de PC1.
- La tolerancia a fallos se logra a nivel de aplicación: backend y workers usan fallback entre endpoints de MinIO, pero cada nodo debe arrancar aunque otros estén caídos.