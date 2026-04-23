"""EndNote backend: write an XML import package to the inbox folder.

Drops a .xml file (+ optional PDF copy) into endnote_inbox so the user can
File → Import → EndNote XML in their desktop client.  No API needed.
"""
from __future__ import annotations

import shutil
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional
from xml.dom import minidom

from paper_organizer.config import AppConfig
from paper_organizer.pipeline.models import PaperMetadata
from paper_organizer.pipeline.synthesize import AnalysisSections


def _indent(xml_str: str) -> str:
    """Return pretty-printed XML with 2-space indentation."""
    return minidom.parseString(xml_str).toprettyxml(indent="  ", encoding=None)


def _build_xml(metadata: PaperMetadata, sections: AnalysisSections) -> str:
    xml_root = ET.Element("xml")
    records  = ET.SubElement(xml_root, "records")
    record   = ET.SubElement(records, "record")

    # Ref type 17 = Journal Article
    ref_type = ET.SubElement(record, "ref-type")
    ref_type.set("name", "Journal Article")
    ref_type.text = "17"

    # Authors
    contribs = ET.SubElement(record, "contributors")
    authors_el = ET.SubElement(contribs, "authors")
    for author in metadata.authors:
        a = ET.SubElement(authors_el, "author")
        # EndNote expects "Family, Given"
        a.text = f"{author.family}, {author.given}".strip(", ")

    # Titles
    titles = ET.SubElement(record, "titles")
    title_el = ET.SubElement(titles, "title")
    title_el.text = metadata.title
    sec_title = ET.SubElement(titles, "secondary-title")
    sec_title.text = metadata.journal

    # Periodical
    periodical = ET.SubElement(record, "periodical")
    full_title = ET.SubElement(periodical, "full-title")
    full_title.text = metadata.journal

    # Year
    dates = ET.SubElement(record, "dates")
    year_el = ET.SubElement(dates, "year")
    year_el.text = str(metadata.year) if metadata.year else ""

    # DOI
    doi_el = ET.SubElement(record, "electronic-resource-num")
    doi_el.text = metadata.doi

    # Abstract
    abstract_el = ET.SubElement(record, "abstract")
    abstract_el.text = metadata.abstract

    # URL
    urls = ET.SubElement(record, "urls")
    related = ET.SubElement(urls, "related-urls")
    url_el = ET.SubElement(related, "url")
    url_el.text = metadata.url or (f"https://doi.org/{metadata.doi}" if metadata.doi else "")

    # PMID in custom1
    if metadata.pmid:
        custom1 = ET.SubElement(record, "custom1")
        custom1.text = f"PMID: {metadata.pmid}"

    # 7-section analysis as research notes (plain text, markdown)
    notes_lines: list[str] = []
    from paper_organizer.pipeline.synthesize import _SECTION_HEADERS, _SECTION_KEYS
    for key in _SECTION_KEYS:
        header = _SECTION_HEADERS[key]
        content = getattr(sections, key, "") or ""
        notes_lines.append(f"## {header}")
        notes_lines.append(content.strip())
        notes_lines.append("")
    notes_el = ET.SubElement(record, "research-notes")
    notes_el.text = "\n".join(notes_lines).strip()

    raw = ET.tostring(xml_root, encoding="unicode", xml_declaration=False)
    pretty = _indent(f'<?xml version="1.0" encoding="UTF-8"?>{raw}')
    # minidom adds an extra <?xml ...?> header when encoding=None — strip it so
    # we get exactly one declaration at the top.
    lines = pretty.splitlines()
    # Keep only the first <?xml line and the rest
    out_lines = [lines[0]] + [l for l in lines[1:] if not l.strip().startswith("<?xml")]
    return "\n".join(out_lines) + "\n"


def export_to_endnote(
    metadata: PaperMetadata,
    sections: AnalysisSections,
    pdf_path: Optional[Path],
    config: AppConfig,
) -> Path:
    """Write XML (+ optional PDF) to endnote_inbox. Returns the XML path.

    The user can then do: EndNote → File → Import → Folder → endnote_inbox.
    """
    inbox = Path(config.backend.endnote_inbox).expanduser()
    inbox.mkdir(parents=True, exist_ok=True)

    safe_name = metadata.first_author_year().replace(" ", "_")
    xml_path = inbox / f"{safe_name}.xml"
    xml_path.write_text(_build_xml(metadata, sections), encoding="utf-8")

    # Copy PDF alongside the XML so it can be manually attached in EndNote
    if pdf_path and pdf_path.exists():
        dest_pdf = inbox / pdf_path.name
        if not dest_pdf.exists():
            shutil.copy2(pdf_path, dest_pdf)

    return xml_path
