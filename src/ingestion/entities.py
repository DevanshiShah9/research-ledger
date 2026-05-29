from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class FilingMetadata:
    ticker: str | None
    company_name: str | None
    filing_type: str
    filing_date: Any
    fiscal_year: int | None
    accession: str | None


@dataclass(slots=True)
class FilingSectionMetadata:
    ticker: str | None
    filing_type: str
    filing_date: Any
    fiscal_year: int | None
    accession: str | None
    section_item: str | None
    section_key: str | None
    section_name: str | None


@dataclass(slots=True)
class Filing:
    filing_id: str
    metadata: FilingMetadata
    sections: list["FilingSection"]


@dataclass(slots=True)
class FilingSection:
    section_id: str
    text: str
    metadata: FilingSectionMetadata


@dataclass(slots=True)
class FilingSectionChunk:
    # chunk_id is the stable storage/search ID; chunk_index is its local
    # position within the section and keeps neighboring chunks ordered.
    chunk_id: str
    section_id: str
    chunk_index: int
    word_start: int
    word_end: int
    metadata: FilingSectionMetadata
    chunk: str


@dataclass(slots=True)
class ChunkRecord:
    """Flat processed chunk shape used for JSON, embeddings, and indexing."""

    chunk_id: str
    section_id: str
    chunk_index: int
    ticker: str | None
    filing_type: str
    filing_date: Any
    fiscal_year: int | None
    accession: str | None
    section_item: str | None
    section_key: str | None
    section_name: str | None
    word_start: int
    word_end: int
    word_count: int
    text: str

    def __post_init__(self) -> None:
        if not self.chunk_id:
            raise ValueError("ChunkRecord must have a non-empty chunk_id")
        if not self.text:
            raise ValueError(f"ChunkRecord {self.chunk_id} has empty text")
        if self.word_end < self.word_start:
            raise ValueError(f"ChunkRecord {self.chunk_id} has invalid word offsets")
        if self.word_count != self.word_end - self.word_start:
            raise ValueError(f"ChunkRecord {self.chunk_id} has invalid word_count")
