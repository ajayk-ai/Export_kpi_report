"""Where a DataFrame comes from: the live Google Sheet, or a local Excel file.

Both paths hand the pipeline the same shape of data — every cell as a string,
blanks preserved — matching how gspread's ``get_all_records`` returns the sheet.
"""
from pathlib import Path

import pandas as pd

from ..clients.sheets_client import get_data_as_dataframe
from ..config import PROJECT_ROOT, settings

DEFAULT_LOCAL_FILE = PROJECT_ROOT / "data" / "test_data.xlsx"


def from_sheet() -> pd.DataFrame:
    """Live data from the configured Google Sheet."""
    return get_data_as_dataframe(settings.sheet_id, settings.worksheet_name)


def from_local(path: str | Path | None = None) -> pd.DataFrame:
    """Data from a local .xlsx (defaults to ``data/test_data.xlsx``)."""
    path = Path(path) if path else DEFAULT_LOCAL_FILE
    if not path.exists():
        raise FileNotFoundError(
            f"Local data file not found: {path}. "
            f"Run `python make_test_data.py` to create it."
        )
    return pd.read_excel(path, dtype=str).fillna("")


def load(source: str = "sheet") -> pd.DataFrame:
    """Pick a data source by name: 'sheet' (default) or 'local'."""
    if source == "local":
        return from_local()
    return from_sheet()
