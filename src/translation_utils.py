from __future__ import annotations

import re
from html import unescape
from html.parser import HTMLParser


TITLE_FALLBACK = "暂时无法生成中文标题，请点击原文查看"
TRANSLATION_FALLBACK = "暂时无法生成中文翻译，请点击原文查看"


TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")
PAYWALL_TERMS = (
    "subscribe to unlock",
    "subscribe",
    "sign in",
    "register",
    "trial",
    "standard digital",
    "premium digital",
    "ft weekend",
    "terms and conditions",
    "explore our subscriptions",
    "unlimited access",
    "cancel anytime",
    "already a subscriber",
    "paywall",
    "订阅",
    "解锁",
    "试用",
    "标准数字版",
    "高级数字版",
    "每月",
    "取消",
    "优惠",
    "适用条款",
    "完整访问",
)


class ReadableHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript"}:
            self.skip_depth += 1
            return
        if tag == "img":
            attrs_dict = dict(attrs)
            alt = attrs_dict.get("alt")
            if alt:
                self.parts.append(f" {alt} ")
        if tag in {"p", "br", "div", "li", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript"} and self.skip_depth:
            self.skip_depth -= 1
        if tag.lower() in {"p", "div", "li", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        if data:
            self.parts.append(data)

    def text(self) -> str:
        return "".join(self.parts)


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    if "<" in value and ">" in value:
        parser = ReadableHTMLParser()
        try:
            parser.feed(value)
            value = parser.text()
        except Exception:
            value = TAG_RE.sub(" ", value)
    else:
        value = TAG_RE.sub(" ", value)
    value = unescape(value)
    return SPACE_RE.sub(" ", value).strip()


def is_paywall_text(value: str | None) -> bool:
    text = clean_text(value).lower()
    if not text:
        return False
    matches = sum(1 for term in PAYWALL_TERMS if term.lower() in text)
    return matches >= 2 or any(term in text for term in ("subscribe to unlock", "explore our subscriptions", "already a subscriber"))


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
    cleaned = clean_text(title)
    return translate_text(cleaned, cleaned or TITLE_FALLBACK)


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
