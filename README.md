# paper-organizer

Paste a DOI, PubMed URL, or PMID → get a structured 7-section clinical analysis saved to Zotero and/or an EndNote import package. Works as a CLI, a mobile-friendly web app, or an auto-watch folder.

---

## Quick start (lab members)

### 1. Install

```bash
# Requires Python 3.11+
pip install uv          # if you don't have uv yet
uv tool install git+https://github.com/YHHuan/paper-organizer.git
```

### 2. Configure

```bash
paper-organizer init
```

The wizard asks for:
- **LLM mode** — choose `shared` if your PI gave you a proxy token; choose `own` if you have your own API key
- **Zotero library ID and API key** — get them from [zotero.org/settings/keys](https://www.zotero.org/settings/keys)
- **Notes folder** — where `.md` analysis files are saved (default `~/lumen-notes`)

### 3. Verify

```bash
paper-organizer doctor
```

Should print `All checks passed`.

---

## Usage

### Ingest a paper by DOI / URL / PMID

```bash
paper-organizer ingest 10.1056/NEJMoa2304146
paper-organizer ingest https://pubmed.ncbi.nlm.nih.gov/37486775
paper-organizer ingest PMID:37486775
```

What happens:
1. Fetches metadata from Crossref + PubMed abstract
2. Downloads the open-access PDF if available
3. Runs LLM 7-section clinical analysis in zh-TW (configurable)
4. Saves `~/lumen-notes/Grinspoon_2023.md`
5. Creates a Zotero item with a structured child note (deduplicated by DOI)

Example output:

```
Pitavastatin to Prevent Cardiovascular Disease in HIV Infection
Steven K. Grinspoon, Kathleen V. Fitch, Markella V. Zanni (2023)
PDF not available (open access only)
Notes saved: ~/lumen-notes/Grinspoon_2023.md
Zotero: created item F4UMRFXJ

Clinical Analysis
One-liner: REPRIEVE試驗顯示，對於接受抗反轉錄病毒治療且心血管風險為低至中等的HIV感染者…
```

### Override the backend

```bash
paper-organizer ingest 10.1056/NEJMoa2304146 --backend endnote   # EndNote XML only
paper-organizer ingest 10.1056/NEJMoa2304146 --backend both       # Zotero + EndNote
```

### Web UI (desktop + mobile)

```bash
paper-organizer serve          # http://localhost:7788
paper-organizer serve --tunnel # prints a public Cloudflare URL for your phone
```

The web UI lets you paste a DOI and see the full analysis with expandable sections — no terminal required.

### Watch a folder (auto-ingest PDFs)

```bash
paper-organizer watch ~/Downloads
```

Drop any paper PDF into `~/Downloads` — the tool detects the DOI from the first two pages and runs the full pipeline automatically. Works great as a background process alongside Zotero's own "watch folder" feature.

```bash
# Run in background
paper-organizer watch ~/Downloads --backend both &
```

---

## What gets created

### Zotero

- Top-level **Journal Article** item with full metadata (title, authors, DOI, abstract, PMID)
- Child **note** with 7-section analysis rendered as HTML:
  - Clinical Takeaway (one-liner)
  - Study Design (structured: N, intervention, outcome, follow-up)
  - Results (key numbers with CIs / p-values)
  - Clinical Relevance
  - Strengths
  - Limitations
  - Action Items
- **Linked PDF** attachment if an open-access copy was found

DOI-based deduplication: re-ingesting the same paper prints "already in library" and skips creation.

### Markdown notes (`~/lumen-notes/`)

Same 7 sections in clean Markdown. Example: `Grinspoon_2023.md`.

### EndNote (`~/EndNote-Inbox/`)

An `.xml` file importable via **File → Import → EndNote XML**, plus a PDF copy placed in the same folder for manual attachment. Use this if you don't have Zotero.

---

## LLM modes

| Mode | Setup | Who pays |
|------|-------|----------|
| `shared` | Enter the proxy token your PI gave you during `init` | Proxy owner (capped per user) |
| `own` (OpenAI) | Enter your `sk-...` key | You |
| `own` (Anthropic) | Enter your `sk-ant-...` key | You |
| `own` (Gemini) | Enter your Google AI Studio key | You |
| `own` (OpenRouter) | Enter your OpenRouter key | You |

Output language defaults to `zh-TW`. Change it in `~/.config/paper-organizer/config.toml`:

```toml
[user]
summary_lang = "en"   # or zh-TW, ja, etc.
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `LLM unreachable` in doctor | Check your proxy token or API key; run `paper-organizer init` again |
| `Zotero API` fail in doctor | Verify your library ID and API key at [zotero.org/settings/keys](https://www.zotero.org/settings/keys) |
| "No DOI or PMID found" in watch mode | The PDF's first two pages don't contain an extractable ID; ingest it manually with `paper-organizer ingest <doi>` |
| PDF not saved | Only open-access PDFs are downloaded automatically; subscription papers need manual upload to Zotero |

---

## For team owners: setting up the shared proxy

See [`proxy/README.md`](proxy/README.md) for full Railway deployment instructions and how to issue virtual keys to lab members.

---

## Status

- [x] CLI: init / doctor / ingest / serve / watch
- [x] Config + secret management (keyring, WSL-safe file fallback)
- [x] LLM client: shared proxy or own key (OpenAI / Anthropic / Gemini / OpenRouter)
- [x] DOI / URL / PMID resolver (Crossref + Unpaywall + PubMed)
- [x] PDF downloader (OA cascade: Unpaywall → PMC → Europe PMC)
- [x] 7-section LLM synthesis in any language
- [x] Zotero adapter (metadata + child note + linked PDF, DOI dedup)
- [x] EndNote XML adapter (drag-import package)
- [x] Mobile-friendly web UI with section accordion
- [x] Watch folder mode (auto-detect DOI from PDF, full pipeline)
- [x] Shared LLM proxy on Railway (virtual keys, OpenRouter backend)
