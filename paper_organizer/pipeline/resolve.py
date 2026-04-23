"""Resolve any paper identifier to PaperMetadata.

Supported input formats
-----------------------
- PubMed URL:  https://pubmed.ncbi.nlm.nih.gov/12345678
- DOI URL:     https://doi.org/10.xxxx/...
- URL with     doi= query param or "DOI:" fragment in body
- Raw DOI:     10.1056/NEJMoa2304146
- PMID:        bare integer string "12345678" or "PMID: 12345678"
"""

from __future__ import annotations

import re
from typing import Any

import httpx

from paper_organizer.pipeline.models import Author, PaperMetadata

_MAILTO = "paper-organizer@example.com"
_UA = f"paper-organizer/0.1 (mailto:{_MAILTO})"
_CROSSREF_BASE = "https://api.crossref.org/works"
_UNPAYWALL_BASE = "https://api.unpaywall.org/v2"
_EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

# Matches a bare DOI (starts with "10." followed by registrant/suffix)
_DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s\"'<>]+)", re.IGNORECASE)
# Matches a bare PMID (6–8 digits that are not part of a longer number)
_PMID_RE = re.compile(r"(?:^|\bPMID[:\s]+)(\d{6,8})(?!\d)", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Input type detection
# ---------------------------------------------------------------------------


def detect_input_type(input_str: str) -> tuple[str, str]:
    """Return (kind, canonical_value) for the given input string.

    kind is one of: "doi" | "pmid" | "url" | "unknown"
    canonical_value is the cleaned DOI / PMID / URL.
    """
    s = input_str.strip()

    # PubMed URL → extract PMID
    pm_match = re.search(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)", s)
    if pm_match:
        return ("pmid", pm_match.group(1))

    # doi.org URL → extract DOI
    doi_url_match = re.search(r"doi\.org/(.+)", s, re.IGNORECASE)
    if doi_url_match:
        return ("doi", doi_url_match.group(1).rstrip("/"))

    # URL with ?doi= or &doi= query param
    doi_param = re.search(r"[?&]doi=([^&\s]+)", s, re.IGNORECASE)
    if doi_param:
        return ("doi", doi_param.group(1))

    # "DOI:" anywhere in the string
    doi_colon = re.search(r"DOI:\s*(\S+)", s, re.IGNORECASE)
    if doi_colon:
        return ("doi", doi_colon.group(1).rstrip("."))

    # Bare DOI (starts with "10.")
    doi_bare = _DOI_RE.search(s)
    if doi_bare and not s.startswith("http"):
        return ("doi", doi_bare.group(1))

    # "PMID: 12345678" or bare integer
    pmid_match = _PMID_RE.search(s)
    if pmid_match:
        return ("pmid", pmid_match.group(1))
    if re.fullmatch(r"\d{6,8}", s):
        return ("pmid", s)

    # Any other URL
    if s.startswith("http://") or s.startswith("https://"):
        return ("url", s)

    return ("unknown", s)


# ---------------------------------------------------------------------------
# Crossref resolver
# ---------------------------------------------------------------------------


def _parse_crossref(data: dict[str, Any]) -> PaperMetadata:
    """Parse a Crossref works/{doi} response into PaperMetadata."""
    msg = data.get("message", {})

    # Authors
    raw_authors = msg.get("author", [])
    authors = [
        Author(given=a.get("given", ""), family=a.get("family", ""))
        for a in raw_authors
    ]

    # Year: prefer published-print, fall back to published-online / created
    year = 0
    for date_key in ("published-print", "published-online", "created"):
        parts = msg.get(date_key, {}).get("date-parts", [[]])
        if parts and parts[0]:
            year = int(parts[0][0])
            break

    # Title
    titles = msg.get("title", [])
    title = titles[0] if titles else ""

    # Journal
    container = msg.get("container-title", [])
    journal = container[0] if container else ""

    # Abstract (Crossref may include JATS XML — strip tags)
    abstract_raw = msg.get("abstract", "")
    abstract = re.sub(r"<[^>]+>", "", abstract_raw).strip()

    doi = msg.get("DOI", "")
    url = msg.get("URL", f"https://doi.org/{doi}" if doi else "")

    return PaperMetadata(
        doi=doi,
        title=title,
        authors=authors,
        journal=journal,
        year=year,
        abstract=abstract,
        url=url,
    )


async def resolve_doi(doi: str) -> PaperMetadata:
    """Resolve a DOI via Crossref + Unpaywall; never raises."""
    metadata = PaperMetadata(doi=doi, url=f"https://doi.org/{doi}")

    async with httpx.AsyncClient(
        headers={"User-Agent": _UA},
        timeout=30,
        follow_redirects=True,
    ) as client:
        # --- Crossref ---
        try:
            resp = await client.get(
                f"{_CROSSREF_BASE}/{doi}",
                params={"mailto": _MAILTO},
            )
            if resp.status_code == 200:
                metadata = _parse_crossref(resp.json())
                metadata.doi = doi  # ensure it's always set
        except Exception:
            pass

        # --- Unpaywall ---
        try:
            resp = await client.get(
                f"{_UNPAYWALL_BASE}/{doi}",
                params={"email": _MAILTO},
            )
            if resp.status_code == 200:
                uw = resp.json()
                metadata.is_open_access = bool(uw.get("is_oa", False))
                best = uw.get("best_oa_location") or {}
                pdf = best.get("url_for_pdf") or ""
                if pdf:
                    metadata.pdf_url = pdf
        except Exception:
            pass

        # --- PubMed abstract fallback ---
        # If Crossref didn't supply an abstract, look it up via DOI→PMID→efetch
        if not metadata.abstract and metadata.doi:
            try:
                search_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
                r = await client.get(search_url, params={
                    "db": "pubmed", "term": f"{doi}[doi]", "retmode": "json"
                })
                ids = r.json().get("esearchresult", {}).get("idlist", [])
                if ids:
                    pmid = ids[0]
                    metadata.pmid = pmid
                    # fetch abstract
                    fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
                    rf = await client.get(fetch_url, params={
                        "db": "pubmed", "id": pmid, "rettype": "abstract", "retmode": "xml"
                    })
                    match = re.search(r'<AbstractText[^>]*>(.*?)</AbstractText>', rf.text, re.DOTALL)
                    if match:
                        metadata.abstract = re.sub(r'<[^>]+>', '', match.group(1)).strip()
            except Exception:
                pass

    return metadata


# ---------------------------------------------------------------------------
# NCBI eutils resolver
# ---------------------------------------------------------------------------


def _parse_eutils_summary(uid: str, result: dict[str, Any]) -> PaperMetadata:
    """Parse an esummary result record into a PaperMetadata."""
    rec = result.get(uid, {})

    title = rec.get("title", "")
    journal = rec.get("source", "")

    # pubdate: "2023 Nov" or "2023 Nov 15" → extract year
    pubdate = rec.get("pubdate", "")
    year = 0
    year_match = re.search(r"\b(\d{4})\b", pubdate)
    if year_match:
        year = int(year_match.group(1))

    # authors: list of {"name": "Smith J"} dicts
    raw_authors = rec.get("authors", [])
    authors: list[Author] = []
    for a in raw_authors:
        name = a.get("name", "")
        parts = name.rsplit(" ", 1)
        if len(parts) == 2:
            authors.append(Author(family=parts[0], given=parts[1]))
        else:
            authors.append(Author(family=name))

    # DOI from elocationid or articleids
    doi = ""
    for aid in rec.get("articleids", []):
        if aid.get("idtype") == "doi":
            doi = aid.get("value", "")
            break

    return PaperMetadata(
        pmid=uid,
        doi=doi,
        title=title,
        journal=journal,
        year=year,
        authors=authors,
        url=f"https://pubmed.ncbi.nlm.nih.gov/{uid}",
    )


async def resolve_pmid(pmid: str) -> PaperMetadata:
    """Resolve a PMID via NCBI eutils; never raises."""
    metadata = PaperMetadata(
        pmid=pmid,
        url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}",
    )

    async with httpx.AsyncClient(
        headers={"User-Agent": _UA},
        timeout=30,
        follow_redirects=True,
    ) as client:
        try:
            resp = await client.get(
                f"{_EUTILS_BASE}/esummary.fcgi",
                params={"db": "pubmed", "id": pmid, "retmode": "json"},
            )
            if resp.status_code == 200:
                body = resp.json()
                result = body.get("result", {})
                metadata = _parse_eutils_summary(pmid, result)
        except Exception:
            pass

    # If a DOI was found, enrich with Crossref + Unpaywall
    if metadata.doi:
        enriched = await resolve_doi(metadata.doi)
        # Merge: keep PMID from eutils, prefer Crossref data for the rest
        if enriched.title:
            enriched.pmid = pmid
            return enriched
        # Crossref gave nothing useful — at least copy pdf_url
        metadata.pdf_url = enriched.pdf_url
        metadata.is_open_access = enriched.is_open_access

    return metadata


# ---------------------------------------------------------------------------
# Generic URL fallback — try to extract DOI from page
# ---------------------------------------------------------------------------


async def _resolve_url(url: str) -> PaperMetadata:
    """Best-effort: fetch URL, grep for a DOI in the body, delegate to resolve_doi."""
    async with httpx.AsyncClient(
        headers={"User-Agent": _UA},
        timeout=30,
        follow_redirects=True,
    ) as client:
        try:
            resp = await client.get(url)
            text = resp.text
            doi_match = _DOI_RE.search(text)
            if doi_match:
                return await resolve_doi(doi_match.group(1))
        except Exception:
            pass

    return PaperMetadata(url=url)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def resolve(input_str: str) -> PaperMetadata:
    """Resolve any paper identifier to PaperMetadata.

    Detects the input type and delegates to the appropriate resolver.
    Never raises; returns a partially-filled PaperMetadata on error.
    """
    kind, value = detect_input_type(input_str.strip())

    if kind == "doi":
        return await resolve_doi(value)
    if kind == "pmid":
        return await resolve_pmid(value)
    if kind == "url":
        return await _resolve_url(value)

    # "unknown" — last-ditch: treat it as a DOI if it looks like one
    doi_match = _DOI_RE.search(value)
    if doi_match:
        return await resolve_doi(doi_match.group(1))

    return PaperMetadata()
