"""Entry point. Run from the project root: `uv run python main.py [--send]`."""
import argparse

from app.config import settings
from app.core.pipeline import run


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute SCM KPIs from Google Sheets.")
    parser.add_argument(
        "--send", action="store_true", help="Email the summary after computing it."
    )
    parser.add_argument(
        "--month", default=None,
        help="Breakup month: full name, abbreviation, or number (e.g. July, Jul, 7). "
        "Defaults to REPORT_MONTH from .env, then the latest month in the data.",
    )
    parser.add_argument(
        "--year", type=int, default=None,
        help="Reporting year (e.g. 2027). Defaults to REPORT_YEAR from .env, "
        "then the latest year in the data.",
    )
    args = parser.parse_args()

    summary = run(send=args.send, month=args.month, year=args.year)
    print(summary)
    if args.send:
        print(f"\nEmailed summary to {settings.email_recipient}")


if __name__ == "__main__":
    main()
