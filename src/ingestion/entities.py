from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class FilingSectionMetadata:
    ticker: str | None
    filing_type: str
    filing_date: Any
    accession: str | None
    section_item: str | None
    section_key: str | None
    section_name: str | None


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
