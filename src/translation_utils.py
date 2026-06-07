from __future__ import annotations

import re
from html import unescape


TITLE_FALLBACK = "暂时无法生成中文标题，请点击原文查看"
TRANSLATION_FALLBACK = "暂时无法生成中文翻译，请点击原文查看"


TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    value = TAG_RE.sub(" ", value)
    value = unescape(value)
    return SPACE_RE.sub(" ", value).strip()


def split_paragraphs(value: str | None, max_paragraphs: int = 80) -> list[str]:
    if not value:
        return []
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    parts = [clean_text(part) for part in re.split(r"\n{2,}|(?<=。)\s+|(?<=\.)\s+", value)]
    return [part for part in parts if len(part) >= 12][:max_paragraphs]


def is_mostly_chinese(value: str) -> bool:
    if not value:
        return False
    cjk = len(CJK_RE.findall(value))
    letters = len(re.findall(r"[A-Za-z]", value))
    return cjk > 0 and cjk >= letters


def _translator():
    try:
        from deep_translator import GoogleTranslator

        return GoogleTranslator(source="auto", target="zh-CN")
    except Exception:
        return None


def translate_text(value: str, fallback: str) -> str:
    value = clean_text(value)
    if not value:
        return fallback
    if is_mostly_chinese(value):
        return value
    translator = _translator()
    if translator is None:
        return fallback
    try:
        translated = translator.translate(value[:4500])
    except Exception:
        return fallback
    translated = clean_text(translated)
    return translated or fallback


def translate_title(title: str) -> str:
    return translate_text(title, TITLE_FALLBACK)


def translate_paragraphs(paragraphs: list[str], max_chars: int = 12000) -> list[str]:
    translated: list[str] = []
    used = 0
    translator = _translator()
    for paragraph in paragraphs:
        paragraph = clean_text(paragraph)
        if not paragraph:
            continue
        if used + len(paragraph) > max_chars:
            break
        used += len(paragraph)
        if is_mostly_chinese(paragraph):
            translated.append(paragraph)
            continue
        if translator is None:
            return []
        try:
            text = clean_text(translator.translate(paragraph[:4500]))
        except Exception:
            return []
        if text:
            translated.append(text)
    return translated

