"""LLM synthesis pipeline: produces 7-section clinical analysis from paper text."""
from __future__ import annotations

import re
from dataclasses import dataclass

from paper_organizer.pipeline.models import PaperMetadata

_INSUFFICIENT = "(insufficient text — please ensure the paper abstract is available)"

_SECTION_KEYS = [
    "one_liner",
    "study_design",
    "results",
    "clinical_relevance",
    "strengths",
    "limitations",
    "action_items",
]

_SECTION_HEADERS = {
    "one_liner": "One-liner",
    "study_design": "Study Design",
    "results": "Results",
    "clinical_relevance": "Clinical Relevance",
    "strengths": "Strengths",
    "limitations": "Limitations",
    "action_items": "Action Items",
}


@dataclass
class AnalysisSections:
    one_liner: str = ""          # Section 1: one sentence clinical significance
    study_design: str = ""       # Section 2: structured study design
    results: str = ""            # Section 3: key quantitative results
    clinical_relevance: str = "" # Section 4: why this matters clinically
    strengths: str = ""          # Section 5: methodological strengths
    limitations: str = ""        # Section 6: limitations
    action_items: str = ""       # Section 7: what a clinician should do/know

    def to_markdown(self, metadata: PaperMetadata) -> str:
        """Render as a clean markdown document."""
        lines: list[str] = []

        # Header block
        title = metadata.title or "Untitled Paper"
        lines.append(f"# {title}\n")

        meta_parts: list[str] = []
        if metadata.authors:
            authors_str = ", ".join(a.full_name() for a in metadata.authors[:5])
            if len(metadata.authors) > 5:
                authors_str += " et al."
            meta_parts.append(authors_str)
        if metadata.journal:
            meta_parts.append(f"*{metadata.journal}*")
        if metadata.year:
            meta_parts.append(str(metadata.year))
        if meta_parts:
            lines.append(" | ".join(meta_parts) + "\n")

        id_parts: list[str] = []
        if metadata.doi:
            id_parts.append(f"DOI: [{metadata.doi}](https://doi.org/{metadata.doi})")
        if metadata.pmid:
            id_parts.append(
                f"PMID: [{metadata.pmid}](https://pubmed.ncbi.nlm.nih.gov/{metadata.pmid})"
            )
        if id_parts:
            lines.append(" | ".join(id_parts) + "\n")

        lines.append("---\n")

        # Sections
        for key in _SECTION_KEYS:
            header = _SECTION_HEADERS[key]
            content = getattr(self, key) or ""
            lines.append(f"## {header}\n")
            lines.append(content.strip() + "\n")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "one_liner": self.one_liner,
            "study_design": self.study_design,
            "results": self.results,
            "clinical_relevance": self.clinical_relevance,
            "strengths": self.strengths,
            "limitations": self.limitations,
            "action_items": self.action_items,
        }


def _graceful_stub() -> AnalysisSections:
    """Return an AnalysisSections where every field signals missing text."""
    return AnalysisSections(
        one_liner=_INSUFFICIENT,
        study_design=_INSUFFICIENT,
        results=_INSUFFICIENT,
        clinical_relevance=_INSUFFICIENT,
        strengths=_INSUFFICIENT,
        limitations=_INSUFFICIENT,
        action_items=_INSUFFICIENT,
    )


def _build_prompt(text: str, lang: str) -> str:
    return f"""You are a clinical research assistant helping a physician read a medical/scientific paper.

Analyze the following paper text and produce a structured clinical summary with exactly 7 sections.
Output each section with a header formatted exactly as `## <Section Name>` on its own line.
Write your entire response in {lang}.

Be concise — do not pad or repeat:
- **One-liner**: 1-2 sentences. The single most important clinical take-away.
- **Study Design**: A structured list with these fields (one per line):
  - Design type:
  - Population:
  - Intervention:
  - Comparator:
  - Primary outcome:
  - Follow-up:
  - N:
- **Results**: Bullet points of key quantitative findings with confidence intervals and p-values where available.
- **Clinical Relevance**: 2-3 sentences focused on "so what for patients and practice".
- **Strengths**: 2-3 bullet points on methodological strengths.
- **Limitations**: 3-5 bullet points on study limitations.
- **Action Items**: 2-3 actionable bullet points for a practising clinician.

Use exactly these section headers (in this order):
## One-liner
## Study Design
## Results
## Clinical Relevance
## Strengths
## Limitations
## Action Items

Paper text:
---
{text}
---"""


def _parse_sections(raw: str) -> AnalysisSections:
    """Split LLM response on `## ` headers and map to AnalysisSections fields."""
    # Map normalised header text → dataclass field name
    header_map: dict[str, str] = {v.lower(): k for k, v in _SECTION_HEADERS.items()}

    sections: dict[str, str] = {}
    current_key: str | None = None
    current_lines: list[str] = []

    def _field_for_header(line: str) -> str | None:
        header_text = line.strip()
        if not header_text.startswith("#"):
            return None
        header_text = header_text.lstrip("#").strip().lower()
        header_text = re.sub(r"^\d+[\).:\-\s]+", "", header_text)
        header_text = header_text.rstrip(":：").strip()
        if header_text in header_map:
            return header_map[header_text]
        for expected, field_name in header_map.items():
            if expected in header_text:
                return field_name
        return None

    for line in raw.splitlines():
        header_key = _field_for_header(line)
        if header_key:
            # Save the previous section
            if current_key is not None:
                sections[current_key] = "\n".join(current_lines).strip()
            current_key = header_key
            current_lines = []
        else:
            if current_key is not None:
                current_lines.append(line)

    # Flush the last section
    if current_key is not None:
        sections[current_key] = "\n".join(current_lines).strip()

    if not sections and raw.strip():
        sections["one_liner"] = raw.strip()

    return AnalysisSections(
        one_liner=sections.get("one_liner", ""),
        study_design=sections.get("study_design", ""),
        results=sections.get("results", ""),
        clinical_relevance=sections.get("clinical_relevance", ""),
        strengths=sections.get("strengths", ""),
        limitations=sections.get("limitations", ""),
        action_items=sections.get("action_items", ""),
    )


async def synthesize(
    metadata: PaperMetadata,
    pdf_text: str = "",  # full text if available; else use abstract
    *,
    config=None,
    lang: str = "zh-TW",  # output language
) -> AnalysisSections:
    """Run a single LLM call to produce a 7-section clinical analysis.

    Uses pdf_text (first 6000 chars) if provided, otherwise falls back to
    metadata.abstract.  Returns a graceful stub if no text is available or
    if the LLM call fails.
    """
    from paper_organizer.llm.client import chat

    # Choose the input text source
    if pdf_text:
        text = pdf_text[:6000]
    elif metadata.abstract:
        text = metadata.abstract
    else:
        return _graceful_stub()

    prompt = _build_prompt(text, lang)
    messages = [{"role": "user", "content": prompt}]

    try:
        raw = await chat(messages, model="smart", config=config, max_tokens=2048)
        sections = _parse_sections(raw)
        return sections
    except Exception:
        return _graceful_stub()
