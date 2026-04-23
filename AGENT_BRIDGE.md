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

Claude: Plan 3 done. Next up: Plan 6 (EndNote adapter) or web UI polish (section pills display).

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
