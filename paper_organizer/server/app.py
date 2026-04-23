from __future__ import annotations

import asyncio as _asyncio
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

app = FastAPI(title="Paper Organizer")

_HERE = Path(__file__).parent
templates = Jinja2Templates(directory=str(_HERE / "templates"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _run_pipeline(
    paper_id: str,
    backend: str,
    pdf_text: str = "",
    pdf_path: Path | None = None,
) -> dict:
    """Resolve → synthesize → push to backends. Returns JSON-ready dict."""
    from paper_organizer.config import get_config, get_secret
    from paper_organizer.pipeline.resolve import resolve

    metadata = await resolve(paper_id)
    abstract = metadata.abstract or ""
    result: dict = {
        "status": "success",
        "title": metadata.title or paper_id,
        "authors": [a.full_name() for a in metadata.authors[:5]],
        "journal": metadata.journal,
        "year": metadata.year,
        "doi": metadata.doi,
        "abstract": abstract[:400] + "..." if len(abstract) > 400 else abstract,
        "pdf_available": bool(metadata.pdf_url),
        "backend": backend,
        "message": "Metadata fetched.",
    }

    cfg = get_config()

    # LLM synthesis
    analysis = None
    try:
        from paper_organizer.pipeline.synthesize import synthesize
        analysis = await synthesize(metadata, pdf_text, config=cfg, lang=cfg.user.summary_lang)
        result["sections"] = analysis.to_dict()
    except Exception:
        pass

    if analysis is not None:
        # EndNote
        if backend in ("endnote", "both"):
            try:
                from paper_organizer.backends.endnote import export_to_endnote
                xml_path = export_to_endnote(metadata, analysis, pdf_path, cfg)
                result["endnote_xml"] = str(xml_path)
            except Exception:
                pass

        # Zotero
        if backend in ("zotero", "both"):
            try:
                from paper_organizer.backends.zotero import push_to_zotero
                zot_key = cfg.backend.zotero_api_key or get_secret("zotero_api_key")
                if cfg.backend.zotero_library_id and zot_key:
                    item_key, created = await _asyncio.to_thread(
                        push_to_zotero, metadata, analysis, pdf_path, cfg
                    )
                    result["zotero_key"] = item_key
                    result["zotero_created"] = created
            except Exception:
                pass

    return result


# ---------------------------------------------------------------------------
# Main UI
# ---------------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


# ---------------------------------------------------------------------------
# Ingest (DOI / URL / PMID)
# ---------------------------------------------------------------------------


@app.post("/ingest")
async def ingest(
    request: Request,
    input_text: str = Form(""),
    backend: str = Form("zotero"),
):
    input_text = input_text.strip()
    if not input_text:
        return JSONResponse({"status": "error", "message": "Input is required"}, status_code=422)

    try:
        result = await _run_pipeline(input_text, backend)
    except Exception as e:
        result = {
            "status": "partial",
            "title": input_text,
            "authors": [], "journal": "", "year": None,
            "doi": "", "abstract": "", "pdf_available": False,
            "backend": backend,
            "message": f"Could not resolve metadata: {e}",
        }

    return JSONResponse(result)


# ---------------------------------------------------------------------------
# Upload PDF (Plan 11)
# ---------------------------------------------------------------------------


@app.post("/upload-pdf")
async def upload_pdf(
    file: UploadFile = File(...),
    backend: str = Form("zotero"),
):
    from paper_organizer.cli import _extract_watch_identifier
    from paper_organizer.config import get_config

    if not (file.filename or "").lower().endswith(".pdf"):
        return JSONResponse(
            {"status": "error", "message": "Only PDF files are accepted"}, status_code=422
        )

    content = await file.read()
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        pdf_text_short = ""
        pdf_text_full = ""
        try:
            import fitz
            doc = fitz.open(str(tmp_path))
            pdf_text_short = "\n".join(doc[i].get_text() for i in range(min(2, len(doc))))
            pdf_text_full = "\n".join(page.get_text() for page in doc)[:8000]
        except Exception:
            pass

        paper_id = _extract_watch_identifier(pdf_text_short)
        if not paper_id:
            return JSONResponse({
                "status": "error",
                "message": "No DOI or PMID found in the first two pages. Try ingesting by DOI instead.",
            }, status_code=422)

        # Copy PDF to pdf_root
        cfg = get_config()
        pdf_root = Path(cfg.backend.pdf_root).expanduser()
        pdf_root.mkdir(parents=True, exist_ok=True)
        import shutil
        dest_pdf = pdf_root / (file.filename or tmp_path.name)
        if not dest_pdf.exists():
            shutil.copy2(tmp_path, dest_pdf)

        result = await _run_pipeline(paper_id, backend, pdf_text_full, dest_pdf)
        result["source"] = "pdf_upload"
        result["detected_id"] = paper_id
        result["pdf_saved_path"] = str(dest_pdf)
        result["message"] = f"PDF analysed · detected ID: {paper_id}"

    except Exception as e:
        result = {
            "status": "error",
            "message": f"PDF processing failed: {e}",
        }
    finally:
        tmp_path.unlink(missing_ok=True)

    return JSONResponse(result)


# ---------------------------------------------------------------------------
# Settings (Plan 10)
# ---------------------------------------------------------------------------


@app.get("/settings")
async def get_settings():
    from paper_organizer.config import get_config, get_secret
    from paper_organizer.pipeline.contact import contact_email

    cfg = get_config()
    has_shared_token = bool(cfg.llm.shared_token or get_secret("shared_token"))
    has_api_key = bool(cfg.llm.api_key or get_secret(f"{cfg.llm.provider}_api_key"))
    has_zotero_key = bool(cfg.backend.zotero_api_key or get_secret("zotero_api_key"))

    llm_ok = (cfg.llm.mode == "shared" and has_shared_token) or \
             (cfg.llm.mode == "own" and has_api_key)

    return JSONResponse({
        "llm_mode": cfg.llm.mode,
        "shared_endpoint": cfg.llm.shared_endpoint,
        "has_shared_token": has_shared_token,
        "provider": cfg.llm.provider,
        "has_provider_api_key": has_api_key,
        "fast_model": cfg.llm.fast_model,
        "smart_model": cfg.llm.smart_model,
        "zotero_library_id": cfg.backend.zotero_library_id,
        "zotero_library_type": cfg.backend.zotero_library_type,
        "has_zotero_api_key": has_zotero_key,
        "primary_backend": cfg.backend.primary,
        "summary_lang": cfg.user.summary_lang,
        "unpaywall_email": contact_email(),
        "is_configured": llm_ok,
    })


@app.post("/settings")
async def save_settings(request: Request):
    from paper_organizer.config import get_config, save_config, set_secret, LLMMode

    data = await request.json()
    cfg = get_config()

    mode = data.get("llm_mode", "").strip()
    if mode in ("shared", "own"):
        cfg.llm.mode = LLMMode(mode)

    if cfg.llm.mode == LLMMode.SHARED:
        ep = data.get("shared_endpoint", "").strip()
        if ep:
            cfg.llm.shared_endpoint = ep
        tok = data.get("shared_token", "").strip()
        if tok:
            set_secret("shared_token", tok)
    else:
        prov = data.get("provider", "").strip()
        if prov in ("openai", "anthropic", "gemini", "openrouter"):
            cfg.llm.provider = prov
        key = data.get("api_key", "").strip()
        if key:
            set_secret(f"{cfg.llm.provider}_api_key", key)
        if data.get("fast_model", "").strip():
            cfg.llm.fast_model = data["fast_model"].strip()
        if data.get("smart_model", "").strip():
            cfg.llm.smart_model = data["smart_model"].strip()

    if data.get("zotero_library_id", "").strip():
        cfg.backend.zotero_library_id = data["zotero_library_id"].strip()
    if data.get("zotero_library_type", "").strip() in ("user", "group"):
        cfg.backend.zotero_library_type = data["zotero_library_type"].strip()
    zot_key = data.get("zotero_api_key", "").strip()
    if zot_key:
        set_secret("zotero_api_key", zot_key)

    if data.get("primary_backend", "").strip() in ("zotero", "endnote", "both"):
        cfg.backend.primary = data["primary_backend"].strip()
    if data.get("summary_lang", "").strip():
        cfg.user.summary_lang = data["summary_lang"].strip()

    email = data.get("unpaywall_email", "").strip()
    if email:
        set_secret("unpaywall_email", email)
        import os
        os.environ["PAPER_ORGANIZER_UNPAYWALL_EMAIL"] = email
        try:
            from paper_organizer.pipeline.contact import contact_email
            contact_email.cache_clear()
        except Exception:
            pass

    save_config(cfg)
    return JSONResponse({"status": "ok"})


@app.post("/settings/test")
async def test_settings():
    results: dict = {}

    try:
        from paper_organizer.llm.client import chat
        from paper_organizer.config import get_config
        cfg = get_config()
        reply = await chat(
            [{"role": "user", "content": "Reply with the single word: pong"}],
            model="fast", config=cfg, max_tokens=8,
        )
        results["llm"] = {"ok": True, "detail": reply.strip()}
    except Exception as e:
        results["llm"] = {"ok": False, "detail": str(e)[:120]}

    try:
        from paper_organizer.config import get_config, get_secret
        cfg = get_config()
        zot_key = cfg.backend.zotero_api_key or get_secret("zotero_api_key")
        if cfg.backend.zotero_library_id and zot_key:
            from pyzotero import zotero as pyzotero
            def _zot_ping():
                pyzotero.Zotero(
                    cfg.backend.zotero_library_id,
                    cfg.backend.zotero_library_type,
                    zot_key,
                ).top(limit=1)
            await _asyncio.to_thread(_zot_ping)
            results["zotero"] = {"ok": True, "detail": f"library {cfg.backend.zotero_library_id}"}
        else:
            results["zotero"] = {"ok": None, "detail": "not configured"}
    except Exception as e:
        results["zotero"] = {"ok": False, "detail": str(e)[:120]}

    return JSONResponse(results)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@app.get("/health")
async def health():
    return {"status": "ok"}
