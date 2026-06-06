from __future__ import annotations

from pathlib import Path

import requests

from .config import ROOT_DIR, Settings


class EmailSendError(RuntimeError):
    pass


def _write_preview(subject: str, html: str, text: str) -> Path:
    output_dir = ROOT_DIR / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_subject = "".join(ch if ch.isalnum() else "_" for ch in subject)[:80].strip("_")
    path = output_dir / f"{safe_subject or 'report'}.html"
    path.write_text(html + "\n\n<!-- TEXT VERSION\n" + text + "\n-->\n", encoding="utf-8")
    return path


def send_email(settings: Settings, subject: str, html: str, text: str) -> dict[str, str | bool]:
    if settings.email_dry_run:
        path = _write_preview(subject, html, text)
        return {"sent": False, "dry_run": True, "preview_path": str(path)}

    if not settings.resend_api_key:
        raise EmailSendError("RESEND_API_KEY is required when EMAIL_DRY_RUN=false.")
    if not settings.sender_email:
        raise EmailSendError("SENDER_EMAIL is required when EMAIL_DRY_RUN=false.")
    if not settings.report_emails:
        raise EmailSendError("REPORT_EMAILS must contain at least one recipient.")

    response = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {settings.resend_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "from": settings.sender_email,
            "to": settings.report_emails,
            "subject": subject,
            "html": html,
            "text": text,
        },
        timeout=30,
    )
    if response.status_code >= 300:
        raise EmailSendError(f"Resend API error {response.status_code}: {response.text[:500]}")
    return {"sent": True, "dry_run": False, "provider_response": response.text}

