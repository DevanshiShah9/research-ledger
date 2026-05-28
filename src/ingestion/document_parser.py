from __future__ import annotations

from typing import Any

from src.ingestion.edgar_client import extract_sections, get_tenk_filings
from src.ingestion.entities import FilingSection, FilingSectionMetadata


def parse_filing_to_sections(filing: Any) -> list[FilingSection]:
    """
    Convert one 10-K filing into normalized section documents.

    The output shape is intentionally stable so downstream chunking/indexing
    can rely on consistent keys.
    """
    raw_sections = extract_sections(filing)
    sections: list[FilingSection] = []

    for section in raw_sections:
        sections.append(
            FilingSection(
                section_id=f"{section['accession']}:{section['item']}",
                text=section["text"],
                metadata=FilingSectionMetadata(
                    ticker=section.get("ticker"),
                    filing_type=section.get("form", "10-K"),
                    filing_date=section.get("filing_date"),
                    accession=section.get("accession"),
                    section_item=section.get("item"),
                    section_key=section.get("section_key"),
                    section_name=section.get("section_name"),
                ),
            )
        )

    return sections


def parse_ticker_filings(ticker: str, limit: int = 1) -> dict[str, list[FilingSection]]:
    """
    Fetch latest 10-K filings for a ticker and group parsed sections by filing year.
    """
    filings = get_tenk_filings(ticker=ticker, limit=limit)

    parsed_filings: dict[str, list[FilingSection]] = {}

    for filing in filings:
        filing_year = str(filing.filing_date.year)

        parsed_filings[filing_year] = parse_filing_to_sections(filing)

    print(f"Parsed {len(parsed_filings)} filings for {ticker}")

    return parsed_filings
