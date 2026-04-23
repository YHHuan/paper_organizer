"""paper-organizer CLI entry point.

Commands
--------
init    Interactive setup wizard — writes ~/.config/paper-organizer/config.toml
doctor  Health check: config, LLM reachability, Zotero API, pdf_root writable
ingest  Ingest a paper by DOI / URL / PMID  (pipeline stub)
serve   Start the FastAPI server (optional cloudflared tunnel hint)
watch   Watch a folder for new PDFs  (watch mode stub)
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table

from paper_organizer import __version__

app = typer.Typer(
    name="paper-organizer",
    help="Research paper analysis CLI with Zotero/EndNote integration.",
    add_completion=False,
)

console = Console()
err_console = Console(stderr=True, style="bold red")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ok(label: str, detail: str = "") -> None:
    msg = f"[green]OK[/green]  {label}"
    if detail:
        msg += f" [dim]({detail})[/dim]"
    console.print(msg)


def _fail(label: str, detail: str = "") -> None:
    msg = f"[red]FAIL[/red] {label}"
    if detail:
        msg += f" [dim]({detail})[/dim]"
    console.print(msg)


def _warn(label: str, detail: str = "") -> None:
    msg = f"[yellow]WARN[/yellow] {label}"
    if detail:
        msg += f" [dim]({detail})[/dim]"
    console.print(msg)


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------


@app.command()
def init() -> None:
    """Interactive setup wizard. Writes ~/.config/paper-organizer/config.toml."""
    from paper_organizer.config import (
        AppConfig,
        BackendConfig,
        BudgetConfig,
        LLMConfig,
        LLMMode,
        UserConfig,
        save_config,
        set_secret,
    )

    console.rule("[bold cyan]paper-organizer setup wizard[/bold cyan]")

    # --- LLM mode ---
    console.print("\n[bold]Step 1 — LLM mode[/bold]")
    console.print("  [cyan]shared[/cyan]  Use the paper-organizer proxy (no API key needed from you)")
    console.print("  [cyan]own[/cyan]     Use your own API key directly\n")
    mode_str = Prompt.ask("LLM mode", choices=["shared", "own"], default="shared")
    mode = LLMMode(mode_str)

    llm_cfg = LLMConfig(mode=mode)

    if mode == LLMMode.SHARED:
        token = Prompt.ask("Shared proxy token (leave blank to set later)", default="", password=True)
        if token:
            set_secret("shared_token", token)
            console.print("[green]Token saved to system keyring.[/green]")
        llm_cfg.shared_token = ""  # never write token into config file
    else:
        provider = Prompt.ask(
            "Provider",
            choices=["openai", "anthropic", "gemini", "openrouter"],
            default="openai",
        )
        api_key = Prompt.ask(f"{provider} API key", password=True)
        if api_key:
            set_secret(f"{provider}_api_key", api_key)
            console.print("[green]API key saved to system keyring.[/green]")

        fast_default = {
            "openai": "openai/gpt-4o-mini",
            "anthropic": "anthropic/claude-haiku-3-5",
            "gemini": "gemini/gemini-1.5-flash",
            "openrouter": "openrouter/google/gemini-flash-1.5",
        }.get(provider, "openai/gpt-4o-mini")

        smart_default = {
            "openai": "openai/gpt-4o",
            "anthropic": "anthropic/claude-sonnet-4-6",
            "gemini": "gemini/gemini-1.5-pro",
            "openrouter": "openrouter/anthropic/claude-sonnet-4-6",
        }.get(provider, "anthropic/claude-sonnet-4-6")

        llm_cfg.provider = provider
        llm_cfg.fast_model = Prompt.ask("Fast model", default=fast_default)
        llm_cfg.smart_model = Prompt.ask("Smart model", default=smart_default)

    # --- Backend ---
    console.print("\n[bold]Step 2 — Reference manager backend[/bold]")
    backend_str = Prompt.ask("Primary backend", choices=["zotero", "endnote", "both"], default="zotero")
    backend_cfg = BackendConfig(primary=backend_str)

    if backend_str in ("zotero", "both"):
        zot_lib_id = Prompt.ask("Zotero library ID (numeric, from zotero.org/settings/keys)", default="")
        zot_api_key = Prompt.ask("Zotero API key", password=True, default="")
        if zot_api_key:
            set_secret("zotero_api_key", zot_api_key)
            console.print("[green]Zotero API key saved to system keyring.[/green]")
        backend_cfg.zotero_library_id = zot_lib_id
        backend_cfg.zotero_library_type = Prompt.ask(
            "Library type", choices=["user", "group"], default="user"
        )
        backend_cfg.zotero_storage_mode = Prompt.ask(
            "PDF storage mode",
            choices=["linked", "copy"],
            default="linked",
        )

    pdf_root = Prompt.ask("Local PDF folder", default=str(backend_cfg.pdf_root))
    notes_root = Prompt.ask("Notes folder", default=str(backend_cfg.notes_root))
    backend_cfg.pdf_root = pdf_root
    backend_cfg.notes_root = notes_root

    # --- User prefs ---
    console.print("\n[bold]Step 3 — User preferences[/bold]")
    persona = Prompt.ask("Your clinical persona", default="clinical researcher")
    summary_lang = Prompt.ask("Summary language", default="zh-TW")
    user_cfg = UserConfig(clinical_persona=persona, summary_lang=summary_lang)

    # --- Save ---
    config = AppConfig(
        user=user_cfg,
        llm=llm_cfg,
        backend=backend_cfg,
        budget=BudgetConfig(),
    )
    save_config(config)
    config_path = Path.home() / ".config" / "paper-organizer" / "config.toml"
    console.print(f"\n[bold green]Config saved to {config_path}[/bold green]")
    console.print("Run [cyan]paper-organizer doctor[/cyan] to verify everything works.")


# ---------------------------------------------------------------------------
# doctor
# ---------------------------------------------------------------------------


@app.command()
def doctor() -> None:
    """Check config, LLM reachability, Zotero API, and pdf_root writability."""
    from paper_organizer.config import get_config, get_secret
    from paper_organizer.llm.client import chat_sync

    console.rule("[bold cyan]paper-organizer doctor[/bold cyan]")
    all_ok = True

    # 1. Config file
    config_path = Path.home() / ".config" / "paper-organizer" / "config.toml"
    if config_path.exists():
        _ok("Config file", str(config_path))
    else:
        _warn("Config file not found", f"expected {config_path} — run `paper-organizer init`")

    config = get_config()

    # 2. LLM reachability — send a tiny ping
    console.print("\n[dim]Pinging LLM...[/dim]")
    try:
        reply = chat_sync(
            [{"role": "user", "content": "Reply with the single word: pong"}],
            model="fast",
            config=config,
            max_tokens=8,
        )
        _ok("LLM reachable", f"response: {reply.strip()!r}")
    except Exception as exc:
        _fail("LLM unreachable", str(exc))
        all_ok = False

    # 3. Zotero API
    if config.backend.primary in ("zotero", "both"):
        console.print("\n[dim]Checking Zotero API...[/dim]")
        zot_key = config.backend.zotero_api_key or get_secret("zotero_api_key")
        lib_id = config.backend.zotero_library_id
        if not zot_key or not lib_id:
            _warn("Zotero", "api_key or library_id not configured")
        else:
            try:
                from pyzotero import zotero

                zot = zotero.Zotero(lib_id, config.backend.zotero_library_type, zot_key)
                # cheap call: fetch at most 1 item
                zot.top(limit=1)
                _ok("Zotero API reachable", f"library {lib_id}")
            except Exception as exc:
                _fail("Zotero API", str(exc))
                all_ok = False

    # 4. pdf_root writable
    pdf_root = Path(config.backend.pdf_root).expanduser()
    console.print(f"\n[dim]Checking pdf_root: {pdf_root}[/dim]")
    try:
        pdf_root.mkdir(parents=True, exist_ok=True)
        test_file = pdf_root / ".paper_organizer_write_test"
        test_file.write_text("ok")
        test_file.unlink()
        _ok("pdf_root writable", str(pdf_root))
    except Exception as exc:
        _fail("pdf_root not writable", str(exc))
        all_ok = False

    console.print()
    if all_ok:
        console.print("[bold green]All checks passed.[/bold green]")
    else:
        console.print("[bold red]Some checks failed — see above.[/bold red]")
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# ingest
# ---------------------------------------------------------------------------


@app.command()
def ingest(
    input: Annotated[str, typer.Argument(help="DOI, URL, or PMID to ingest")],
    backend: Annotated[
        Optional[str],
        typer.Option("--backend", help="Override backend: zotero | endnote | both"),
    ] = None,
) -> None:
    """Ingest a paper by DOI, URL, or PMID."""
    from paper_organizer.config import get_config
    from paper_organizer.pipeline.resolve import resolve
    from paper_organizer.pipeline.acquire import acquire_pdf

    config = get_config()

    with console.status(f"[cyan]Resolving {input}...[/cyan]"):
        metadata = asyncio.run(resolve(input))

    if not metadata.title:
        console.print(f"[red]Could not resolve: {input}[/red]")
        raise typer.Exit(1)

    console.print(f"[bold]{metadata.title}[/bold]")
    console.print(
        f"[dim]{', '.join(a.full_name() for a in metadata.authors[:3])} ({metadata.year})[/dim]"
    )

    pdf_root = Path(config.backend.pdf_root).expanduser()
    with console.status("[cyan]Downloading PDF...[/cyan]"):
        pdf_path = asyncio.run(acquire_pdf(metadata, pdf_root))

    if pdf_path:
        console.print(f"[green]PDF saved:[/green] {pdf_path.name}")
    else:
        console.print("[yellow]PDF not available (open access only)[/yellow]")

    # --- Extract text from PDF if we have one ---
    pdf_text = ""
    if pdf_path and pdf_path.exists():
        try:
            import fitz  # pymupdf
            doc = fitz.open(str(pdf_path))
            pdf_text = "\n".join(page.get_text() for page in doc)[:8000]
        except Exception:
            pass

    # --- LLM synthesis ---
    from paper_organizer.pipeline.synthesize import synthesize

    with console.status("[cyan]Running LLM analysis...[/cyan]"):
        analysis = asyncio.run(
            synthesize(metadata, pdf_text, config=config, lang=config.user.summary_lang)
        )

    # --- Save notes ---
    notes_root = Path(config.backend.notes_root).expanduser()
    notes_root.mkdir(parents=True, exist_ok=True)
    safe_name = metadata.first_author_year().replace(" ", "_")
    notes_path = notes_root / f"{safe_name}.md"
    notes_path.write_text(analysis.to_markdown(metadata), encoding="utf-8")
    console.print(f"[green]Notes saved:[/green] {notes_path}")

    # --- Push to Zotero ---
    active_backend = backend or config.backend.primary
    if active_backend in ("zotero", "both"):
        from paper_organizer.config import get_secret as _get_secret
        zot_key = config.backend.zotero_api_key or _get_secret("zotero_api_key")
        zot_lib = config.backend.zotero_library_id
        if zot_key and zot_lib:
            from paper_organizer.backends.zotero import push_to_zotero
            with console.status("[cyan]Pushing to Zotero...[/cyan]"):
                try:
                    item_key, created = push_to_zotero(metadata, analysis, pdf_path, config)
                    if created:
                        console.print(f"[green]Zotero:[/green] created item {item_key}")
                    else:
                        console.print(
                            f"[yellow]Zotero:[/yellow] DOI already in library ({item_key})"
                        )
                except Exception as exc:
                    console.print(f"[yellow]Zotero push failed:[/yellow] {exc}")
        else:
            console.print("[yellow]Zotero not configured — skipping[/yellow]")

    # --- Print summary ---
    console.print(f"\n[bold cyan]Clinical Analysis[/bold cyan]")
    console.print(f"[bold]One-liner:[/bold] {analysis.one_liner}")


# ---------------------------------------------------------------------------
# serve
# ---------------------------------------------------------------------------


@app.command()
def serve(
    host: Annotated[str, typer.Option("--host", help="Bind host")] = "0.0.0.0",
    port: Annotated[int, typer.Option("--port", help="Bind port")] = 7788,
    tunnel: Annotated[
        bool,
        typer.Option("--tunnel/--no-tunnel", help="Print cloudflared tunnel hint"),
    ] = False,
) -> None:
    """Start the paper-organizer FastAPI server on host:port."""
    if tunnel:
        console.print(
            "[bold yellow]Tunnel hint:[/bold yellow] install cloudflared and run:\n"
            f"  [cyan]cloudflared tunnel --url http://localhost:{port}[/cyan]\n"
        )

    console.print(f"Starting server on [cyan]http://{host}:{port}[/cyan] ...")

    import uvicorn

    try:
        # Prefer a create_app factory if it exists; fall back to bare module-level app
        from paper_organizer.server.app import create_app  # type: ignore[attr-defined]
        application = create_app()
    except (ImportError, AttributeError):
        try:
            from paper_organizer.server.app import app as application  # type: ignore[assignment]
        except ImportError:
            from fastapi import FastAPI
            application = FastAPI(title="paper-organizer", version=__version__)

            @application.get("/")
            def root():
                return {"status": "ok", "version": __version__}

            @application.get("/health")
            def health():
                return {"status": "healthy"}

    uvicorn.run(application, host=host, port=port)


# ---------------------------------------------------------------------------
# watch
# ---------------------------------------------------------------------------


@app.command()
def watch(
    folder: Annotated[str, typer.Argument(help="Folder to watch for new PDFs")],
) -> None:
    """Watch a folder for new PDFs and auto-ingest them. (Stub — not yet implemented.)"""
    watch_path = Path(folder).expanduser().resolve()
    console.print(
        f"[yellow]Watch mode not yet implemented[/yellow] for: [cyan]{watch_path}[/cyan]\n"
        "When implemented, this will use watchdog to monitor the folder and\n"
        "automatically call [cyan]ingest[/cyan] on any new PDF that appears."
    )


# ---------------------------------------------------------------------------
# version
# ---------------------------------------------------------------------------


@app.command()
def version() -> None:
    """Print the installed version."""
    console.print(f"paper-organizer [cyan]{__version__}[/cyan]")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    app()


if __name__ == "__main__":
    main()
