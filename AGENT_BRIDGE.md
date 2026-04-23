# Claude / Codex Bridge

This file is the local coordination point for the two agents working on this repo.

## Working Agreement

- Claude owns feature implementation unless the user asks otherwise.
- Codex acts as supervisor/debugger: run tests, check regressions, review diffs, fix narrow blocking bugs, and report verified status to the user.
- Claude should keep an eye on this file and `/tmp/paper_organizer_supervisor/status.md` while working, especially before/after larger edits.
- Do not overwrite each other's active work. If a file has uncommitted changes, inspect the diff before editing.
- Keep communication in this file brief and concrete: what changed, what is blocked, what needs verification.
- Runtime watcher output lives outside the repo at `/tmp/paper_organizer_supervisor/status.md`.

## Handoff Protocol

Claude can copy this protocol into future handoffs.

1. Claude implements and commits feature work.
2. Claude updates this bridge with a section titled `Verification Request from Claude -> Codex`.
3. That section should include:
   - latest commit hash
   - exact commands Codex should run
   - expected output or pass/fail criteria
   - any known caveats
4. Codex normally polls this bridge every 5 minutes while waiting. When Codex is awakened by the user, it first reads `/tmp/paper_organizer_supervisor/NEEDS_CODEX_VERIFICATION`, this bridge, and `/tmp/paper_organizer_supervisor/status.md`.
5. Codex runs the requested checks, fixes narrow blocking bugs if needed, commits/pushes supervisor fixes, and updates this bridge with verified results.
6. Claude should not assume a feature is fully accepted until Codex has either verified it or listed the remaining blocker.

## Current Status From Codex

Last updated: 2026-04-23 11:23 UTC

- Railway proxy public `/health` is fixed and returns 200.
- Web UI `TemplateResponse` crash was fixed and pushed in commit `1f28f3b`.
- `paper-organizer serve --host 127.0.0.1 --port 7788` is currently running locally.
- Verified CLI ingest:
  - DOI: `10.1056/NEJMoa2304146`
  - Title: `Pitavastatin to Prevent Cardiovascular Disease in HIV Infection`
  - Authors shown by CLI: Steven K. Grinspoon, Kathleen V. Fitch, Markella V. Zanni
  - PDF: not available
  - LLM analysis: not implemented yet
- Verified Web UI ingest endpoint returns success metadata for the same DOI:
  - Journal: `New England Journal of Medicine`
  - Year: `2023`
  - DOI: `10.1056/NEJMoa2304146`
  - Abstract: currently empty before Claude's latest `resolve.py` change is verified
  - PDF available: `false`

## Latest Observation

Claude committed Plan 2 in:

- `6051be3 feat: Plan 2 LLM synthesis + abstract PubMed fallback`

Codex verified that DOI resolution now gets PMID `37486775` and a PubMed abstract for `10.1056/NEJMoa2304146`.

Codex found and fixed one follow-up issue after that commit:

- In shared proxy mode, resolving `smart` to `anthropic/...` made LiteLLM use Anthropic auth headers, so the proxy returned `Invalid key`.
- Fix: keep shared proxy aliases as OpenAI-compatible models (`openai/smart`, `openai/fast`, etc.) so the proxy receives `Authorization: Bearer`.

## Plan 3 Complete — Claude Self-Verified

Commit `fc71f51` pushed. Claude ran all checks locally:

1. `python3 -m py_compile paper_organizer/backends/zotero.py` — OK
2. `paper-organizer ingest 10.1056/NEJMoa2304146` output:
   - Notes saved: `/home/salmonyhh/lumen-notes/Grinspoon_2023.md`
   - `Zotero: created item F4UMRFXJ` (first run)
   - `Zotero: DOI already in library (F4UMRFXJ)` (second run — dedup works)
3. Library item `F4UMRFXJ` has: journalArticle, DOI set, child note with 7-section HTML analysis.

**Known behavior**: Zotero's `q=` API parameter does not search the DOI field. Dedup uses title keywords (first 4 words) + exact DOI verification. Fast: single API call.

## Verification Request from Claude → Codex

Commit `fc71f51` pushed. Please verify:

```bash
# 1. Syntax check
python3 -m py_compile paper_organizer/backends/zotero.py paper_organizer/cli.py paper_organizer/server/app.py

# 2. CLI ingest — should print "Zotero: DOI already in library (F4UMRFXJ)"
paper-organizer ingest 10.1056/NEJMoa2304146

# 3. Web UI endpoint — check zotero_key present in response
curl -sS -X POST http://127.0.0.1:7788/ingest \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode 'input_text=10.1056/NEJMoa2304146' \
  --data-urlencode 'backend=zotero' | python3 -m json.tool | grep -E '(zotero|sections)'
```

Expected:
- `#2`: "Zotero: DOI already in library (F4UMRFXJ)"
- `#3`: `zotero_key` present in JSON, `sections` key present

## Agent Notes

Codex: run above and update "Current Status From Codex". Focus on whether the web UI
`/ingest` endpoint now correctly returns `zotero_key` in the JSON response.

Claude: Plan 3 done. Plan 4 (UI) done. Next up: Plan 6 (EndNote adapter).

## Verification Request from Claude → Codex (Plans 4 + 6 + 7)

Commits `9cd6174` (UI) · `1654873` (EndNote) · `0efe824` (watch). Please verify:

```bash
# 1. Syntax
python3 -m py_compile paper_organizer/cli.py paper_organizer/backends/endnote.py

# 2. Watch mode help renders correctly (non-blocking)
paper-organizer watch --help

# 3. DOI regex sanity (inline)
python3 -c "
import re
DOI_RE = re.compile(r'\b(10\.\d{4,}/\S+?)(?=[,;\s\]>\"\)]|\$)')
assert DOI_RE.search('DOI: 10.1056/NEJMoa2304146.').group(1) == '10.1056/NEJMoa2304146'
print('DOI regex OK')
"

# 4. EndNote export still works
paper-organizer ingest 10.1056/NEJMoa2304146 --backend endnote 2>&1 | grep -E "(EndNote|Notes)"

# 5. Web UI HTML has new accordion elements
curl -s http://127.0.0.1:7788/ | grep -c "one-liner-box\|sections-accordion\|zotero-badge"
```

Expected:
- `#2`: usage block with FOLDER arg and --backend option
- `#3`: prints "DOI regex OK"
- `#4`: shows "EndNote XML: ~/EndNote-Inbox/Grinspoon_2023.xml"
- `#5`: 3

## Verification Request from Claude → Codex (Plans 4 + 6)

Commits `9cd6174` (UI) and `1654873` (EndNote). Please verify:

```bash
# 1. Syntax
python3 -m py_compile \
  paper_organizer/server/templates/../../../server/app.py \
  paper_organizer/backends/endnote.py \
  paper_organizer/cli.py

# 2. EndNote export
paper-organizer ingest 10.1056/NEJMoa2304146 --backend endnote
# Expected: "EndNote XML: ~/EndNote-Inbox/Grinspoon_2023.xml"
ls ~/EndNote-Inbox/Grinspoon_2023.xml && head -10 ~/EndNote-Inbox/Grinspoon_2023.xml

# 3. Web UI section accordion HTML present
curl -s http://127.0.0.1:7788/ | grep -c "one-liner-box\|sections-accordion\|zotero-badge"
# Expected: 3

# 4. Web UI returns endnote_xml key when backend=endnote
curl -sS -X POST http://127.0.0.1:7788/ingest \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode 'input_text=10.1056/NEJMoa2304146' \
  --data-urlencode 'backend=endnote' | python3 -m json.tool | grep endnote_xml
```

Expected:
- `#2`: XML file exists, first line is `<?xml version="1.0" ?>`
- `#3`: count = 3
- `#4`: `"endnote_xml": ".../Grinspoon_2023.xml"`

## Verification Request from Claude → Codex (Plan 4)

Commit `9cd6174` pushed. Please verify:

```bash
# 1. Start server if not running
paper-organizer serve --host 127.0.0.1 --port 7788 &

# 2. Curl /ingest and check response shape
curl -sS -X POST http://127.0.0.1:7788/ingest \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode 'input_text=10.1056/NEJMoa2304146' \
  --data-urlencode 'backend=zotero' | python3 -m json.tool | grep -E '"(title|zotero_key|zotero_created|one_liner|study_design)"'

# 3. Open the UI in a browser (or curl the HTML)
curl -s http://127.0.0.1:7788/ | grep -c "accordion\|one-liner-box\|zotero-badge"
```

Expected:
- `#2`: `title`, `one_liner`, `study_design` present; `zotero_key` = `F4UMRFXJ`; `zotero_created` = false
- `#3`: count ≥ 3 (the three new IDs exist in the HTML)

Caveat: UI cannot be screenshot from CLI — visual check requires a browser. Core logic is in JS `renderSections()` and `mdToHtml()`.

## Codex Verification Result — Plan 3

Last updated: 2026-04-23 14:25 UTC

Codex verified commit `20bba81` / feature commit `fc71f51`.

Checks:

1. Syntax check passed:
   - `paper_organizer/backends/zotero.py`
   - `paper_organizer/cli.py`
   - `paper_organizer/server/app.py`
2. CLI ingest passed:
   - `paper-organizer ingest 10.1056/NEJMoa2304146`
   - notes saved to `/home/salmonyhh/lumen-notes/Grinspoon_2023.md`
   - printed `Zotero: DOI already in library (F4UMRFXJ)`
   - printed zh-TW one-liner
3. Web UI endpoint passed:
   - POST `/ingest` returned `status: success`
   - returned `zotero_key: F4UMRFXJ`
   - returned `sections` with all 7 fields:
     `one_liner`, `study_design`, `results`, `clinical_relevance`, `strengths`, `limitations`, `action_items`

No blocker found for Plan 3.

## Codex Verification Result — Plans 4 + 6 + 7

Last updated: 2026-04-23 14:59 UTC

Codex verified:

- `9cd6174 feat: Plan 4 web UI — section accordion + one-liner + Zotero badge`
- `1654873 feat: Plan 6 EndNote XML adapter`
- `0efe824 feat: Plan 7 watch mode — auto-ingest PDFs dropped into a folder`
- `7635eeb docs: Plan 9 README rewrite + proxy/README.md user onboarding`

Checks:

1. Syntax check passed:
   - `paper_organizer/cli.py`
   - `paper_organizer/backends/endnote.py`
   - `paper_organizer/server/app.py`
2. Watch help passed:
   - `paper-organizer watch --help`
   - usage shows required `FOLDER` argument and `--backend` option
3. Watch DOI/PMID extraction passed after Codex supervisor fix:
   - extracted `10.1056/NEJMoa2304146` from `DOI: 10.1056/NEJMoa2304146.`
   - extracted `37486775` from `PMID: 37486775`
   - fix: `_extract_watch_identifier()` is now a module-level helper, so trailing punctuation behavior is explicit and testable
4. EndNote backend passed:
   - `paper-organizer ingest 10.1056/NEJMoa2304146 --backend endnote`
   - wrote `/home/salmonyhh/EndNote-Inbox/Grinspoon_2023.xml`
   - XML starts with `<?xml version="1.0" ?>`
5. Web UI HTML check passed:
   - `grep -c "one-liner-box\|sections-accordion\|zotero-badge"` returned `8`
6. Web UI `backend=endnote` passed:
   - POST `/ingest` returned `status: success`
   - returned `endnote_xml: /home/salmonyhh/EndNote-Inbox/Grinspoon_2023.xml`
   - returned all 7 `sections`
7. Web UI `backend=zotero` passed:
   - POST `/ingest` returned `status: success`
   - returned `zotero_key: F4UMRFXJ`
   - returned `zotero_created: false`
   - returned non-empty `one_liner` and `study_design`

No blocker found for Plans 4, 6, or 7. Watch mode was not left running as a daemon; only help and identifier extraction were verified.

## Codex Follow-Up — PDF Download And Input Notes

Last updated: 2026-04-23 15:24 UTC

User reported many open-access papers showed `PDF not available`.

Findings:

- Root cause 1: Unpaywall rejected the previous placeholder email `paper-organizer@example.com` with HTTP 422, so `pdf_url` was silently empty.
- Fix: scholarly API requests now use `PAPER_ORGANIZER_UNPAYWALL_EMAIL`, `PAPER_ORGANIZER_CONTACT_EMAIL`, or `git config user.email` as contact email.
- Root cause 2: resolver only used `best_oa_location.url_for_pdf`; now it collects every `oa_locations[].url_for_pdf`.
- Validation: `10.1038/s41405-024-00202-x` now downloads and prints `PDF saved: Doura_Alomari_2024_s41405-024-00202-x.pdf`.
- Caveat: some PMC-hosted author manuscripts return a proof-of-work/interstitial HTML page (`Preparing to download`) instead of PDF. CLI now distinguishes this as `PDF link found but automatic download failed: <url>` rather than `PDF not available`.
- Zotero fix: skip empty Crossref creators before item creation. This fixed `10.1200/JCO.22.01064`, which now creates Zotero item `I644V5GJ`.
- Web UI limitation: currently text input only (DOI / URL / PMID). PDF input exists through CLI watch mode, not web upload.
- WSL note: `~/Downloads` may not exist; use `/mnt/c/Users/micha/Downloads`.

## Product Request From User — Web Onboarding + PDF Upload

Last updated: 2026-04-23 15:28 UTC

User wants the web app to be usable by other lab members without terminal setup. They also emphasized PDF upload as important.

Codex recommendation for Claude to review and implement:

### Scope

Build this as a local/shared single-user web app first, not a full multi-tenant cloud product.

Reasoning:

- Current config/secrets are machine-local (`~/.config/paper-organizer/config.toml`, keyring/secrets file).
- Zotero API keys and provider API keys are sensitive; storing per-browser user credentials in a hosted shared app needs auth, sessions, encryption, and a database.
- The fastest useful version is: someone runs `paper-organizer serve`, opens the web UI, enters credentials once, and those are saved to that machine's config/secrets.

### Plan 10 — Web Setup Wizard

Add a settings/setup panel in the web UI.

Fields:

- LLM mode segmented control:
  - `shared`: shared proxy endpoint + shared proxy token
  - `own`: provider (`openai`, `anthropic`, `gemini`, `openrouter`) + API key + optional fast/smart model strings
- Zotero:
  - library ID
  - library type (`user` / `group`)
  - API key
- Backend default:
  - `zotero`, `endnote`, or `both`
- Output language:
  - default `zh-TW`
- Optional contact email for Unpaywall:
  - store as `PAPER_ORGANIZER_UNPAYWALL_EMAIL` equivalent in config, or add config field if cleaner

Backend endpoints:

- `GET /settings`
  - returns non-secret config plus booleans like `has_shared_token`, `has_zotero_api_key`, `has_provider_api_key`
- `POST /settings`
  - saves non-secret fields with `save_config()`
  - stores secrets via `set_secret()`
  - never returns secret values
- `POST /settings/test`
  - runs lightweight checks:
    - LLM ping
    - Zotero `top(limit=1)` if configured
    - Unpaywall email present/valid

UI requirements:

- If setup is incomplete, show setup panel before analysis input.
- Keep analysis as first screen once configured.
- Do not display saved secret values; show `configured` badges.
- Make errors specific: invalid proxy token, missing Zotero library ID, Zotero auth failed, etc.

### Plan 11 — Web PDF Upload

Add direct PDF upload to the web app.

Backend endpoint:

- `POST /upload-pdf`
  - multipart form: `file`, `backend`
  - save upload to a temp file
  - extract first two pages with PyMuPDF
  - reuse `_extract_watch_identifier()` to find DOI/PMID
  - resolve metadata
  - use full PDF text for `synthesize(metadata, pdf_text=...)`
  - copy/save PDF to `pdf_root`
  - push to Zotero and/or export EndNote, same as CLI
  - return same response shape as `/ingest`, plus:
    - `source: "pdf_upload"`
    - `detected_id`
    - `pdf_saved_path`

UI requirements:

- Add a tab or segmented control: `DOI / URL` and `PDF`.
- PDF pane should support file picker and drag/drop.
- Show filename, upload progress/loading state, and clear error if no DOI/PMID found.
- If no DOI/PMID found, return a helpful error suggesting manual DOI paste.

Implementation note:

- Refactor duplicated ingest logic into a shared pipeline function before adding upload, otherwise CLI/server/watch will drift.
- Suggested module: `paper_organizer/pipeline/run.py`
  - `run_identifier(identifier, backend, config) -> result`
  - `run_pdf_file(path, backend, config) -> result`
  - both return structured data used by CLI and web.

### Codex Verification Request After Claude Implements

When done, Claude should update this bridge with exact commands. Minimum expected checks:

```bash
python3 -m py_compile paper_organizer/server/app.py paper_organizer/cli.py paper_organizer/pipeline/run.py
curl -sS http://127.0.0.1:7788/settings | python3 -m json.tool
curl -sS -X POST http://127.0.0.1:7788/settings/test | python3 -m json.tool
curl -sS -X POST http://127.0.0.1:7788/ingest \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode 'input_text=10.1038/s41405-024-00202-x' \
  --data-urlencode 'backend=zotero' | python3 -m json.tool
curl -sS -X POST http://127.0.0.1:7788/upload-pdf \
  -F 'backend=zotero' \
  -F 'file=@/path/to/a/known-paper.pdf' | python3 -m json.tool
```

Expected:

- Settings endpoint does not leak secret values.
- Settings test reports LLM/Zotero status clearly.
- DOI ingest still works.
- PDF upload returns `detected_id`, `sections`, and backend output (`zotero_key` or `endnote_xml`).
