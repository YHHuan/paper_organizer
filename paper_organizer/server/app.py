from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import pathlib

app = FastAPI(title="Paper Organizer")

_HERE = pathlib.Path(__file__).parent
templates = Jinja2Templates(directory=str(_HERE / "templates"))


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve the main input form."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/ingest")
async def ingest(
    request: Request,
    input_text: str = Form(""),
    backend: str = Form("zotero"),
):
    """Accept paper submission. Currently returns a stub response."""
    input_text = input_text.strip()
    if not input_text:
        return JSONResponse(
            {"status": "error", "message": "No input provided."},
            status_code=422,
        )

    # TODO: call pipeline
    return JSONResponse({
        "status": "queued",
        "input": input_text,
        "backend": backend,
        "message": "Pipeline not yet implemented. Received your submission.",
    })


@app.get("/health")
async def health():
    return {"status": "ok"}
