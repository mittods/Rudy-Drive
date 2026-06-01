from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, TypeVar
import os

from minio import Minio
import io
from minio.error import S3Error
import urllib3

from .config import MinIOConfig


T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class MinIOClient:
    config: MinIOConfig

    def candidate_endpoints(self) -> tuple[str, ...]:
        endpoints = tuple(
            endpoint.strip()
            for endpoint in self.config.endpoints
            if endpoint.strip()
        )
        return endpoints or (self.config.endpoint,)

    def connect(self, endpoint: str | None = None) -> Minio:
        target_endpoint = endpoint or self.config.endpoint
        connect_timeout = float(os.getenv("MINIO_CONNECT_TIMEOUT_SECONDS", "3"))
        read_timeout = float(os.getenv("MINIO_READ_TIMEOUT_SECONDS", "20"))
        http_client = urllib3.PoolManager(
            timeout=urllib3.Timeout(connect=connect_timeout, read=read_timeout),
            retries=False,
        )
        return Minio(
            endpoint=target_endpoint,
            access_key=self.config.access_key,
            secret_key=self.config.secret_key,
            secure=self.config.secure,
            http_client=http_client,
        )

    def with_client(self, operation: Callable[[Minio], T]) -> T:
        last_error: Exception | None = None
        for endpoint in self.candidate_endpoints():
            client = self.connect(endpoint)
            try:
                return operation(client)
            except Exception as exc:
                last_error = exc
        if last_error is not None:
            raise last_error
        raise RuntimeError("No MinIO endpoints configured")

    def ensure_bucket_all(self) -> None:
        last_error: Exception | None = None
        for endpoint in self.candidate_endpoints():
            client = self.connect(endpoint)
            try:
                if not client.bucket_exists(self.config.bucket):
                    client.make_bucket(self.config.bucket)
            except Exception as exc:
                last_error = exc
        if last_error is not None:
            # don't fail hard if some endpoints are down; caller can decide
            pass

    def put_object_all(self, object_name: str, data: bytes, content_type: str = "application/octet-stream") -> list[str]:
        """Attempt to put the same object to all candidate endpoints.

        Returns list of endpoints that succeeded. Raises last exception if none succeeded.
        """
        successes: list[str] = []
        last_error: Exception | None = None
        for endpoint in self.candidate_endpoints():
            client = self.connect(endpoint)
            try:
                client.put_object(
                    bucket_name=self.config.bucket,
                    object_name=object_name,
                    data=io.BytesIO(data),
                    length=len(data),
                    content_type=content_type,
                )
                successes.append(endpoint)
            except Exception as exc:
                last_error = exc
                continue

        if not successes and last_error is not None:
            raise last_error
        return successes

    def get_object_bytes(self, endpoint: str, object_name: str) -> bytes:
        client = self.connect(endpoint)
        try:
            resp = client.get_object(self.config.bucket, object_name)
            try:
                data = resp.read()
            finally:
                try:
                    resp.close()
                    resp.release_conn()
                except Exception:
                    pass
            return data
        except S3Error as exc:
            raise

    def copy_object_between(self, src_endpoint: str, dst_endpoint: str, object_name: str) -> bool:
        try:
            data = self.get_object_bytes(src_endpoint, object_name)
        except Exception:
            return False
        try:
            dst = self.connect(dst_endpoint)
            dst.put_object(
                bucket_name=self.config.bucket,
                object_name=object_name,
                data=io.BytesIO(data),
                length=len(data),
                content_type="application/octet-stream",
            )
            return True
        except Exception:
            return False

    def delete_prefix_all(self, prefix: str) -> None:
        last_error: Exception | None = None
        for endpoint in self.candidate_endpoints():
            client = self.connect(endpoint)
            try:
                for object_info in client.list_objects(self.config.bucket, prefix=prefix, recursive=True):
                    client.remove_object(self.config.bucket, object_info.object_name)
            except Exception as exc:
                last_error = exc
        if last_error is not None:
            # don't fail hard if some endpoints are down
            pass

    def replicate_operation(self, operation: Callable[[Minio], T]) -> list[tuple[str, bool, Exception | None]]:
        """Run the operation against all candidate endpoints.

        Returns a list of tuples (endpoint, success, exception).
        Raises the last exception if all attempts fail.
        """
        results: list[tuple[str, bool, Exception | None]] = []
        last_error: Exception | None = None
        for endpoint in self.candidate_endpoints():
            client = self.connect(endpoint)
            try:
                operation(client)
                results.append((endpoint, True, None))
            except Exception as exc:
                results.append((endpoint, False, exc))
                last_error = exc
        if not any(ok for _, ok, _ in results):
            if last_error is not None:
                raise last_error
            raise RuntimeError("No MinIO endpoints configured")
        return results

    def copy_object(self, source_endpoint: str, target_endpoint: str, bucket: str, object_name: str) -> None:
        """Copy an object from source_endpoint to target_endpoint by streaming through memory.

        Note: used for small chunk objects; not optimized for huge objects.
        """
        src = self.connect(source_endpoint)
        dst = self.connect(target_endpoint)

        # Ensure bucket exists on destination
        try:
            if not dst.bucket_exists(bucket):
                dst.make_bucket(bucket)
        except Exception:
            # ignore - will error when attempting put
            pass

        # Read object into memory and write to destination
        try:
            response = src.get_object(bucket, object_name)
            data = b""
            for chunk in response.stream(32 * 1024):
                data += chunk
            response.close()
            response.release_conn()
            dst.put_object(bucket_name=bucket, object_name=object_name, data=io.BytesIO(data), length=len(data), content_type="application/octet-stream")
        except Exception:
            raise

    def list_objects_on(self, endpoint: str, prefix: str | None = None) -> list[str]:
        client = self.connect(endpoint)
        try:
            return [obj.object_name for obj in client.list_objects(self.config.bucket, prefix=prefix, recursive=True)]
        except Exception:
            return []

    def repair_endpoint(self, target_endpoint: str) -> dict[str, int]:
        """Ensure the target endpoint has all objects present across the other endpoints.

        Returns a summary dict: {"copied": n, "skipped": m, "errors": k}
        """
        bucket = self.config.bucket
        candidates = [e for e in self.candidate_endpoints() if e != target_endpoint]
        # Collect union of objects from other endpoints
        union: set[str] = set()
        for ep in candidates:
            try:
                objs = self.list_objects_on(ep)
                union.update(objs)
            except Exception:
                continue

        # List objects on target
        try:
            target_objs = set(self.list_objects_on(target_endpoint))
        except Exception:
            target_objs = set()

        to_copy = sorted(list(union - target_objs))
        copied = 0
        skipped = 0
        errors = 0
        import io

        for obj in to_copy:
            # find a source that has the object
            source_found = False
            for src in candidates:
                src_objs = self.list_objects_on(src)
                if obj in src_objs:
                    try:
                        self.copy_object(src, target_endpoint, bucket, obj)
                        copied += 1
                        source_found = True
                        break
                    except Exception:
                        errors += 1
                        source_found = False
            if not source_found:
                skipped += 1

        return {"copied": copied, "skipped": skipped, "errors": errors}

    def ensure_bucket(self) -> None:
        def operation(client: Minio) -> None:
            if not client.bucket_exists(self.config.bucket):
                client.make_bucket(self.config.bucket)

        self.with_client(operation)

    def delete_prefix(self, prefix: str) -> None:
        def operation(client: Minio) -> None:
            for object_info in client.list_objects(self.config.bucket, prefix=prefix, recursive=True):
                client.remove_object(self.config.bucket, object_info.object_name)

        self.with_client(operation)
