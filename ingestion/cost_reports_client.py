"""
HCRIS Cost Report Client.
Loads the three-file CMS HCRIS Hospital 2552-10 layout (rpt / nmrc / alpha)
from a local directory into BigQuery as raw long-format tables.

Usage:
    python -m ingestion.cost_reports_client --input-dir HOSP10FY2025/
    python -m ingestion.cost_reports_client --input-dir HOSP10FY2025/ --project data-viz-sandbox-495114
"""

import argparse
import logging
import os
import re
import sys
import time
import pandas as pd
from google.cloud import bigquery
from google.cloud.exceptions import NotFound

from ingestion.config import GCP_PROJECT, BQ_DATASET_COSTREPORTS

logger = logging.getLogger(__name__)

# HCRIS files have no headers — schemas are positional per CMS form 2552-10 layout.
RPT_COLUMNS = [
    "rpt_rec_num", "prvdr_ctrl_type_cd", "prvdr_num", "npi", "rpt_stus_cd",
    "fy_bgn_dt", "fy_end_dt", "proc_dt", "initl_rpt_sw", "last_rpt_sw",
    "trnsmtl_num", "fi_num", "adr_vndr_cd", "fi_creat_dt", "util_cd",
    "npr_dt", "spec_ind", "fi_rcpt_dt",
]
NMRC_COLUMNS = ["rpt_rec_num", "wksht_cd", "line_num", "clmn_num", "itm_val_num"]
ALPHA_COLUMNS = ["rpt_rec_num", "wksht_cd", "line_num", "clmn_num", "itm_alphanmrc_itm_txt"]

FILE_SPECS = [
    ("rpt", RPT_COLUMNS, "raw_hcris_rpt"),
    ("nmrc", NMRC_COLUMNS, "raw_hcris_nmrc"),
    ("alpha", ALPHA_COLUMNS, "raw_hcris_alpha"),
]


def find_file(input_dir: str, suffix: str) -> str:
    """Find the CSV in input_dir whose name ends with _<suffix>.csv (case-insensitive)."""
    target = f"_{suffix}.csv".lower()
    for name in os.listdir(input_dir):
        if name.lower().endswith(target):
            return os.path.join(input_dir, name)
    raise FileNotFoundError(f"No file matching *_{suffix}.csv in {input_dir}")


def read_hcris_csv(path: str, columns: list[str]) -> pd.DataFrame:
    """
    Read an HCRIS CSV with explicit column names, no header, all strings.
    String dtype preserves zero-padded codes (wksht_cd, line_num, clmn_num)
    and avoids type drift on numeric values that should be cast in dbt.
    """
    return pd.read_csv(path, header=None, names=columns, dtype=str, keep_default_na=False)


def ensure_dataset(client: bigquery.Client, dataset_id: str) -> None:
    """Create the dataset if it doesn't exist."""
    full_id = f"{client.project}.{dataset_id}"
    try:
        client.get_dataset(full_id)
    except NotFound:
        logger.info(f"Creating dataset {full_id}")
        dataset = bigquery.Dataset(full_id)
        dataset.location = "US"
        client.create_dataset(dataset)


def detect_fy(input_dir: str) -> int:
    """Extract a 4-digit fiscal year from the input directory name (e.g. HOSP10FY2024 -> 2024)."""
    base = os.path.basename(os.path.normpath(input_dir))
    m = re.search(r"(?:FY|fy)?(20\d{2})", base)
    if not m:
        raise ValueError(
            f"Could not infer fiscal year from directory '{base}'. "
            f"Pass --fiscal-year YYYY explicitly."
        )
    return int(m.group(1))


def load_df(client: bigquery.Client, df: pd.DataFrame, dataset: str, table: str) -> None:
    """Truncate-load a DataFrame into <project>.<dataset>.<table> as all STRING columns."""
    table_id = f"{client.project}.{dataset}.{table}"
    schema = [bigquery.SchemaField(c, "STRING") for c in df.columns]
    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        schema=schema,
    )
    start = time.time()
    logger.info(f"Loading {len(df):,} rows -> {table_id}")
    job = client.load_table_from_dataframe(df, table_id, job_config=job_config)
    job.result()
    logger.info(f"  done in {round(time.time() - start, 1)}s")


def ingest(
    input_dir: str,
    project: str,
    dataset: str,
    fiscal_year: int,
    dry_run: bool = False,
) -> None:
    """
    Load one fiscal year of HCRIS into per-FY suffixed tables:
    raw_hcris_rpt_fy{YYYY}, raw_hcris_nmrc_fy{YYYY}, raw_hcris_alpha_fy{YYYY}.
    Per-FY tables + WRITE_TRUNCATE = idempotent without DML (free-tier compatible).
    """
    if not os.path.isdir(input_dir):
        raise NotADirectoryError(f"{input_dir} is not a directory")

    client = None
    if not dry_run:
        client = bigquery.Client(project=project)
        ensure_dataset(client, dataset)
    else:
        logger.info("DRY RUN — parsing only, no BigQuery writes")

    logger.info(f"Loading fiscal year {fiscal_year} into _fy{fiscal_year}-suffixed tables")

    for suffix, columns, base_table in FILE_SPECS:
        table = f"{base_table}_fy{fiscal_year}"
        path = find_file(input_dir, suffix)
        logger.info(f"Reading {path}")
        df = read_hcris_csv(path, columns)
        logger.info(f"  parsed {len(df):,} rows, {len(df.columns)} cols")
        logger.info(f"  sample row: {df.iloc[0].to_dict()}")
        if dry_run:
            target = f"{project}.{dataset}.{table}"
            logger.info(f"  would load -> {target}")
        else:
            load_df(client, df, dataset, table)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    parser = argparse.ArgumentParser(description="Load HCRIS cost report CSVs into BigQuery.")
    parser.add_argument("--input-dir", required=True, help="Directory containing _rpt.csv, _nmrc.csv, _alpha.csv")
    parser.add_argument("--project", default=GCP_PROJECT, help=f"GCP project (default: {GCP_PROJECT})")
    parser.add_argument("--dataset", default=BQ_DATASET_COSTREPORTS, help=f"BigQuery dataset (default: {BQ_DATASET_COSTREPORTS})")
    parser.add_argument("--fiscal-year", type=int, default=None, help="Override fiscal year tag (default: auto-detect from --input-dir)")
    parser.add_argument("--dry-run", action="store_true", help="Parse CSVs and report counts without writing to BigQuery")
    args = parser.parse_args()

    fy = args.fiscal_year if args.fiscal_year is not None else detect_fy(args.input_dir)

    ingest(args.input_dir, args.project, args.dataset, fy, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
