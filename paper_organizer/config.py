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
        env_prefix="PAPER_ORGANIZER_",
        env_nested_delimiter="__",
    )


def get_config() -> AppConfig:
    """Load config from TOML file, then overlay env vars."""
    import tomllib

    data: dict = {}
    if _CONFIG_FILE.exists():
        try:
            data = tomllib.loads(_CONFIG_FILE.read_text())
        except Exception:
            pass
    return AppConfig(**data)


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

    # model_dump(mode="json") converts enums to their .value strings automatically
    data = config.model_dump(mode="json")
    for section, values in data.items():
        if isinstance(values, dict):
            _write_section(section, values)
        else:
            lines.append(f'{section} = "{values}"' if isinstance(values, str) else f"{section} = {values}")

    _CONFIG_FILE.write_text("\n".join(lines).lstrip() + "\n", encoding="utf-8")


def get_secret(key: str) -> str:
    """Retrieve a secret from keyring, falling back to file then env var."""
    try:
        value = keyring.get_password(_KEYRING_SERVICE, key)
        if value:
            return value
    except Exception:
        pass
    # fallback 1: secrets file
    value = _secrets_file_get(key)
    if value:
        return value
    # fallback 2: env var
    return os.environ.get(f"PAPER_ORGANIZER_{key.upper()}", "")


def set_secret(key: str, value: str) -> None:
    """Store a secret in system keyring, falling back to local secrets file."""
    try:
        keyring.set_password(_KEYRING_SERVICE, key, value)
        return
    except Exception:
        pass
    _secrets_file_set(key, value)


_SECRETS_FILE = _CONFIG_DIR / "secrets.toml"


def _secrets_file_get(key: str) -> str:
    if not _SECRETS_FILE.exists():
        return ""
    try:
        import tomllib
        data = tomllib.loads(_SECRETS_FILE.read_text())
        return data.get(key, "")
    except Exception:
        return ""


def _secrets_file_set(key: str, value: str) -> None:
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    existing: dict = {}
    if _SECRETS_FILE.exists():
        try:
            import tomllib
            existing = tomllib.loads(_SECRETS_FILE.read_text())
        except Exception:
            pass
    existing[key] = value
    lines = [f'{k} = "{v}"' for k, v in existing.items()]
    _SECRETS_FILE.write_text("\n".join(lines) + "\n")
    _SECRETS_FILE.chmod(0o600)
