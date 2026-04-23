# paper-organizer

Research paper analysis CLI — paste a DOI/URL/PMID, get structured notes pushed to Zotero or an EndNote import package.

## Install

```bash
pip install git+https://github.com/YHHuan/paper_organizer.git
```

Or with [uv](https://github.com/astral-sh/uv):

```bash
uv tool install git+https://github.com/YHHuan/paper_organizer.git
```

## Quick start

```bash
paper-organizer init      # interactive setup (LLM key, Zotero, etc.)
paper-organizer doctor    # verify everything is reachable
paper-organizer ingest https://pubmed.ncbi.nlm.nih.gov/12345678
```

## LLM modes

| Mode | How | Who pays |
|------|-----|----------|
| `shared` | Virtual key on the team proxy | Proxy owner (capped per user) |
| `own` | Your own OpenAI / Anthropic / Gemini / OpenRouter key | You |

`init` will ask which mode you want.

## Mobile (iPhone / Android)

1. On your computer: `paper-organizer serve --tunnel`
2. Copy the Cloudflare URL shown in the terminal
3. Open that URL on your phone → paste any paper link → done

## Web UI

```bash
paper-organizer serve          # opens http://localhost:7788
```

## Backends

| Backend | Notes |
|---------|-------|
| Zotero | Pushes metadata + PDF (linked) + structured child note. Free 300 MB quota is enough for notes + metadata. |
| EndNote | Produces a drag-import XML + PDF folder in `~/EndNote-Inbox/`. |

## Proxy deployment (team owners)

See [`proxy/README.md`](proxy/README.md) for Railway deployment instructions and virtual key generation.

## Status

- [x] CLI skeleton (init / doctor / serve / watch stubs)
- [x] Config + secret management (keyring)
- [x] LLM client (shared proxy or own key)
- [x] Web UI (mobile-friendly)
- [x] LiteLLM proxy config (Railway)
- [ ] DOI/URL/PMID resolver
- [ ] PDF downloader
- [ ] Section chunker
- [ ] LLM extraction + synthesis
- [ ] Zotero adapter
- [ ] EndNote adapter
