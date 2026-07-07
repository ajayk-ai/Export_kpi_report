"""Entry point. Run from the project root: `uv run python main.py [--send]`."""
import argparse

from src.config import settings
from src.pipeline import run


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute SCM KPIs from Google Sheets.")
    parser.add_argument(
        "--send", action="store_true", help="Email the summary after computing it."
    )
    args = parser.parse_args()

    summary = run(send=args.send)
    print(summary)
    if args.send:
        print(f"\nEmailed summary to {settings.email_recipient}")


if __name__ == "__main__":
    main()
