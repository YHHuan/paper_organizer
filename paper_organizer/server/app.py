from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import pathlib

app = FastAPI(title="Paper Organizer")

_HERE = pathlib.Path(__file__).parent
templates = Jinja2Templates(directory=str(_HERE / "templates"))


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve the main UI."""
    return templates.TemplateResponse(request, "index.html")


@app.post("/ingest")
async def ingest(
    request: Request,
    input_text: str = Form(""),
    backend: str = Form("zotero"),
):
    """Accept a paper reference and attempt to resolve metadata.

    Falls back to a stub response if the pipeline is not yet available.
    """
    input_text = input_text.strip()
    if not input_text:
        return JSONResponse(
            {"status": "error", "message": "Input is required"},
            status_code=422,
        )

    # Try real pipeline, fall back to stub
    try:
        from paper_organizer.pipeline.resolve import resolve  # type: ignore[import]
        metadata = await resolve(input_text)
        abstract = metadata.abstract or ""
        result = {
            "status": "success",
            "title": metadata.title or input_text,
            "authors": [a.full_name() for a in metadata.authors[:5]],
            "journal": metadata.journal,
            "year": metadata.year,
            "doi": metadata.doi,
            "abstract": abstract[:400] + "..." if len(abstract) > 400 else abstract,
            "pdf_available": bool(metadata.pdf_url),
            "backend": backend,
            "message": "Metadata fetched.",
        }

        # Run LLM synthesis; failures are non-fatal
        analysis = None
        try:
            from paper_organizer.pipeline.synthesize import synthesize
            from paper_organizer.config import get_config, get_secret
            cfg = get_config()
            analysis = await synthesize(metadata, lang=cfg.user.summary_lang)
            result.update({"sections": analysis.to_dict()})
        except Exception:
            pass

        # Export to EndNote; failures are non-fatal
        if analysis is not None and backend in ("endnote", "both"):
            try:
                from paper_organizer.backends.endnote import export_to_endnote
                xml_path = export_to_endnote(metadata, analysis, None, cfg)
                result["endnote_xml"] = str(xml_path)
            except Exception:
                pass

        # Push to Zotero; failures are non-fatal
        if analysis is not None and backend in ("zotero", "both"):
            try:
                import asyncio as _asyncio
                from paper_organizer.backends.zotero import push_to_zotero
                zot_key = cfg.backend.zotero_api_key or get_secret("zotero_api_key")
                if cfg.backend.zotero_library_id and zot_key:
                    item_key, created = await _asyncio.to_thread(
                        push_to_zotero, metadata, analysis, None, cfg
                    )
                    result["zotero_key"] = item_key
                    result["zotero_created"] = created
            except Exception:
                pass

    except Exception as e:
        result = {
            "status": "partial",
            "title": input_text,
            "authors": [],
            "journal": "",
            "year": None,
            "doi": "",
            "abstract": "",
            "pdf_available": False,
            "backend": backend,
            "message": f"Could not resolve metadata: {e}. Pipeline will be ready soon.",
        }

    return JSONResponse(result)


@app.get("/health")
async def health():
    return {"status": "ok"}
