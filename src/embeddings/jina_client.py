from __future__ import annotations

import os
from dataclasses import replace
from typing import Any

import requests
from src.schemas.entities import ChunkRecord

JINA_EMBEDDINGS_URL = "https://api.jina.ai/v1/embeddings"
DEFAULT_JINA_MODEL = "jina-embeddings-v5-text-small"
DEFAULT_EMBEDDING_TASK = "retrieval.passage"


class JinaEmbeddingClient:
    """
    Small client for Jina AI text embeddings.

    Set JINA_API_KEY in your environment before making live API calls. The
    default task is retrieval.passage because filing chunks are documents that
    will later be retrieved by user queries.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        endpoint: str = JINA_EMBEDDINGS_URL,
        timeout: int = 60,
    ) -> None:
        self.api_key = api_key or os.getenv("JINA_API_KEY")
        self.model = model or os.getenv("JINA_EMBEDDING_MODEL", DEFAULT_JINA_MODEL)
        self.endpoint = endpoint
        self.timeout = timeout

        if not self.api_key:
            raise ValueError("JINA_API_KEY must be set to generate embeddings")

    def embed_texts(
        self,
        texts: list[str],
        task: str = DEFAULT_EMBEDDING_TASK,
    ) -> list[list[float]]:
        """
        Embed a batch of text strings and return vectors in input order.
        """
        if not texts:
            return []

        payload: dict[str, Any] = {
            "model": self.model,
            "input": texts,
            "task": task,
            "embedding_type": "float",
        }
        response = requests.post(
            self.endpoint,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()

        data = response.json()["data"]
        data = sorted(data, key=lambda item: item["index"])
        return [item["embedding"] for item in data]

    def embed_query(self, query: str) -> list[float]:
        """
        Embed a user query using Jina's retrieval.query task.
        """
        return self.embed_texts([query], task="retrieval.query")[0]

    def embed_chunk_records(
        self,
        records: list[ChunkRecord],
    ) -> list[ChunkRecord]:
        """
        Return chunk records with embedding fields filled in.
        """
        texts = [record.text for record in records]
        embeddings = self.embed_texts(texts, task="retrieval.passage")

        return [
            replace(
                record,
                embedding=embedding,
                embedding_model=self.model,
            )
            for record, embedding in zip(records, embeddings, strict=True)
        ]
