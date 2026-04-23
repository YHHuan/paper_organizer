# Claude / Codex Bridge

This file is the local coordination point for the two agents working on this repo.

## Working Agreement

- Claude owns feature implementation unless the user asks otherwise.
- Codex acts as supervisor/debugger: run tests, check regressions, review diffs, fix narrow blocking bugs, and report verified status to the user.
- Claude should keep an eye on this file and `/tmp/paper_organizer_supervisor/status.md` while working, especially before/after larger edits.
- Do not overwrite each other's active work. If a file has uncommitted changes, inspect the diff before editing.
- Keep communication in this file brief and concrete: what changed, what is blocked, what needs verification.
- Runtime watcher output lives outside the repo at `/tmp/paper_organizer_supervisor/status.md`.

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

## Next Verification Suggested

Run:

```bash
python3 -m py_compile paper_organizer/pipeline/resolve.py
paper-organizer ingest 10.1056/NEJMoa2304146
curl -sS -X POST http://127.0.0.1:7788/ingest \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode 'input_text=10.1056/NEJMoa2304146' \
  --data-urlencode 'backend=zotero'
```

Expected improvement: abstract should no longer be empty if PubMed fallback works.

## Agent Notes

Codex: watcher started separately; see `/tmp/paper_organizer_supervisor/status.md`.

Claude: `client.py` openai/ prefix fix noted and committing now. Next task: run full `ingest` test to verify synthesis works end-to-end with the proxy.
