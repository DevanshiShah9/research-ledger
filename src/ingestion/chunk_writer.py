from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from src.ingestion.entities import Filing, FilingSectionChunk

DEFAULT_OUTPUT_DIR = Path("data/processed")


def write_filing_chunks(
    filing: Filing,
    chunks: list[FilingSectionChunk],
    output_dir: Path | str = DEFAULT_OUTPUT_DIR,
) -> Path:
    """
    Write one filing's chunks to a JSON artifact.

    JSON is the temporary processed-data layer. Later, these same records can
    be inserted into PostgreSQL and indexed into OpenSearch.
    """
    output_path = _build_output_path(filing, Path(output_dir))
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "filing": asdict(filing.metadata),
        "chunk_count": len(chunks),
        "chunks": [chunk_to_record(chunk) for chunk in chunks],
    }

    output_path.write_text(
        json.dumps(payload, indent=2, default=str),
        encoding="utf-8",
    )

    return output_path


def chunk_to_record(chunk: FilingSectionChunk) -> dict:
    """
    Convert a chunk dataclass into the flat record shape expected by search.
    """
    metadata = asdict(chunk.metadata)
    return {
        "chunk_id": chunk.chunk_id,
        "section_id": chunk.section_id,
        "chunk_index": chunk.chunk_index,
        "word_start": chunk.word_start,
        "word_end": chunk.word_end,
        "word_count": chunk.word_end - chunk.word_start,
        "text": chunk.chunk,
        "metadata": metadata,
    }


def _build_output_path(filing: Filing, output_dir: Path) -> Path:
    ticker = filing.metadata.ticker or "unknown_ticker"
    accession = filing.metadata.accession or filing.filing_id
    return output_dir / ticker.upper() / f"{accession}.json"
