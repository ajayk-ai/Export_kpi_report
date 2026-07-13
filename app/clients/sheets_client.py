"""Read data from Google Sheets using a service account (optionally delegated)."""
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials

from ..config import settings

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def _get_credentials() -> Credentials:
    creds = Credentials.from_service_account_file(
        settings.service_account_file, scopes=SCOPES
    )
    # Impersonate a Workspace user via domain-wide delegation, so access is
    # granted through that user rather than the service account itself.
    if settings.delegated_user:
        creds = creds.with_subject(settings.delegated_user)
    return creds


def get_data_as_dataframe(sheet_id: str, worksheet_name: str) -> pd.DataFrame:
    client = gspread.authorize(_get_credentials())
    worksheet = client.open_by_key(sheet_id).worksheet(worksheet_name)
    return pd.DataFrame(worksheet.get_all_records())


def overwrite_worksheet(
    sheet_id: str, worksheet_name: str, df: pd.DataFrame
) -> int:
    """Replace ALL contents of a worksheet with ``df`` (header + rows).

    Destructive: the sheet is cleared first. Every cell is written as raw text
    (``raw=True``) so day-first ``DD-MM-YYYY`` date strings survive intact
    instead of being re-parsed by Sheets. Returns the number of data rows
    written.
    """
    client = gspread.authorize(_get_credentials())
    worksheet = client.open_by_key(sheet_id).worksheet(worksheet_name)

    # Everything as strings: dates stay 'DD-MM-YYYY', blanks stay empty.
    frame = df.astype(str).where(df.notna(), "")
    values = [frame.columns.tolist()] + frame.values.tolist()

    worksheet.clear()
    worksheet.update(values, "A1", raw=True)
    return len(frame)
