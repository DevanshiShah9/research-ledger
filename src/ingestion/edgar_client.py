from __future__ import annotations

from typing import Any

import edgar

# Sections to extract from each 10-K filing
# Item 1  → Business (company overview, products, segments, competition)
# Item 1A → Risk Factors (regulatory, operational, market, competitive risks)
# Item 7  → MD&A - Management's Discussion & Analysis (revenue drivers, 
#            margin trends, liquidity, forward-looking management narrative)
# Excludes Item 8 (Financial Statements & Notes) to control token usage
DEFAULT_IDENTITY = "Financial RAG Project devanshishah9699@gmail.com"
TARGET_ITEMS = {"1", "1A", "7"}
MIN_CHARS = 200


class EdgarClient:
    """
    Thin wrapper around edgartools for fetching and extracting 10-K content.
    """

    def __init__(
        self,
        identity: str = DEFAULT_IDENTITY,
        target_items: set[str] | None = None,
        min_chars: int = MIN_CHARS,
    ) -> None:
        self.identity = identity
        self.target_items = target_items or TARGET_ITEMS
        self.min_chars = min_chars
        edgar.set_identity(identity)

    def get_tenk_filings(self, ticker: str, limit: int = 5) -> list:
        """Get the most recent 10-K filings for a company."""
        company = edgar.Company(ticker)
        filings = company.get_filings(form="10-K").latest(limit)
        if not isinstance(filings, list):
            filings = [filings]
        return filings

    def extract_sections(self, filing: Any) -> list[dict]:
        """
        Extract narrative text sections from a 10-K filing.

        Items 1 (Business), 1A (Risk Factors), and 7 (MD&A) are included.
        Output goes to parser → chunker → embedder → OpenSearch.
        """
        tenk = filing.obj()
        if tenk is None:
            raise ValueError(f"Could not parse filing: {filing.accession_number}")

        ticker = self._get_primary_ticker(filing)
        sections = []

        for section in tenk.sections.values():
            if section.item not in self.target_items:
                continue

            text = section.text()
            if not text or len(text.strip()) < self.min_chars:
                continue

            sections.append(
                {
                    "section_key": f"Part {section.part} - Item {section.item}",
                    "section_name": text.split("\n")[0].strip(),
                    "item": section.item,
                    "text": text,
                    "ticker": ticker,
                    "form": "10-K",
                    "filing_date": str(filing.filing_date),
                    "accession": filing.accession_number,
                }
            )

        return sections

    def extract_financials(self, ticker: str) -> dict:
        """
        Extract structured financial data using the Company Facts API.

        This output is not chunked; it can later be stored separately for
        dashboard metrics or structured financial lookups.
        """
        company = edgar.Company(ticker)
        return {
            "ticker": ticker,
            "income_statement": company.income_statement(periods=4, annual=True).to_llm_context(),
            "balance_sheet": company.balance_sheet(periods=4, annual=True).to_llm_context(),
            "cash_flow": company.cashflow_statement(periods=4, annual=True).to_llm_context(),
        }

    def _get_primary_ticker(self, filing: Any) -> str | None:
        entity = filing.get_entity()
        tickers = getattr(entity, "tickers", None) or []
        return tickers[0] if tickers else None


_default_client: EdgarClient | None = None


def get_default_edgar_client() -> EdgarClient:
    global _default_client
    if _default_client is None:
        _default_client = EdgarClient()
    return _default_client


def get_tenk_filings(ticker: str, limit: int = 5) -> list:
    """Compatibility wrapper for fetching recent 10-K filings."""
    return get_default_edgar_client().get_tenk_filings(ticker=ticker, limit=limit)


def extract_sections(filing: Any) -> list[dict]:
    """Compatibility wrapper for extracting target 10-K sections."""
    return get_default_edgar_client().extract_sections(filing)


def extract_financials(ticker: str) -> dict:
    """Compatibility wrapper for extracting structured financials."""
    return get_default_edgar_client().extract_financials(ticker)
