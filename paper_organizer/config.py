"""Configuration models and helpers for paper-organizer."""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path

import keyring
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

_CONFIG_DIR = Path.home() / ".config" / "paper-organizer"
_CONFIG_FILE = _CONFIG_DIR / "config.toml"

_KEYRING_SERVICE = "paper-organizer"


class LLMMode(str, Enum):
    SHARED = "shared"
    OWN = "own"


class LLMConfig(BaseModel):
    mode: LLMMode = LLMMode.SHARED
    # shared mode
    shared_endpoint: str = "https://proxy.paper-organizer.dev"
    shared_token: str = ""
    # own mode
    provider: str = "openai"  # openai | anthropic | gemini | openrouter
    api_key: str = ""
    fast_model: str = "openai/gpt-4o-mini"
    smart_model: str = "anthropic/claude-sonnet-4-6"


class BackendConfig(BaseModel):
    primary: str = "zotero"  # zotero | endnote | both
    zotero_library_id: str = ""
    zotero_library_type: str = "user"
    zotero_api_key: str = ""
    zotero_storage_mode: str = "linked"  # linked | copy
    pdf_root: str = "~/lumen-pdfs"
    notes_root: str = "~/lumen-notes"
    endnote_inbox: str = "~/EndNote-Inbox"


class UserConfig(BaseModel):
    clinical_persona: str = "clinical researcher"
    summary_lang: str = "zh-TW"
    research_threads: list[str] = []


class BudgetConfig(BaseModel):
    daily_usd: float = 3.0
    per_paper_cap_usd: float = 0.15
    monthly_usd: float = 50.0


class AppConfig(BaseSettings):
    user: UserConfig = UserConfig()
    llm: LLMConfig = LLMConfig()
    backend: BackendConfig = BackendConfig()
    budget: BudgetConfig = BudgetConfig()

    model_config = SettingsConfigDict(
        toml_file=str(_CONFIG_FILE),
        env_prefix="PAPER_ORGANIZER_",
        env_nested_delimiter="__",
    )


def get_config() -> AppConfig:
    """Load and return the application config.

    Reads from ~/.config/paper-organizer/config.toml when it exists,
    falls back to all-defaults otherwise.
    """
    if _CONFIG_FILE.exists():
        return AppConfig()  # pydantic-settings picks up the toml_file automatically
    return AppConfig()


def save_config(config: AppConfig) -> None:
    """Persist config to ~/.config/paper-organizer/config.toml using tomllib format."""
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    # Build a plain dict and write as TOML manually (tomllib is read-only; use inline write)
    lines: list[str] = []

    def _write_section(prefix: str, data: dict) -> None:
        scalars: dict = {}
        subsections: dict = {}
        for k, v in data.items():
            if isinstance(v, dict):
                subsections[k] = v
            else:
                scalars[k] = v
        if scalars:
            lines.append(f"\n[{prefix}]")
            for k, v in scalars.items():
                if isinstance(v, str):
                    lines.append(f'{k} = "{v}"')
                elif isinstance(v, list):
                    items = ", ".join(f'"{i}"' for i in v)
                    lines.append(f"{k} = [{items}]")
                else:
                    lines.append(f"{k} = {v}")
        for sub_key, sub_val in subsections.items():
            _write_section(f"{prefix}.{sub_key}", sub_val)

    data = config.model_dump()
    for section, values in data.items():
        if isinstance(values, dict):
            _write_section(section, values)
        else:
            lines.append(f'{section} = "{values}"' if isinstance(values, str) else f"{section} = {values}")

    _CONFIG_FILE.write_text("\n".join(lines).lstrip() + "\n", encoding="utf-8")


def get_secret(key: str) -> str:
    """Retrieve a secret from keyring, falling back to environment variable.

    Keyring service name: "paper-organizer"
    Falls back to env var PAPER_ORGANIZER_<KEY> (uppercased).
    Returns empty string if not found.
    """
    value = keyring.get_password(_KEYRING_SERVICE, key)
    if value:
        return value
    env_key = f"PAPER_ORGANIZER_{key.upper()}"
    return os.environ.get(env_key, "")


def set_secret(key: str, value: str) -> None:
    """Store a secret in the system keyring."""
    keyring.set_password(_KEYRING_SERVICE, key, value)
