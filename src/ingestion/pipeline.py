from __future__ import annotations

from pathlib import Path
from typing import Any

from src.ingestion.chunk_writer import DEFAULT_OUTPUT_DIR, write_filing_chunks
from src.ingestion.chunker import FilingChunker
from src.ingestion.document_parser import FilingParser
from src.ingestion.edgar_client import EdgarClient, get_default_edgar_client
from src.ingestion.entities import Filing, FilingSectionChunk


class FilingIngestionPipeline:
    """
    Task-sized ingestion pipeline for SEC 10-K filings.

    Each public method maps cleanly to a future Airflow task. The
    run_for_ticker method is a convenience runner for local development.
    """

    def __init__(
        self,
        edgar_client: EdgarClient | None = None,
        parser: FilingParser | None = None,
        chunker: FilingChunker | None = None,
        output_dir: Path | str = DEFAULT_OUTPUT_DIR,
    ) -> None:
        self.edgar_client = edgar_client or get_default_edgar_client()
        self.parser = parser or FilingParser(edgar_client=self.edgar_client)
        self.chunker = chunker or FilingChunker()
        self.output_dir = Path(output_dir)

    def fetch_filings(self, ticker: str, limit: int = 1) -> list[Any]:
        """
        Airflow task boundary: fetch recent 10-K filings from EDGAR.
        """
        return self.edgar_client.get_tenk_filings(ticker=ticker, limit=limit)

    def parse_filings(self, filings: list[Any]) -> list[Filing]:
        """
        Airflow task boundary: convert EDGAR filing objects to Filing objects.
        """
        return [self.parser.parse_filing(filing) for filing in filings]

    def chunk_filing(self, filing: Filing) -> list[FilingSectionChunk]:
        """
        Airflow task boundary: chunk one parsed Filing object.
        """
        return self.chunker.chunk_sections(filing.sections)

    def chunk_filings(
        self,
        filings: list[Filing],
    ) -> dict[str, list[FilingSectionChunk]]:
        """
        Airflow task boundary: chunk each parsed Filing object.
        """
        return {
            filing.filing_id: self.chunk_filing(filing)
            for filing in filings
        }

    def write_chunks(
        self,
        filing: Filing,
        chunks: list[FilingSectionChunk],
    ) -> Path:
        """
        Airflow task boundary: write one filing's chunks to JSON.
        """
        return write_filing_chunks(
            filing=filing,
            chunks=chunks,
            output_dir=self.output_dir,
        )

    def write_all_chunks(
        self,
        filings: list[Filing],
        chunks_by_filing_id: dict[str, list[FilingSectionChunk]],
    ) -> list[Path]:
        """
        Airflow task boundary: write all filing chunk artifacts to JSON.
        """
        output_paths: list[Path] = []

        for filing in filings:
            chunks = chunks_by_filing_id.get(filing.filing_id, [])
            output_paths.append(self.write_chunks(filing, chunks))

        return output_paths

    def run_for_ticker(self, ticker: str, limit: int = 1) -> list[Path]:
        """
        Local development runner for the full ingestion flow.
        """
        raw_filings = self.fetch_filings(ticker=ticker, limit=limit)
        filings = self.parse_filings(raw_filings)
        chunks_by_filing_id = self.chunk_filings(filings)
        return self.write_all_chunks(filings, chunks_by_filing_id)
