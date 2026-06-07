from __future__ import annotations

from .translation_utils import clean_text, split_paragraphs


USER_AGENT = "investment-learning-radar/0.2 (+learning project)"


def best_available_text(row, timeout: int = 15) -> tuple[str, str]:
    raw_content = clean_text(row["raw_content"] or "")
    raw_summary = clean_text(row["raw_summary"] or "")
    if len(raw_content) >= 400:
        return raw_content, "rss_content"
    if raw_summary and len(raw_summary) >= 120:
        return raw_summary, "rss_summary"

    extracted = extract_from_url(row["url"], timeout=timeout)
    if extracted:
        return extracted, "article_page"
    if raw_content:
        return raw_content, "rss_content"
    if raw_summary:
        return raw_summary, "rss_summary"
    return "", "none"


def extract_from_url(url: str, timeout: int = 15) -> str:
    html = ""
    try:
        downloaded = _trafilatura_fetch(url)
        if downloaded:
            extracted = _trafilatura_extract(downloaded)
            if extracted and len(extracted) >= 200:
                return extracted
    except Exception:
        pass

    try:
        import requests

        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
        response.raise_for_status()
        html = response.text
    except Exception:
        return ""

    try:
        extracted = _trafilatura_extract(html)
        if extracted and len(extracted) >= 200:
            return extracted
    except Exception:
        pass
    return _simple_html_extract(html)


def _trafilatura_fetch(url: str) -> str:
    try:
        import trafilatura

        return trafilatura.fetch_url(url) or ""
    except Exception:
        return ""


def _trafilatura_extract(html: str) -> str:
    try:
        import trafilatura

        return clean_text(trafilatura.extract(html, include_comments=False, include_tables=False) or "")
    except Exception:
        return ""


def _simple_html_extract(html: str) -> str:
    paragraphs = split_paragraphs(html, max_paragraphs=60)
    text = "\n\n".join(paragraphs)
    return text if len(text) >= 200 else ""
