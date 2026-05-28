# Research Ledger

Research Ledger is a financial research assistant project. The first phase,
**FinDocRAG**, focuses on grounded question-answering over SEC 10-K filings.
The future second phase, **FinSight**, will expand the system with live market
context, news, and analytics dashboards.

## Overview

### Problem Statement

Financial analysts, investors, and researchers spend significant time manually reading through SEC 10-K annual reports to extract insights about company performance, risk exposure, and strategic direction. These documents are dense, lengthy (10-Ks can exceed 200 pages), and require domain knowledge to navigate effectively.

There is no low-friction way to ask natural language questions across multiple filings from multiple companies and get grounded, source-cited answers.

### FinDocRAG

FinDocRAG is a multi-node LangGraph-powered RAG system that allows users to:

- Ask natural language questions about any US public company's 10-K filings
- Get answers grounded in actual filing text, with source citations
- Query across multiple filings (e.g., compare risk factors across 3 years of 10-Ks)
- Interact via a chat interface backed by an intelligent retrieval pipeline

The system uses SEC EDGAR as its data source — a free, official, programmatic API maintained by the US Securities and Exchange Commission containing filings from every publicly listed US company.

### Target Users

- Buy-side / sell-side analysts doing fundamental research
- Retail investors wanting plain-language summaries of filings
- Risk teams reviewing disclosed risk factors across peers

### Why This Is Technically Interesting

- LangGraph orchestrates a stateful, conditional pipeline — not a simple chain
- The graph makes decisions: route queries, retry on poor retrieval, detect hallucinations
- Hybrid search (BM25 + vector) over long-form financial documents
- Designed for extensibility into FinSight, the future market-context phase

---

## FinDocRAG — Scope & Constraints

### In Scope

- Ingest 10-K filings from SEC EDGAR for any US public company
- Parse filings into structured Filing and FilingSection objects
- Chunk filing sections into retrieval-ready records
- Store processed chunks as JSON first, with PostgreSQL planned as a later durable store
- Embed and index filing chunks for hybrid search
- Airflow pipeline for scheduled/retryable ingestion
- LangGraph pipeline: query classification → decomposition → retrieval → grading → generation → hallucination check
- Chat interface (Gradio) for user interaction
- Source citations in every answer (which filing, which section)
- Docker Compose for local deployment

### Out of Scope

- Live stock price data
- News sentiment analysis
- Investment recommendations or buy/sell signals
- User authentication
- Cloud deployment
- 10-Q quarterly filings
- Multi-company comparative analysis in a single query (FinSight)

### Constraints

- Fully free stack — no paid APIs required
- Runs locally via Docker Compose
- LLM: Gemini Flash (free tier) or Ollama (fully local)
- Embeddings: Jina AI free tier (1M tokens/month)

---

## Tech Stack

| Component | Tool | Cost |
|---|---|---|
| LLM | Gemini Flash / Ollama | Free |
| Embeddings | Jina AI | Free tier |
| Search Index | OpenSearch | Free |
| Search | Hybrid search: BM25 + vector similarity + RRF | Free |
| Graph Orchestration | LangGraph | Open source |
| Filing Ingestion | edgartools | Free |
| Backend API | FastAPI | Open source |
| Chat UI | Gradio | Open source |
| Infrastructure | Docker Compose | Free |
| Observability | Langfuse (self-hosted) | Free |

---

## System Architecture — FinDocRAG

### LangGraph Node Descriptions

#### NODE 1 — Query Classifier

- **Purpose:** Determine if the query is answerable from SEC filings
- **Logic:** LLM classifies query as "filing-relevant" or "out-of-scope"
- **Out-of-scope examples:** "Should I buy this stock?", "What is the current price?"
- **Output:** Route to decomposer OR return clean rejection message

#### NODE 2 — Query Decomposer

- **Purpose:** Break complex questions into focused sub-queries
- **Example input:** "How has Apple's revenue and debt changed over 3 years?"
- **Example output:** `["Apple revenue 2022 10-K", "Apple revenue 2023 10-K", "Apple revenue 2024 10-K", "Apple long-term debt 2022-2024"]`
- **Why:** Single complex queries perform poorly at retrieval. Sub-queries get better chunks.

#### NODE 3 — Retriever

- **Purpose:** Fetch relevant document chunks for each sub-query
- **Method:** Hybrid search — BM25 keyword match + OpenSearch vector similarity
- **Fusion:** Reciprocal Rank Fusion (RRF) to merge both result sets
- **Metadata filters:** company ticker, filing type (10-K), fiscal year, section item

#### NODE 4 — Document Grader

- **Purpose:** Filter out irrelevant chunks before passing to the LLM
- **Logic:** LLM scores each chunk as relevant/irrelevant to the sub-query
- **Why:** Prevents the generator from being confused by loosely related text

#### NODE 5 — Query Rewriter (conditional)

- **Purpose:** Reformulate the query if grading finds no relevant chunks
- **Triggers:** When Document Grader returns zero relevant chunks
- **Max retries:** 2 (prevents infinite loops)
- **Logic:** LLM rephrases query with different terminology

#### NODE 6 — Answer Generator

- **Purpose:** Synthesize a grounded answer from relevant chunks
- **Requirements:** Every claim must be traceable to a specific chunk/filing
- **Output format:** Answer text + list of source citations (company, filing, section, page)

#### NODE 7 — Hallucination Checker

- **Purpose:** Verify the generated answer doesn't contain claims not in the source chunks
- **Logic:** LLM compares answer against retrieved chunks, flags unsupported claims
- **On failure:** Trigger regeneration with stricter grounding instructions

### LangGraph State Object

The shared state passed between all nodes:

```python
{
    "query": str,                    # original user query
    "sub_queries": List[str],        # from decomposer
    "retrieved_chunks": List[dict],  # from retriever
    "graded_chunks": List[dict],     # from grader (filtered)
    "retry_count": int,              # tracks rewriter retries
    "answer": str,                   # from generator
    "citations": List[dict],         # source references
    "hallucination_flag": bool,      # from checker
    "rejection_reason": str          # if classifier rejects
}
```

### Ingestion Pipeline

**Step 1 — Company + Filing Selection**
- User specifies: ticker symbol (e.g., "AAPL"), filing type fixed to 10-K, date range/limit
- System calls SEC EDGAR API to get filing index

**Step 2 — Document Fetch**
- Download filing HTML from EDGAR via edgartools

**Step 3 — Structured Filing Model**
- Normalize each 10-K into a Filing object
- Preserve FilingSection objects for Item 1 (Business), Item 1A (Risk Factors), and Item 7 (MD&A)
- Attach metadata needed for citations: ticker, filing type, filing date, accession, section item, section name

**Step 4 — Chunking Strategy**
- Section-aware chunking: never mix text from different 10-K items in the same chunk
- Word-window chunking: target 600 words with 100-word overlap
- Each chunk gets stable metadata and IDs for indexing/citations

**Step 5 — Processed Storage**
- Store chunk records as JSON while the pipeline is being developed
- JSON is the first durable checkpoint between parsing and indexing
- PostgreSQL can replace or supplement JSON later once the schema is stable

**Step 6 — Embedding + Indexing**
- Embed chunks with Jina AI
- Store chunks and embeddings in OpenSearch
- Use OpenSearch BM25 for keyword search
- Use OpenSearch vector search for semantic search
- Merge BM25 and vector rankings with Reciprocal Rank Fusion (RRF)

**Step 7 — Airflow Orchestration**
- Airflow DAG coordinates the ingestion workflow
- Suggested tasks: fetch 10-K filings → parse sections → create chunks → validate chunks → write JSON → embed chunks → index OpenSearch
- Airflow should orchestrate stable code paths rather than contain parsing/search logic directly


## Future Direction: FinSight

FinSight is the planned second phase of Research Ledger. It upgrades the system
from a filing-only analysis tool into a broader research assistant with live
market context.

### What FinSight Adds

- Answer questions requiring current stock price (e.g., "Is the stock trading below book value?")
- Pull recent news sentiment to contextualize filing data
- Cross-company comparison in a single query
- A lightweight dashboard showing financial metric trends over time

### New Data Sources

| Source | Data | API Method |
|---|---|---|
| Yahoo Finance | Live + historical stock price | yfinance (free Python lib) |
| Tavily Search | Recent news about company | Tavily API (free tier) |
| SEC EDGAR | Filings (already in FinDocRAG) | Same as FinDocRAG |

### Architecture Changes

The biggest change is upgrading NODE 1 (Query Classifier) into a full Router
that determines which tools/agents to invoke.

Query types in FinSight:
- `"filing-only"` → existing FinDocRAG pipeline unchanged
- `"price-required"` → call yfinance tool, optionally combine with filings
- `"news-required"` → call Tavily search tool
- `"multi-source"` → combine filings + price + news before generating answer

New nodes added:
- **[Price Fetcher]** — calls yfinance for current/historical price data
- **[News Fetcher]** — calls Tavily for recent news sentiment
- **[Data Synthesizer]** — merges filing chunks + price data + news before generation

> **Important:** The system will NOT make investment recommendations. It will present data and let the user draw conclusions. This is explicitly stated in the UI and in the system prompt given to the LLM.

### Dashboard

A lightweight Gradio dashboard tab showing:
- Revenue, net income, EPS trends from annual 10-K data
- Debt-to-equity ratio trend
- Key risk factor changes between annual filings (diff view)
- Recent news sentiment score

Data for the dashboard is pre-computed at ingestion time and stored in PostgreSQL, not generated on-the-fly by the LLM.

---

## Open Questions

- **LLM choice:** Default to Gemini Flash (better quality, requires internet) with Ollama as fallback config option (fully local, lower quality).
- **Demo companies:** Pre-index 5 well-known companies across sectors — JPMorgan, Goldman Sachs, Apple, Microsoft, ExxonMobil (covering banking, tech, and energy).
- **Table chunking:** Financial tables (income statements, balance sheets) are poorly handled by naive text chunking. May need a separate table extraction pass. To be decided during implementation.

---

## References

- [SEC EDGAR API](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
- [LangGraph Docs](https://langchain-ai.github.io/langgraph/)
- [Reference project (arXiv RAG)](https://github.com/jamwithai/production-agentic-rag-course)
- [Comparable project (Financial RAG)](https://github.com/DeepakSilaych/Financial_Agentic_RAG)
- [LangGraph multi-agent patterns](https://langchain-ai.github.io/langgraph/concepts/multi_agent/)
