"""
CMS Historical File Client.
Reads HRRP supplemental data files from local ZIPs and parses into DataFrames.
"""

import io
import os
import logging
import zipfile
import pandas as pd
from typing import Optional
from ingestion.config import HRRP_LOCAL_FILES, RAW_DATA_DIR

logger = logging.getLogger(__name__)

HEADER_KEYWORDS = ["provider", "hospital", "ccn"]


def parse_single_year(fiscal_year: int, filepath: str) -> Optional[pd.DataFrame]:
    """Public wrapper for parsing a single year's ZIP file."""
    return _parse_local_zip(fiscal_year, filepath)


def fetch_all_historical_hrrp() -> Optional[pd.DataFrame]:
    """Parse all fiscal years and return a stacked DataFrame."""
    all_frames = []
    for fiscal_year, filename in sorted(HRRP_LOCAL_FILES.items()):
        filepath = os.path.join(RAW_DATA_DIR, filename)
        if not os.path.exists(filepath):
            continue
        df = _parse_local_zip(fiscal_year, filepath)
        if df is not None and not df.empty:
            df["fiscal_year"] = fiscal_year
            all_frames.append(df)
    if not all_frames:
        return None
    return pd.concat(all_frames, ignore_index=True)


def _parse_local_zip(fiscal_year: int, filepath: str) -> Optional[pd.DataFrame]:
    """Parse a single fiscal year's HRRP ZIP file."""
    try:
        with zipfile.ZipFile(filepath) as zf:
            file_list = zf.namelist()
            logger.info(f"  FY{fiscal_year} archive contains: {file_list}")

            data_file = _find_data_file(file_list)
            if data_file is None:
                logger.warning(f"  FY{fiscal_year}: no recognized data file")
                return None

            logger.info(f"  Parsing: {data_file}")

            with zf.open(data_file) as f:
                file_bytes = f.read()
                lower = data_file.lower()

                if lower.endswith(".csv"):
                    df = _parse_csv_smart(file_bytes, fiscal_year)
                elif lower.endswith(".xls"):
                    df = _parse_excel_smart(file_bytes, fiscal_year, engine="xlrd")
                else:
                    df = _parse_excel_smart(file_bytes, fiscal_year, engine="openpyxl")

            return df

    except zipfile.BadZipFile:
        logger.error(f"  FY{fiscal_year}: not a valid ZIP")
        return None
    except Exception as e:
        logger.error(f"  FY{fiscal_year}: error — {e}")
        return None


def _find_data_file(file_list: list[str]) -> Optional[str]:
    """Find the main HRRP data file in a ZIP archive."""
    for name in file_list:
        lower = name.lower()
        if any(kw in lower for kw in ["hrrp", "readmission", "supplement"]):
            if lower.endswith((".xlsx", ".xls", ".csv")):
                return name

    for name in file_list:
        lower = name.lower()
        if lower.endswith((".xlsx", ".xls", ".csv")):
            if "layout" not in lower and "readme" not in lower:
                return name

    return None


def _parse_excel_smart(file_bytes: bytes, fiscal_year: int, engine: str) -> Optional[pd.DataFrame]:
    """
    Parse an Excel file by finding the best data sheet and detecting the header row.
    Scans for the row containing 'Hospital', 'Provider', or 'CCN' to find the real headers.
    """
    try:
        xls = pd.ExcelFile(io.BytesIO(file_bytes), engine=engine)
        logger.info(f"  FY{fiscal_year} sheets: {xls.sheet_names}")

        best_df = None
        best_rows = 0
        best_sheet = None

        for sheet_name in xls.sheet_names:
            lower_sheet = sheet_name.lower()
            if any(kw in lower_sheet for kw in ["variable", "layout", "description"]):
                continue

            # Read with no header to scan for the real header row
            raw = pd.read_excel(xls, sheet_name=sheet_name, header=None, dtype=str)

            header_row = _find_header_row(raw)
            if header_row is None:
                continue

            # Re-read with the correct header row
            df = pd.read_excel(xls, sheet_name=sheet_name, header=header_row, dtype=str)

            # Drop rows that are clearly not data (footers, notes)
            df = _clean_data_rows(df)

            if len(df) > best_rows:
                best_rows = len(df)
                best_df = df
                best_sheet = sheet_name

        if best_df is not None:
            logger.info(f"  FY{fiscal_year}: using sheet '{best_sheet}' with {best_rows} rows")

        return best_df

    except Exception as e:
        logger.error(f"  FY{fiscal_year}: Excel parse error — {e}")
        return None


def _parse_csv_smart(file_bytes: bytes, fiscal_year: int) -> Optional[pd.DataFrame]:
    """Parse a CSV file, detecting the header row."""
    try:
        raw = pd.read_csv(io.BytesIO(file_bytes), header=None, dtype=str)
        header_row = _find_header_row(raw)
        if header_row is None:
            return pd.read_csv(io.BytesIO(file_bytes), dtype=str)

        df = pd.read_csv(io.BytesIO(file_bytes), header=header_row, dtype=str)
        df = _clean_data_rows(df)
        return df

    except Exception as e:
        logger.error(f"  FY{fiscal_year}: CSV parse error — {e}")
        return None


def _find_header_row(raw: pd.DataFrame) -> Optional[int]:
    """
    Scan the first 15 rows for the one that contains header keywords
    like 'Hospital', 'Provider', or 'CCN' in the first column.
    """
    for i in range(min(15, len(raw))):
        cell = str(raw.iloc[i, 0]).lower().strip()
        if any(kw in cell for kw in HEADER_KEYWORDS):
            # Make sure it's a short header, not a long title containing 'hospital'
            if len(cell) < 50:
                return i

    # Fallback: check any column in the row, not just the first
    for i in range(min(15, len(raw))):
        for j in range(min(5, raw.shape[1])):
            cell = str(raw.iloc[i, j]).lower().strip()
            if any(kw in cell for kw in HEADER_KEYWORDS) and len(cell) < 50:
                return i

    return None


def _clean_data_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Remove footer rows and notes that aren't actual hospital data."""
    if df.empty:
        return df

    first_col = df.columns[0]

    # Keep only rows where the first column looks like a provider number
    # (6-digit number) or at least isn't a note/footer
    mask = df[first_col].apply(lambda x: _is_provider_number(str(x)))
    cleaned = df[mask].copy()

    return cleaned


def _is_provider_number(val: str) -> bool:
    """Check if a value looks like a CMS provider number (typically 6 digits)."""
    val = val.strip()
    if len(val) == 6 and val.isdigit():
        return True
    if len(val) == 6 and val[:2].isdigit():
        return True
    return False