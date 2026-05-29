from __future__ import annotations

import re

from src.schemas.entities import FilingSection, FilingSectionChunk

CHUNK_SIZE_WORDS = 600
CHUNK_OVERLAP_WORDS = 100


class FilingChunker:
    """
    Service for splitting parsed SEC filing sections into word-based chunks.

    The chunker assumes section boundaries have already been detected by the
    parser, so it never mixes text from different 10-K items in one chunk.
    """

    def __init__(
        self,
        chunk_size_words: int = CHUNK_SIZE_WORDS,
        chunk_overlap_words: int = CHUNK_OVERLAP_WORDS,
    ) -> None:
        if chunk_size_words <= 0:
            raise ValueError("chunk_size_words must be greater than zero")
        if chunk_overlap_words < 0:
            raise ValueError("chunk_overlap_words cannot be negative")
        if chunk_overlap_words >= chunk_size_words:
            raise ValueError("chunk_overlap_words must be smaller than chunk_size_words")

        self.chunk_size_words = chunk_size_words
        self.chunk_overlap_words = chunk_overlap_words
        self.step_size_words = chunk_size_words - chunk_overlap_words

    def chunk_sections(
        self,
        sections: list[FilingSection],
    ) -> list[FilingSectionChunk]:
        """
        Split parsed filing sections into overlapping word-window chunks.
        """
        section_chunks: list[FilingSectionChunk] = []

        for section in sections:
            section_chunks.extend(self._chunk_section(section))

        return section_chunks

    def _chunk_section(self, section: FilingSection) -> list[FilingSectionChunk]:
        words = self._split_into_words(section.text)
        if not words:
            return []

        chunks: list[FilingSectionChunk] = []
        chunk_index = 0
        word_start = 0

        while word_start < len(words):
            word_end = min(word_start + self.chunk_size_words, len(words))
            chunk_words = words[word_start:word_end]

            chunks.append(
                self._create_chunk(
                    section=section,
                    chunk_words=chunk_words,
                    chunk_index=chunk_index,
                    word_start=word_start,
                    word_end=word_end,
                )
            )

            chunk_index += 1
            if word_end == len(words):
                break

            word_start += self.step_size_words

        return chunks

    def _create_chunk(
        self,
        section: FilingSection,
        chunk_words: list[str],
        chunk_index: int,
        word_start: int,
        word_end: int,
    ) -> FilingSectionChunk:
        return FilingSectionChunk(
            chunk_id=self._make_chunk_id(section, chunk_index),
            section_id=section.section_id,
            chunk_index=chunk_index,
            word_start=word_start,
            word_end=word_end,
            metadata=section.metadata,
            chunk=self._reconstruct_text(chunk_words),
        )

    def _split_into_words(self, text: str) -> list[str]:
        return re.findall(r"\S+", text)

    def _reconstruct_text(self, words: list[str]) -> str:
        return " ".join(words)

    def _make_chunk_id(self, section: FilingSection, chunk_index: int) -> str:
        accession = section.metadata.accession or "unknown-accession"
        section_item = section.metadata.section_item or "unknown-section"
        return f"{accession}:{section_item}:{chunk_index}"


def chunk_sections(
    sections: list[FilingSection],
    chunk_size_words: int = CHUNK_SIZE_WORDS,
    chunk_overlap_words: int = CHUNK_OVERLAP_WORDS,
) -> list[FilingSectionChunk]:
    """
    Convenience wrapper for chunking parsed filing sections.
    """
    chunker = FilingChunker(
        chunk_size_words=chunk_size_words,
        chunk_overlap_words=chunk_overlap_words,
    )
    return chunker.chunk_sections(sections)
