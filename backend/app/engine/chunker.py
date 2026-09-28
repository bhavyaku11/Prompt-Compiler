"""Deterministic text chunking and content hashing engine."""

from dataclasses import dataclass, field
import hashlib
import re
from typing import Any

from app.config import settings


@dataclass(frozen=True)
class ChunkItem:
    """A single deterministic chunk of text with position and hash metadata."""

    chunk_index: int
    content: str
    content_hash: str
    char_start: int
    char_end: int
    metadata: dict[str, Any] = field(default_factory=dict)


def compute_content_hash(text: str) -> str:
    """Calculate deterministic SHA-256 hex digest for normalized text."""
    normalized = normalize_text(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def normalize_text(text: str) -> str:
    """Normalize whitespace and line endings deterministically."""
    if not text:
        return ""
    # Normalize CRLF and CR to LF
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Remove null bytes or control characters
    text = text.replace("\x00", "")
    # Strip trailing whitespace on each line
    lines = [line.rstrip() for line in text.split("\n")]
    result = "\n".join(lines)
    return result.strip()


class TextChunker:
    """Deterministic, paragraph- and line-aware text chunker with configurable overlap."""

    def __init__(
        self,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ) -> None:
        self.chunk_size = chunk_size or settings.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError(
                f"chunk_overlap ({self.chunk_overlap}) must be strictly less than chunk_size ({self.chunk_size})"
            )

    def chunk_text(
        self,
        text: str,
        source_name: str = "",
        source_type: str = "documentation",
        base_metadata: dict[str, Any] | None = None,
    ) -> list[ChunkItem]:
        """Split text into sequential, overlapping chunks preserving paragraph/line boundaries."""
        normalized = normalize_text(text)
        if not normalized:
            return []

        # If text is smaller than chunk_size, return single chunk
        if len(normalized) <= self.chunk_size:
            chunk_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
            meta = dict(base_metadata or {})
            if source_name:
                meta["source_name"] = source_name
            meta["source_type"] = source_type
            return [
                ChunkItem(
                    chunk_index=0,
                    content=normalized,
                    content_hash=chunk_hash,
                    char_start=0,
                    char_end=len(normalized),
                    metadata=meta,
                )
            ]

        # Break text into atomic segments: prefer paragraphs (\n\n), then lines (\n), then words
        paragraphs = re.split(r"(\n\n+)", normalized)
        segments: list[str] = []
        for p in paragraphs:
            if not p:
                continue
            if len(p) <= self.chunk_size:
                segments.append(p)
            else:
                # Break long paragraph by single newlines
                sub_lines = re.split(r"(\n+)", p)
                for sl in sub_lines:
                    if not sl:
                        continue
                    if len(sl) <= self.chunk_size:
                        segments.append(sl)
                    else:
                        # Break long line by sentences or words
                        words = sl.split(" ")
                        cur_w = []
                        cur_len = 0
                        for w in words:
                            w_len = len(w) + (1 if cur_w else 0)
                            if cur_len + w_len <= self.chunk_size:
                                cur_w.append(w)
                                cur_len += w_len
                            else:
                                if cur_w:
                                    segments.append(" ".join(cur_w))
                                cur_w = [w]
                                cur_len = len(w)
                        if cur_w:
                            segments.append(" ".join(cur_w))

        # Assemble segments into sliding chunks with overlap
        chunks: list[ChunkItem] = []
        cur_content = ""
        cur_start = 0
        step_back_size = self.chunk_overlap

        for seg in segments:
            candidate = cur_content + seg if not cur_content else cur_content + seg
            if len(candidate) <= self.chunk_size:
                cur_content = candidate
            else:
                if cur_content.strip():
                    stripped = cur_content.strip()
                    c_hash = hashlib.sha256(stripped.encode("utf-8")).hexdigest()
                    meta = dict(base_metadata or {})
                    if source_name:
                        meta["source_name"] = source_name
                    meta["source_type"] = source_type
                    chunks.append(
                        ChunkItem(
                            chunk_index=len(chunks),
                            content=stripped,
                            content_hash=c_hash,
                            char_start=cur_start,
                            char_end=cur_start + len(stripped),
                            metadata=meta,
                        )
                    )
                    # Advance start with overlap
                    overlap_text = cur_content[-step_back_size:] if len(cur_content) > step_back_size else ""
                    cur_start = cur_start + len(cur_content) - len(overlap_text)
                    cur_content = overlap_text + seg
                else:
                    cur_content = seg

        if cur_content.strip():
            stripped = cur_content.strip()
            c_hash = hashlib.sha256(stripped.encode("utf-8")).hexdigest()
            meta = dict(base_metadata or {})
            if source_name:
                meta["source_name"] = source_name
            meta["source_type"] = source_type
            chunks.append(
                ChunkItem(
                    chunk_index=len(chunks),
                    content=stripped,
                    content_hash=c_hash,
                    char_start=cur_start,
                    char_end=cur_start + len(stripped),
                    metadata=meta,
                )
            )

        return chunks
