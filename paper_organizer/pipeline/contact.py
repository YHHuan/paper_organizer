"""Contact identity helpers for polite scholarly API requests."""
from __future__ import annotations

import os
import re
import subprocess
from functools import lru_cache

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _valid_email(value: str) -> str:
    value = value.strip()
    return value if _EMAIL_RE.match(value) else ""


@lru_cache(maxsize=1)
def contact_email() -> str:
    """Return the user's contact email for Crossref/Unpaywall requests."""
    for key in ("PAPER_ORGANIZER_UNPAYWALL_EMAIL", "PAPER_ORGANIZER_CONTACT_EMAIL"):
        value = _valid_email(os.environ.get(key, ""))
        if value:
            return value

    # Fall back to secret store (set via web settings panel)
    try:
        from paper_organizer.config import get_secret
        value = _valid_email(get_secret("unpaywall_email") or "")
        if value:
            return value
    except Exception:
        pass

    for args in (
        ("git", "config", "user.email"),
        ("git", "config", "--global", "user.email"),
    ):
        try:
            result = subprocess.run(
                args,
                check=False,
                capture_output=True,
                text=True,
                timeout=2,
            )
        except Exception:
            continue
        value = _valid_email(result.stdout)
        if value:
            return value

    return ""


def user_agent() -> str:
    email = contact_email()
    contact = f"mailto:{email}" if email else "no-contact-email"
    return f"paper-organizer/0.1 ({contact})"
