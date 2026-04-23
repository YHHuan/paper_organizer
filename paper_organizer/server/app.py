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
            "message": "Metadata fetched. LLM analysis coming in next update.",
        }
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
