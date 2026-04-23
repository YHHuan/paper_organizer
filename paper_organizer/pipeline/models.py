"""Pydantic models for the paper-organizer pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import BaseModel


class Author(BaseModel):
    given: str = ""
    family: str = ""

    def full_name(self) -> str:
        return f"{self.given} {self.family}".strip()


class PaperMetadata(BaseModel):
    doi: str = ""
    pmid: str = ""
    title: str = ""
    authors: list[Author] = []
    journal: str = ""
    year: int = 0
    abstract: str = ""
    url: str = ""       # canonical URL
    pdf_url: str = ""   # best open-access PDF URL found
    pdf_urls: list[str] = []  # all open-access PDF URLs found
    is_open_access: bool = False

    def first_author_year(self) -> str:
        """e.g. 'Smith_2024'"""
        fa = self.authors[0].family if self.authors else "Unknown"
        return f"{fa}_{self.year}" if self.year else fa


class PipelineResult(BaseModel):
    metadata: PaperMetadata
    pdf_path: Optional[Path] = None
    pdf_available: bool = False
    notes_md: str = ""      # filled by later stages
    error: str = ""
