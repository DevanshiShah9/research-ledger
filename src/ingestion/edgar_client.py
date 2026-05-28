import edgar


edgar.set_identity("Financial RAG Project devanshishah9699@gmail.com")


# Sections to extract from each 10-K filing
# Item 1  → Business (company overview, products, segments, competition)
# Item 1A → Risk Factors (regulatory, operational, market, competitive risks)
# Item 7  → MD&A - Management's Discussion & Analysis (revenue drivers, 
#            margin trends, liquidity, forward-looking management narrative)
# Excludes Item 8 (Financial Statements & Notes) to control token usage
TARGET_ITEMS = {"1", "1A", "7"}
MIN_CHARS = 200


def get_tenk_filings(ticker: str, limit: int = 5) -> list:
    """Get the most recent 10-K filings for a company."""
    company = edgar.Company(ticker)
    filings = company.get_filings(form="10-K").latest(limit)
    if not isinstance(filings, list):
        filings = [filings]
    return filings


def extract_sections(filing) -> list[dict]:
    """
    Extract narrative text sections from a 10-K filing.
    Items 1 (Business), 1A (Risk Factors), 7 (MD&A) only.
    Output goes to chunker → embedder → ChromaDB.
    """
    tenk = filing.obj()
    if tenk is None:
        raise ValueError(f"Could not parse filing: {filing.accession_number}")
    entity = filing.get_entity()
    tickers = getattr(entity, "tickers", None) or []
    ticker = tickers[0] if tickers else None
    sections = []
    for section in tenk.sections.values():
        if section.item not in TARGET_ITEMS:
            continue
        text = section.text()
        if not text or len(text.strip()) < MIN_CHARS:
            continue
        first_line = text.split('\n')[0].strip()
        sections.append({
            "section_key":  f"Part {section.part} - Item {section.item}",
            "section_name": first_line,
            "item":         section.item,
            "text":         text,
            "ticker":       ticker,
            "form":         "10-K",
            "filing_date":  str(filing.filing_date),
            "accession":    filing.accession_number,
        })
    return sections

def extract_financials(ticker: str) -> dict:
    """
    Extract structured financial data using the Company Facts API.
    Returns LLM-ready context for income statement, balance sheet, cash flow.
    Output goes directly to SQLite — no chunking or embedding needed.
    """
    company = edgar.Company(ticker)
    return {
        "ticker":           ticker,
        "income_statement": company.income_statement(periods=4, annual=True).to_llm_context(),
        "balance_sheet":    company.balance_sheet(periods=4, annual=True).to_llm_context(),
        "cash_flow":        company.cashflow_statement(periods=4, annual=True).to_llm_context(),
    }