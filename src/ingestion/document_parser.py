from __future__ import annotations

from typing import Any

from src.ingestion.edgar_client import EdgarClient, get_default_edgar_client
from src.schemas.entities import (
    Filing,
    FilingMetadata,
    FilingSection,
    FilingSectionMetadata,
)


class FilingParser:
    """
    Service for converting EDGAR 10-K filing objects into domain objects.
    """

    def __init__(self, edgar_client: EdgarClient | None = None) -> None:
        self.edgar_client = edgar_client or get_default_edgar_client()

    def parse_filing(self, filing: Any) -> Filing:
        """
        Convert one SEC 10-K filing into a structured Filing object.

        The Filing object is the canonical parsed representation. Downstream
        chunking, JSON persistence, embedding, and indexing should build from it.
        """
        raw_sections = self.edgar_client.extract_sections(filing)
        filing_metadata = self._build_filing_metadata(filing, raw_sections)
        sections = self._build_sections(raw_sections, filing_metadata)

        return Filing(
            filing_id=filing_metadata.accession or "unknown-accession",
            metadata=filing_metadata,
            sections=sections,
        )

    def parse_filing_to_sections(self, filing: Any) -> list[FilingSection]:
        """
        Convert one 10-K filing into normalized section documents.

        Kept as a convenience method for workflows that only need sections.
        """
        return self.parse_filing(filing).sections

    def parse_ticker_filings(self, ticker: str, limit: int = 1) -> list[Filing]:
        """
        Fetch latest 10-K filings for a ticker and parse them into Filing objects.
        """
        filings = self.edgar_client.get_tenk_filings(ticker=ticker, limit=limit)
        parsed_filings = [self.parse_filing(filing) for filing in filings]

        print(f"Parsed {len(parsed_filings)} filings for {ticker}")

        return parsed_filings

    def parse_ticker_sections_by_year(
        self,
        ticker: str,
        limit: int = 1,
    ) -> dict[str, list[FilingSection]]:
        """
        Fetch latest 10-K filings and group parsed sections by fiscal year.

        This preserves the old parser shape while the project moves to Filing
        objects as the primary ingestion representation.
        """
        parsed_filings = self.parse_ticker_filings(ticker=ticker, limit=limit)
        return {
            str(filing.metadata.fiscal_year): filing.sections
            for filing in parsed_filings
        }

    def _build_filing_metadata(
        self,
        filing: Any,
        raw_sections: list[dict],
    ) -> FilingMetadata:
        first_section = raw_sections[0] if raw_sections else {}
        filing_date = first_section.get("filing_date") or str(getattr(filing, "filing_date", ""))
        accession = first_section.get("accession") or getattr(filing, "accession_number", None)

        return FilingMetadata(
            ticker=first_section.get("ticker"),
            company_name=self._get_company_name(filing),
            filing_type=first_section.get("form", "10-K"),
            filing_date=filing_date,
            fiscal_year=self._get_fiscal_year(filing, filing_date),
            accession=accession,
        )

    def _build_sections(
        self,
        raw_sections: list[dict],
        filing_metadata: FilingMetadata,
    ) -> list[FilingSection]:
        sections: list[FilingSection] = []

        for section in raw_sections:
            section_item = section.get("item")
            section_id = f"{filing_metadata.accession}:{section_item}"

            sections.append(
                FilingSection(
                    section_id=section_id,
                    text=section["text"],
                    metadata=FilingSectionMetadata(
                        ticker=filing_metadata.ticker,
                        filing_type=filing_metadata.filing_type,
                        filing_date=filing_metadata.filing_date,
                        fiscal_year=filing_metadata.fiscal_year,
                        accession=filing_metadata.accession,
                        section_item=section_item,
                        section_key=section.get("section_key"),
                        section_name=section.get("section_name"),
                    ),
                )
            )

        return sections

    def _get_company_name(self, filing: Any) -> str | None:
        try:
            entity = filing.get_entity()
        except Exception:
            return None

        return (
            getattr(entity, "name", None)
            or getattr(entity, "company_name", None)
            or getattr(entity, "display_name", None)
        )

    def _get_fiscal_year(self, filing: Any, filing_date: Any) -> int | None:
        date_value = getattr(filing, "filing_date", None)
        year = getattr(date_value, "year", None)
        if year is not None:
            return int(year)

        filing_date_text = str(filing_date)
        if len(filing_date_text) >= 4 and filing_date_text[:4].isdigit():
            return int(filing_date_text[:4])

        return None


_default_parser: FilingParser | None = None


def get_default_filing_parser() -> FilingParser:
    global _default_parser
    if _default_parser is None:
        _default_parser = FilingParser()
    return _default_parser


def parse_filing(filing: Any) -> Filing:
    """Compatibility wrapper for parsing one filing."""
    return get_default_filing_parser().parse_filing(filing)


def parse_filing_to_sections(filing: Any) -> list[FilingSection]:
    """Compatibility wrapper for parsing one filing into sections."""
    return get_default_filing_parser().parse_filing_to_sections(filing)


def parse_ticker_filings(ticker: str, limit: int = 1) -> list[Filing]:
    """Compatibility wrapper for fetching and parsing ticker filings."""
    return get_default_filing_parser().parse_ticker_filings(ticker=ticker, limit=limit)


def parse_ticker_sections_by_year(
    ticker: str,
    limit: int = 1,
) -> dict[str, list[FilingSection]]:
    """Compatibility wrapper for grouping parsed sections by fiscal year."""
    return get_default_filing_parser().parse_ticker_sections_by_year(
        ticker=ticker,
        limit=limit,
    )
