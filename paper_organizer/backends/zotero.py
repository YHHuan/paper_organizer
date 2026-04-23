"""Zotero backend: push paper metadata + 7-section analysis to user's library."""
from __future__ import annotations

import html as _html
from pathlib import Path
from typing import Optional

from paper_organizer.config import AppConfig, get_secret
from paper_organizer.pipeline.models import PaperMetadata
from paper_organizer.pipeline.synthesize import (
    AnalysisSections,
    _SECTION_HEADERS,
    _SECTION_KEYS,
)


def _client(config: AppConfig):
    from pyzotero import zotero as pyzotero

    api_key = config.backend.zotero_api_key or get_secret("zotero_api_key")
    return pyzotero.Zotero(
        config.backend.zotero_library_id,
        config.backend.zotero_library_type,
        api_key,
    )


def _find_by_doi(zot, doi: str, title: str = "") -> Optional[str]:
    """Return existing item key if DOI already in library, else None.

    Zotero's q= parameter searches title/abstract/notes but NOT the DOI field.
    We search by title keywords and verify the DOI field exactly.
    """
    if not doi:
        return None
    # Use first 4 title words as search term; fall back to DOI suffix
    query = " ".join(title.split()[:4]) if title else doi.rsplit("/", 1)[-1]
    for item in zot.items(q=query, limit=20):
        if item.get("data", {}).get("DOI", "").strip().lower() == doi.lower():
            return item["key"]
    return None


def _build_journal_item(metadata: PaperMetadata) -> dict:
    creators = []
    for author in metadata.authors:
        given = author.given.strip()
        family = author.family.strip()
        if not given and not family:
            continue
        creators.append(
            {"creatorType": "author", "firstName": given, "lastName": family}
        )
    extra = f"PMID: {metadata.pmid}" if metadata.pmid else ""
    return {
        "itemType": "journalArticle",
        "title": metadata.title,
        "creators": creators,
        "abstractNote": metadata.abstract,
        "publicationTitle": metadata.journal,
        "date": str(metadata.year) if metadata.year else "",
        "DOI": metadata.doi,
        "url": metadata.url,
        "extra": extra,
        "tags": [{"tag": "paper-organizer"}],
        "relations": {},
    }


def _sections_to_html(sections: AnalysisSections, metadata: PaperMetadata) -> str:
    parts: list[str] = [
        f"<h2>{_html.escape(metadata.title)}</h2>",
        "<hr/>",
    ]
    for key in _SECTION_KEYS:
        header = _SECTION_HEADERS[key]
        content = getattr(sections, key, "") or ""
        parts.append(f"<h3>{_html.escape(header)}</h3>")
        if not content.strip():
            continue
        lines = [ln.strip() for ln in content.strip().splitlines()]
        if any(ln.startswith(("- ", "• ", "* ")) for ln in lines):
            items = "".join(
                f"<li>{_html.escape(ln.lstrip('-•* ').strip())}</li>"
                for ln in lines
                if ln
            )
            parts.append(f"<ul>{items}</ul>")
        else:
            paragraph = "<br/>".join(_html.escape(ln) for ln in lines if ln)
            parts.append(f"<p>{paragraph}</p>")
    return "\n".join(parts)


def push_to_zotero(
    metadata: PaperMetadata,
    sections: AnalysisSections,
    pdf_path: Optional[Path],
    config: AppConfig,
) -> tuple[str, bool]:
    """Push paper to Zotero library. Returns (item_key, created).

    created=False means the DOI was already in the library (deduplicated).
    Raises RuntimeError on API errors.
    """
    zot = _client(config)

    existing_key = _find_by_doi(zot, metadata.doi, metadata.title)
    if existing_key:
        return existing_key, False

    # Create top-level journal article item
    result = zot.create_items([_build_journal_item(metadata)])
    successful = result.get("successful", {})
    if not successful:
        raise RuntimeError(f"Zotero item creation failed: {result.get('failed', {})}")
    item_key: str = list(successful.values())[0]["key"]

    # Child note: 7-section HTML analysis
    zot.create_items([{
        "itemType": "note",
        "parentItem": item_key,
        "note": _sections_to_html(sections, metadata),
        "tags": [{"tag": "paper-organizer"}],
        "relations": {},
    }])

    # Linked PDF attachment (only if the file actually exists locally)
    if pdf_path and pdf_path.exists():
        zot.create_items([{
            "itemType": "attachment",
            "linkMode": "linked_file",
            "title": pdf_path.name,
            "path": str(pdf_path.resolve()),
            "contentType": "application/pdf",
            "parentItem": item_key,
            "tags": [],
            "relations": {},
        }])

    return item_key, True
