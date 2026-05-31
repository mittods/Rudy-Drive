from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ChunkMetadata:
    id: str
    file_id: str
    node: str
    chunk_index: int
    object_name: str