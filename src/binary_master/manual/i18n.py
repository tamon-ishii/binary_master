"""Language resolution and internationalization utilities for manual generator."""

from __future__ import annotations

import locale
import os
from typing import Literal, Optional


def resolve_language(lang: Optional[str] = "auto") -> Literal["en", "ja"]:
    """Resolve language choice ('auto', 'en', 'ja') to 'en' or 'ja' based on system locale.

    If lang is 'auto' (or None/empty), it checks environment variables (LC_ALL, LC_MESSAGES, LANG)
    and Python's locale.getlocale(). If the locale indicates Japanese ('ja' or 'japanese'),
    it returns 'ja', otherwise 'en'.
    """
    if not lang or lang == "auto":
        env_lang = (
            os.environ.get("LC_ALL")
            or os.environ.get("LC_MESSAGES")
            or os.environ.get("LANG")
            or ""
        )
        if not env_lang:
            try:
                loc = locale.getlocale()[0] or ""
                env_lang = loc
            except Exception:
                pass
        if env_lang.lower().startswith("ja") or "japanese" in env_lang.lower():
            return "ja"
        return "en"

    clean = lang.lower().strip()
    if clean.startswith("ja") or clean.startswith("jp"):
        return "ja"
    return "en"


