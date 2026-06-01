from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from .config import ChunkingConfig
from .minio_client import MinIOClient


@dataclass(frozen=True, slots=True)
class ChunkRecord:
    upload_id: str
    index: int
    object_name: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class ChunkStorage:
    minio_client: MinIOClient
    chunking: ChunkingConfig = ChunkingConfig()

    def object_name(self, upload_id: str, index: int) -> str:
        return f"{upload_id}/chunk_{index}"

    def _put_chunk(self, client, upload_id: str, index: int, chunk: bytes) -> ChunkRecord:
        object_name = self.object_name(upload_id, index)
        # replicate the chunk to all available endpoints
        self.minio_client.put_object_all(object_name, chunk, content_type="application/octet-stream")
        return ChunkRecord(
            upload_id=upload_id,
            index=index,
            object_name=object_name,
            size_bytes=len(chunk),
        )

    def store_bytes(self, upload_id: str, data: bytes) -> list[ChunkRecord]:
        # Ensure bucket exists on all endpoints we will write to
        self.minio_client.ensure_bucket_all()
        records: list[ChunkRecord] = []
        for index, start in enumerate(range(0, len(data), self.chunking.size_bytes)):
            chunk = data[start : start + self.chunking.size_bytes]
            records.append(self._put_chunk(None, upload_id, index, chunk))
        return records

    def store_stream(self, upload_id: str, stream: BinaryIO) -> list[ChunkRecord]:
        # Ensure bucket exists across all endpoints before replicated writes.
        self.minio_client.ensure_bucket_all()

        if not stream.seekable():
            return self.store_bytes(upload_id, stream.read())

        start_position = stream.tell()

        stream.seek(start_position)
        records: list[ChunkRecord] = []
        index = 0
        while True:
            chunk = stream.read(self.chunking.size_bytes)
            if not chunk:
                break
            records.append(self._put_chunk(None, upload_id, index, chunk))
            index += 1
        return records

    def store_file(self, upload_id: str, file_path: str | Path) -> list[ChunkRecord]:
        path = Path(file_path)
        with path.open("rb") as stream:
            return self.store_stream(upload_id, stream)