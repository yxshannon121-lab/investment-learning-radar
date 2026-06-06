from src.config import load_settings


def test_report_emails_are_loaded_from_env(monkeypatch):
    monkeypatch.setenv("REPORT_EMAILS", "a@example.com, b@example.com")
    settings = load_settings()
    assert settings.report_emails == ["a@example.com", "b@example.com"]

