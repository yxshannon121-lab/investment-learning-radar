from __future__ import annotations

import argparse
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from .config import load_settings
from .database import Database
from .fetch_news import fetch_and_store
from .market_data import update_due_snapshots
from .reports import analyze_due_news, run_report
from .web_dashboard import write_dashboard


def _is_due(settings, local_time: str | None, weekday: str | None) -> bool:
    now = datetime.now(ZoneInfo(settings.timezone))
    if local_time:
        hour, minute = [int(part) for part in local_time.split(":", 1)]
        if now.hour != hour or now.minute != minute:
            return False
    if weekday and now.strftime("%A").lower() != weekday.lower():
        return False
    return True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Investment Learning Radar")
    parser.add_argument(
        "command",
        choices=[
            "fetch",
            "track",
            "dashboard",
            "morning",
            "premarket",
            "weekly",
            "email-morning",
            "email-premarket",
            "email-weekly",
        ],
    )
    parser.add_argument("--only-if-local-time", help="Run only when local time matches HH:MM in TIMEZONE.")
    parser.add_argument("--only-weekday", help="Run only on a weekday name, for example Sunday.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    settings = load_settings()
    db = Database(settings)
    db.init()

    if not _is_due(settings, args.only_if_local_time, args.only_weekday):
        print(json.dumps({"skipped": True, "reason": "not due in configured timezone"}, ensure_ascii=False))
        return

    if args.command == "fetch":
        fetch_result = fetch_and_store(settings, db)
        dashboard_path = write_dashboard(settings, db)
        result = {"fetch": fetch_result, "dashboard": str(dashboard_path)}
    elif args.command == "track":
        tracked = update_due_snapshots(db)
        dashboard_path = write_dashboard(settings, db)
        result = {"tracked": tracked, "dashboard": str(dashboard_path)}
    elif args.command.startswith("email-"):
        result = run_report(args.command.removeprefix("email-"), settings, db)
        dashboard_path = write_dashboard(settings, db)
        result["dashboard"] = str(dashboard_path)
    else:
        fetch_result = fetch_and_store(settings, db)
        analyzed = analyze_due_news(settings, db)
        tracked = update_due_snapshots(db)
        dashboard_path = write_dashboard(settings, db)
        result = {
            "command": args.command,
            "fetch": fetch_result,
            "analyzed": analyzed,
            "tracked": tracked,
            "dashboard": str(dashboard_path),
            "database": str(settings.sqlite_path),
        }

    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
