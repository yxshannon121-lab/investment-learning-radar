from __future__ import annotations

import re
from difflib import SequenceMatcher


TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def normalize_title(title: str) -> str:
    return " ".join(TOKEN_RE.findall(title.lower()))


def title_similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, normalize_title(left), normalize_title(right)).ratio()


def is_duplicate_title(title: str, existing_titles: list[str], threshold: float = 0.9) -> bool:
    normalized = normalize_title(title)
    if not normalized:
        return True
    return any(title_similarity(title, existing) >= threshold for existing in existing_titles)

