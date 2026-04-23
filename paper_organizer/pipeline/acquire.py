"""Download a PDF for a given PaperMetadata.

Download cascade (stops at first success):
1. metadata.pdf_url  (Unpaywall best OA link)
2. PMC full-text PDF via PubMed Central
3. Europe PMC PDF mirror
"""

from __future__ import annotations

import re
from pathlib import Path

import httpx

from paper_organizer.pipeline.models import PaperMetadata

_UA = "paper-organizer/0.1 (mailto:paper-organizer@example.com)"
_EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


# ---------------------------------------------------------------------------
# Filename helpers
# ---------------------------------------------------------------------------


def _short_doi_suffix(doi: str) -> str:
    """Return the part after the last '/' in a DOI, safe for filenames.

    e.g. "10.1056/NEJMoa2304146" → "NEJMoa2304146"
    """
    if not doi:
        return ""
    suffix = doi.rsplit("/", 1)[-1]
    # Remove characters that are problematic in filenames
    return re.sub(r"[^\w.\-]", "_", suffix)


def _safe_filename(metadata: PaperMetadata) -> str:
    """Generate a safe PDF filename: {FirstAuthor}_{Year}_{short_doi}.pdf

    Falls back gracefully when fields are missing.
    """
    family = metadata.authors[0].family if metadata.authors else "Unknown"
    # Strip whitespace and characters unsafe for filenames
    family = re.sub(r"[^\w\-]", "_", family.strip())

    year = str(metadata.year) if metadata.year else "0000"

    suffix = _short_doi_suffix(metadata.doi)
    if suffix:
        return f"{family}_{year}_{suffix}.pdf"
    if metadata.pmid:
        return f"{family}_{year}_PMID{metadata.pmid}.pdf"
    return f"{family}_{year}.pdf"


# ---------------------------------------------------------------------------
# PDF validity check
# ---------------------------------------------------------------------------


def _is_valid_pdf(data: bytes) -> bool:
    """Return True iff data starts with the PDF magic bytes %PDF."""
    return data[:4] == b"%PDF"


# ---------------------------------------------------------------------------
# PMC ID lookup
# ---------------------------------------------------------------------------


async def _get_pmc_id(pmid: str, client: httpx.AsyncClient) -> str:
    """Return the PMC ID (without 'PMC' prefix) for a PMID, or '' if not found."""
    try:
        resp = await client.get(
            f"{_EUTILS_BASE}/elink.fcgi",
            params={
                "dbfrom": "pubmed",
                "db": "pmc",
                "id": pmid,
                "retmode": "json",
            },
        )
        if resp.status_code != 200:
            return ""
        body = resp.json()
        link_sets = body.get("linksets", [])
        for ls in link_sets:
            for ldb in ls.get("linksetdbs", []):
                if ldb.get("dbto") == "pmc":
                    ids = ldb.get("links", [])
                    if ids:
                        return str(ids[0])
    except Exception:
        pass
    return ""


# ---------------------------------------------------------------------------
# Download helpers
# ---------------------------------------------------------------------------


async def _try_download(url: str, client: httpx.AsyncClient) -> bytes | None:
    """Attempt to GET a URL and return bytes if response is a valid PDF."""
    try:
        resp = await client.get(url)
        if resp.status_code == 200 and _is_valid_pdf(resp.content):
            return resp.content
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Main acquire function
# ---------------------------------------------------------------------------


async def acquire_pdf(
    metadata: PaperMetadata,
    pdf_root: Path,
    *,
    skip_if_exists: bool = True,
) -> Path | None:
    """Try to download the paper PDF. Returns Path if successful, None if unavailable.

    Download cascade (stops at first success):
    1. metadata.pdf_url  (Unpaywall best OA link)
    2. PMC full-text PDF (fetches PMC ID from PMID if needed)
    3. Europe PMC PDF mirror
    """
    pdf_root.mkdir(parents=True, exist_ok=True)
    dest = pdf_root / _safe_filename(metadata)

    if skip_if_exists and dest.exists():
        return dest

    async with httpx.AsyncClient(
        headers={"User-Agent": _UA},
        timeout=60,
        follow_redirects=True,
    ) as client:

        # --- Step 1: Unpaywall best OA PDF ---
        if metadata.pdf_url:
            data = await _try_download(metadata.pdf_url, client)
            if data:
                dest.write_bytes(data)
                return dest

        # --- Steps 2 & 3: PMC PDF (requires a PMC ID) ---
        pmc_id = ""

        # Try to extract PMC ID from existing metadata fields
        if metadata.pmid:
            pmc_id = await _get_pmc_id(metadata.pmid, client)

        if pmc_id:
            # Step 2: PubMed Central direct PDF
            pmc_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc_id}/pdf/"
            data = await _try_download(pmc_url, client)
            if data:
                dest.write_bytes(data)
                return dest

            # Step 3: Europe PMC mirror
            epmc_url = (
                f"https://europepmc.org/backend/ptpmcrender.fcgi"
                f"?accid=PMC{pmc_id}&blobtype=pdf"
            )
            data = await _try_download(epmc_url, client)
            if data:
                dest.write_bytes(data)
                return dest

    return None
