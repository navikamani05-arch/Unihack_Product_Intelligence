"""Evidence-preserving text normalization helpers used by catalog and delivery output."""
from __future__ import annotations

import re
from typing import Any, Optional


_DISPLAY_SUFFIX_RE = re.compile(
    r"(?:\s*[-|:/]\s*|\s+)(?:for\s+)?display(?:\s+only)?\s*$",
    re.IGNORECASE,
)
_DEMO_SUFFIX_RE = re.compile(r"(?:\s*[-|:/]\s*|\s+)(?:demo|sample)\s*$", re.IGNORECASE)
_TRAILING_FINISH_RE = re.compile(r"\s+(?:ss|stainless\s+steel)\s*$", re.IGNORECASE)


def normalize_product_name(value: Any, identifier: Optional[Any] = None) -> Optional[str]:
    """Return a short, source-derived commerce title without changing the raw value.

    The helper only removes an identifier when it is an exact leading token and removes
    explicit merchandising suffixes such as ``Display Only``. It does not infer a
    category or invent words. The original description remains available to callers.
    """
    if value is None:
        return None
    text = " ".join(str(value).strip().split())
    if not text:
        return None

    if identifier:
        identifier_text = " ".join(str(identifier).strip().split())
        if identifier_text and text.casefold().startswith(identifier_text.casefold()):
            remainder = text[len(identifier_text):]
            if not remainder or remainder[0].isspace() or remainder[0] in "-:|/":
                text = remainder.lstrip(" -:|/")

    previous = None
    while text and text != previous:
        previous = text
        text = _DISPLAY_SUFFIX_RE.sub("", text).strip(" -:|/")
        text = _DEMO_SUFFIX_RE.sub("", text).strip(" -:|/")
        # A terminal SS/stainless-steel finish marker is a merchandising qualifier,
        # not a replacement for the raw description or a fabricated attribute.
        text = _TRAILING_FINISH_RE.sub("", text).strip(" -:|/")

    return " ".join(text.split()) or None


__all__ = ["normalize_product_name"]
