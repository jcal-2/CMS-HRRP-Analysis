"""
Epic 10 / Story 10.1.1 + 10.1.2: CMS Cost Report (HCRIS) Ingestion
===================================================================
Extracts financial viability fields from raw CMS HCRIS data (Form 2552-10)
and loads them to BigQuery for enriching the 872 compound-penalized hospital list.

Fields extracted:
  - Number of Beds (S3, Line 14, Col 2)
  - Total Discharges (S3, Line 14, Col 15)
  - FTE Employees (S3, Line 14, Col 10)
  - Rural/Urban indicator (S2, Line 26, Col 1)
  - Net Patient Revenue (G3, Line 3, Col 1)
  - Total Other Income (G3, Line 4, Col 1)
  - Total Revenue (G3, Line 5, Col 1)   [net patient rev + other income]
  - Total Expenses (G3, Line 8, Col 1)  [total operating + non-operating]
  - Net Income (G3, Line 9, Col 1)
  - Operating Margin (derived: net_income / total_revenue)

Data source:
  https://www.cms.gov/data-research/statistics-trends-and-reports/cost-reports/cost-reports-fiscal-year

Usage:
  1. Download the latest HOSPITAL-2010 zip for the desired fiscal year
     from the CMS cost reports by fiscal year page.
  2. Unzip it into a folder (e.g., data/hcris_fy2024/)
  3. Run: python ingest_cost_reports.py --input-dir data/hcris_fy2024/ --project data-viz-sandbox-495114

Author: Jay Callery
Project: CMS-HRRP-Analysis (Epic 10)
"""

import argparse
import os
import sys
import glob
import pandas as pd
from google.cloud import bigquery

# ---------------------------------------------------------------------------
# HCRIS worksheet/line/column codes for fields we need
# Format: (worksheet_code, line_num, column_num, field_name)
#
# IMPORTANT: HCRIS encodes line/column as zero-padded strings.
#   Line 14 = "01400", Column 2 = "00200"
#   The trailing zeros represent sub-line/sub-column (usually 00).
#   Some HCRIS files use 5-digit codes, others 6-digit.
#   We normalize to 5-digit for matching.
# ---------------------------------------------------------------------------

NUMERIC_FIELDS = [
    # Worksheet S-3, Part I: Statistical Data
    ("S300001", 1400, 200, "bed_count"),           # Line 14, Col 2
    ("S300001", 1400, 1500, "total_discharges"),    # Line 14, Col 15
    ("S300001", 1400, 1000, "fte_employees"),        # Line 14, Col 10

    # Worksheet G-3: Statement of Revenues and Expenses
    ("G300000", 300, 100, "net_patient_revenue"),    # Line 3, Col 1
    ("G300000", 400, 100, "total_other_income"),     # Line 4, Col 1
    ("G300000", 500, 100, "total_revenue"),           # Line 5, Col 1  (net patient rev + other)
    ("G300000", 800, 100, "total_expenses"),           # Line 8, Col 1  (total oper + non-oper)
    ("G300000", 900, 100, "net_income"),               # Line 9, Col 1  (revenue - expenses)
]

ALPHA_FIELDS = [
    # Worksheet S-2, Part I: Provider Identification
    ("S200001", 2600, 100, "rural_urban"),    # Line 26, Col 1 (1=Urban, 2=Rural)
]


def parse_hcris_rpt(rpt_path: str) -> pd.DataFrame:
    """Parse the RPT file to get report-level metadata (CCN, fiscal year, etc.)."""
    print(f"  Parsing RPT file: {os.path.basename(rpt_path)}")

    # RPT file columns (pipe-delimited, no header)
    # rpt_rec_num | prvdr_ctrl_type_cd | prvdr_num | npi | rpt_stus_cd |
    # fy_bgn_dt | fy_end_dt | proc_dt | initl_rpt_sw | last_rpt_sw | trnsmtl_num | ...
    col_names = [
        "rpt_rec_num", "prvdr_ctrl_type_cd", "prvdr_num", "npi",
        "rpt_stus_cd", "fy_bgn_dt", "fy_end_dt", "proc_dt",
        "initl_rpt_sw", "last_rpt_sw", "trnsmtl_num",
        "fi_num", "adr_vndr_cd", "fi_creat_dt", "util_cd",
        "npr_dt", "spec_ind", "fi_rcpt_dt"
    ]

    df = pd.read_csv(
        rpt_path,
        sep=",",
        header=None,
        names=col_names,
        dtype=str,
        on_bad_lines="skip"
    )

    # prvdr_num is the CCN (facility_id)
    # Keep only the columns we need
    df = df[["rpt_rec_num", "prvdr_num", "fy_bgn_dt", "fy_end_dt", "rpt_stus_cd"]].copy()
    df.rename(columns={"prvdr_num": "facility_id"}, inplace=True)

    # Strip whitespace from facility_id
    df["facility_id"] = df["facility_id"].str.strip()

    print(f"    Found {len(df):,} cost reports")
    return df


def parse_hcris_nmrc(nmrc_path: str, fields: list) -> pd.DataFrame:
    """Parse the NMRC file to extract specific numeric fields."""
    print(f"  Parsing NMRC file: {os.path.basename(nmrc_path)} (this may take a minute...)")

    # NMRC columns: rpt_rec_num, wksht_cd, line_num, clmn_num, itm_val_num
    col_names = ["rpt_rec_num", "wksht_cd", "line_num", "clmn_num", "itm_val_num"]

    # Read in chunks to handle large files
    chunks = []
    for chunk in pd.read_csv(
        nmrc_path, sep=",", header=None, names=col_names,
        dtype={"rpt_rec_num": str, "wksht_cd": str, "line_num": str,
               "clmn_num": str, "itm_val_num": str},
        chunksize=500_000, on_bad_lines="skip"
    ):
        # Strip whitespace from codes
        chunk["wksht_cd"] = chunk["wksht_cd"].str.strip()
        chunk["line_num"] = chunk["line_num"].str.strip()
        chunk["clmn_num"] = chunk["clmn_num"].str.strip()

        # Filter to only the worksheet codes we care about
        target_worksheets = set(f[0] for f in fields)
        chunk = chunk[chunk["wksht_cd"].isin(target_worksheets)]

        if len(chunk) > 0:
            chunks.append(chunk)

    if not chunks:
        print("    WARNING: No matching records found in NMRC file")
        return pd.DataFrame()

    df = pd.concat(chunks, ignore_index=True)
    print(f"    Filtered to {len(df):,} rows for target worksheets")

    # Convert line_num and clmn_num to integers for matching
    # HCRIS uses zero-padded strings like "01400" or "00200"
    df["line_int"] = pd.to_numeric(df["line_num"], errors="coerce").astype("Int64")
    df["clmn_int"] = pd.to_numeric(df["clmn_num"], errors="coerce").astype("Int64")

    # Extract each field
    results = []
    for wksht, line, col, field_name in fields:
        mask = (
            (df["wksht_cd"] == wksht) &
            (df["line_int"] == line) &
            (df["clmn_int"] == col)
        )
        field_df = df.loc[mask, ["rpt_rec_num", "itm_val_num"]].copy()
        field_df["itm_val_num"] = pd.to_numeric(field_df["itm_val_num"], errors="coerce")
        field_df.rename(columns={"itm_val_num": field_name}, inplace=True)
        results.append(field_df)
        print(f"    {field_name}: {len(field_df):,} records")

    return results


def parse_hcris_alpha(alpha_path: str, fields: list) -> list:
    """Parse the ALPHNMRC file for text fields (e.g., rural/urban)."""
    print(f"  Parsing ALPHNMRC file: {os.path.basename(alpha_path)}")

    col_names = ["rpt_rec_num", "wksht_cd", "line_num", "clmn_num", "itm_alphnmrc_itm_txt"]

    chunks = []
    for chunk in pd.read_csv(
        alpha_path, sep=",", header=None, names=col_names,
        dtype=str, chunksize=500_000, on_bad_lines="skip"
    ):
        chunk["wksht_cd"] = chunk["wksht_cd"].str.strip()
        chunk["line_num"] = chunk["line_num"].str.strip()
        chunk["clmn_num"] = chunk["clmn_num"].str.strip()

        target_worksheets = set(f[0] for f in fields)
        chunk = chunk[chunk["wksht_cd"].isin(target_worksheets)]

        if len(chunk) > 0:
            chunks.append(chunk)

    if not chunks:
        return []

    df = pd.concat(chunks, ignore_index=True)
    df["line_int"] = pd.to_numeric(df["line_num"], errors="coerce").astype("Int64")
    df["clmn_int"] = pd.to_numeric(df["clmn_num"], errors="coerce").astype("Int64")

    results = []
    for wksht, line, col, field_name in fields:
        mask = (
            (df["wksht_cd"] == wksht) &
            (df["line_int"] == line) &
            (df["clmn_int"] == col)
        )
        field_df = df.loc[mask, ["rpt_rec_num", "itm_alphnmrc_itm_txt"]].copy()
        field_df.rename(columns={"itm_alphnmrc_itm_txt": field_name}, inplace=True)
        results.append(field_df)
        print(f"    {field_name}: {len(field_df):,} records")

    return results


def build_hospital_financials(rpt_df, nmrc_results, alpha_results) -> pd.DataFrame:
    """Join all extracted fields into a single hospital-level table."""
    print("\n  Building hospital-level financial table...")

    # Start with RPT as the base (one row per cost report)
    result = rpt_df[["rpt_rec_num", "facility_id", "fy_bgn_dt", "fy_end_dt"]].copy()

    # Join each numeric field
    for field_df in nmrc_results:
        if len(field_df) > 0:
            field_name = [c for c in field_df.columns if c != "rpt_rec_num"][0]
            result = result.merge(field_df, on="rpt_rec_num", how="left")

    # Join each alpha field
    for field_df in alpha_results:
        if len(field_df) > 0:
            field_name = [c for c in field_df.columns if c != "rpt_rec_num"][0]
            result = result.merge(field_df, on="rpt_rec_num", how="left")

    # Calculate derived fields
    if "total_revenue" in result.columns and "net_income" in result.columns:
        result["operating_margin"] = result.apply(
            lambda row: round(row["net_income"] / row["total_revenue"], 4)
            if pd.notna(row["total_revenue"]) and row["total_revenue"] != 0
            and pd.notna(row["net_income"])
            else None,
            axis=1
        )
    else:
        result["operating_margin"] = None

    # Map rural/urban codes
    if "rural_urban" in result.columns:
        result["rural_urban"] = result["rural_urban"].map(
            {"1": "Urban", "2": "Rural"}
        ).fillna("Unknown")

    # Drop rpt_rec_num (internal HCRIS key, not needed downstream)
    result.drop(columns=["rpt_rec_num"], inplace=True)

    # Deduplicate: keep the most recent cost report per facility
    result["fy_end_dt"] = pd.to_datetime(result["fy_end_dt"], errors="coerce")
    result.sort_values("fy_end_dt", ascending=False, inplace=True)
    result.drop_duplicates(subset=["facility_id"], keep="first", inplace=True)

    print(f"    Final table: {len(result):,} unique hospitals")
    print(f"    Columns: {list(result.columns)}")

    # Summary stats
    for col in ["bed_count", "total_discharges", "total_revenue", "operating_margin"]:
        if col in result.columns:
            non_null = result[col].notna().sum()
            print(f"    {col}: {non_null:,} non-null values")

    return result


def load_to_bigquery(df: pd.DataFrame, project: str, dataset: str, table: str):
    """Load the financial table to BigQuery."""
    table_id = f"{project}.{dataset}.{table}"
    print(f"\n  Loading to BigQuery: {table_id}")

    client = bigquery.Client(project=project)

    job_config = bigquery.LoadJobConfig(
        write_disposition="WRITE_TRUNCATE",
        autodetect=True,
    )

    job = client.load_table_from_dataframe(df, table_id, job_config=job_config)
    job.result()  # Wait for completion

    table_ref = client.get_table(table_id)
    print(f"    Loaded {table_ref.num_rows:,} rows to {table_id}")


def find_hcris_files(input_dir: str) -> tuple:
    """Find the RPT, NMRC, and ALPHNMRC files in the input directory."""
    rpt_files = glob.glob(os.path.join(input_dir, "*RPT*")) + \
                glob.glob(os.path.join(input_dir, "*rpt*"))
    nmrc_files = glob.glob(os.path.join(input_dir, "*NMRC*")) + \
                 glob.glob(os.path.join(input_dir, "*nmrc*"))
    alpha_files = glob.glob(os.path.join(input_dir, "*ALPHA*")) + \
                  glob.glob(os.path.join(input_dir, "*alpha*"))

    # Exclude NMRC from RPT matches, ALPHA from NMRC matches
    rpt_files = [f for f in rpt_files if "NMRC" not in f.upper() and "ALPHA" not in f.upper()]
    nmrc_files = [f for f in nmrc_files if "ALPHA" not in f.upper()]

    if not rpt_files:
        print("ERROR: No RPT file found. Expected a file like HOSP_RPT*.CSV")
        sys.exit(1)
    if not nmrc_files:
        print("ERROR: No NMRC file found. Expected a file like HOSP_NMRC*.CSV")
        sys.exit(1)

    rpt = rpt_files[0]
    nmrc = nmrc_files[0]
    alpha = alpha_files[0] if alpha_files else None

    print(f"  RPT:   {os.path.basename(rpt)}")
    print(f"  NMRC:  {os.path.basename(nmrc)}")
    print(f"  ALPHA: {os.path.basename(alpha) if alpha else 'NOT FOUND (rural/urban will be skipped)'}")

    return rpt, nmrc, alpha


def main():
    parser = argparse.ArgumentParser(
        description="Ingest CMS HCRIS Cost Report data for Epic 10"
    )
    parser.add_argument(
        "--input-dir", required=True,
        help="Directory containing unzipped HCRIS files (RPT, NMRC, ALPHNMRC)"
    )
    parser.add_argument(
        "--project", default="data-viz-sandbox-495114",
        help="GCP project ID"
    )
    parser.add_argument(
        "--dataset", default="cms_raw_historical",
        help="BigQuery dataset"
    )
    parser.add_argument(
        "--table", default="stg_cost_report_financials",
        help="BigQuery table name"
    )
    parser.add_argument(
        "--csv-only", action="store_true",
        help="Output CSV only, skip BigQuery load"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("CMS HCRIS Cost Report Ingestion")
    print("Epic 10 / Story 10.1.1 + 10.1.2")
    print("=" * 60)

    # Step 1: Find files
    print("\n[1/5] Locating HCRIS files...")
    rpt_path, nmrc_path, alpha_path = find_hcris_files(args.input_dir)

    # Step 2: Parse RPT (report metadata)
    print("\n[2/5] Parsing report metadata...")
    rpt_df = parse_hcris_rpt(rpt_path)

    # Step 3: Parse NMRC (numeric values)
    print("\n[3/5] Extracting financial and utilization fields...")
    nmrc_results = parse_hcris_nmrc(nmrc_path, NUMERIC_FIELDS)

    # Step 4: Parse ALPHNMRC (text values)
    alpha_results = []
    if alpha_path:
        print("\n[4/5] Extracting classification fields...")
        alpha_results = parse_hcris_alpha(alpha_path, ALPHA_FIELDS)
    else:
        print("\n[4/5] Skipping ALPHNMRC (file not found)")

    # Step 5: Build and load
    print("\n[5/5] Building hospital financial table...")
    financials = build_hospital_financials(rpt_df, nmrc_results, alpha_results)

    # Output CSV regardless
    csv_path = os.path.join(args.input_dir, "hospital_financials_extracted.csv")
    financials.to_csv(csv_path, index=False)
    print(f"\n  CSV saved: {csv_path}")

    # Load to BigQuery unless --csv-only
    if not args.csv_only:
        load_to_bigquery(financials, args.project, args.dataset, args.table)
    else:
        print("\n  Skipping BigQuery load (--csv-only flag set)")

    print("\n" + "=" * 60)
    print("DONE. Next steps:")
    print("  1. Verify row counts in BigQuery")
    print("  2. Run: SELECT facility_id, bed_count, operating_margin")
    print("     FROM stg_cost_report_financials")
    print("     WHERE facility_id IN (SELECT facility_id FROM compound_penalized)")
    print("  3. Build dbt model to join financials to compound-penalized list")
    print("  4. Re-tier based on penalty severity + financial viability")
    print("=" * 60)


if __name__ == "__main__":
    main()
