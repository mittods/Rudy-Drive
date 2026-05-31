from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .chunk_metadata import ChunkMetadata
from .minio_client import MinIOClient


@dataclass(frozen=True, slots=True)
class ChunkRecoveryWorker:
    minio_client: MinIOClient

    def read_chunk(self, chunk: ChunkMetadata) -> bytes:
        def operation(client) -> bytes:
            response = client.get_object(self.minio_client.config.bucket, chunk.object_name)
            try:
                return response.read()
            finally:
                response.close()
                response.release_conn()

        return self.minio_client.with_client(operation)

    def download_chunk(self, chunk: ChunkMetadata) -> bytes:
        return self.read_chunk(chunk)

    def recover_bytes(self, chunks: Iterable[ChunkMetadata]) -> bytes:
        ordered_chunks = sorted(chunks, key=lambda chunk: chunk.chunk_index)
        return b"".join(self.download_chunk(chunk) for chunk in ordered_chunks)