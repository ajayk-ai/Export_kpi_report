"""Fetch the report's source DataFrame from the live Google Sheet."""
import pandas as pd

from ..clients.sheets_client import get_data_as_dataframe
from ..config import settings


def load() -> pd.DataFrame:
    """Live data from the configured Google Sheet."""
    return get_data_as_dataframe(settings.sheet_id, settings.worksheet_name)
