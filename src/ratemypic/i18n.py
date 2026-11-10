# src/ratemypic/i18n.py
"""Simple i18n helper for the RateMyPic bot.
Provides translation lookup with a fallback to English.
"""
import json
from pathlib import Path
from typing import Dict

BASE_DIR = Path(__file__).parent / "i18n"

# language code → human readable name (used for validation / UI)
SUPPORTED_LANGUAGES = {
    "en": "English",
    "ru": "Russian",
    "es": "Spanish",
    "pt": "Portuguese",
    "id": "Indonesian",
}

# Cache of loaded translation dictionaries
_translations: Dict[str, Dict[str, str]] = {}


def _load(lang: str) -> Dict[str, str]:
    """Load a language JSON file; return empty dict if missing."""
    if lang in _translations:
        return _translations[lang]
    path = BASE_DIR / f"{lang}.json"
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {}
    _translations[lang] = data
    return data


def t(key: str, lang: str = "en", **fmt) -> str:
    """Return a translated string.

    * ``key`` – dot‑separated identifier, e.g. ``start.welcome``.
    * ``lang`` – language code; if unknown, falls back to English.
    * ``fmt`` – optional ``str.format`` arguments for interpolation.
    """
    if lang not in SUPPORTED_LANGUAGES:
        lang = "en"
    # Try requested language, then English fallback
    translation = _load(lang).get(key) or _load("en").get(key, f"[{key}]")
    if fmt:
        try:
            translation = translation.format(**fmt)
        except Exception:
            pass  # keep raw translation on format error
    return translation
