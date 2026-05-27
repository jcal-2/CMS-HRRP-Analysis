"""
Main ingestion entrypoint.
Orchestrates pulling historical files and current API data into BigQuery.
"""

import logging
import os
import pandas as pd
from ingestion.config import CURRENT_DATASETS, BQ_DATASET_HISTORICAL, BQ_DATASET_CURRENT, HRRP_LOCAL_FILES, RAW_DATA_DIR
from ingestion.cms_api_client import fetch_dataset
from ingestion.cms_file_client import parse_single_year
from ingestion.loaders import load_to_bigquery

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def run_historical_ingestion() -> None:
    """Load all historical HRRP penalty data — one table per fiscal year."""
    logger.info("=" * 60)
    logger.info("STARTING HISTORICAL INGESTION")
    logger.info("=" * 60)

    for fiscal_year, filename in sorted(HRRP_LOCAL_FILES.items()):
        filepath = os.path.join(RAW_DATA_DIR, filename)

        if not os.path.exists(filepath):
            logger.warning(f"FY{fiscal_year}: file not found, skipping")
            continue

        logger.info(f"--- FY{fiscal_year} ---")
        df = parse_single_year(fiscal_year, filepath)

        if df is not None and not df.empty:
            df["fiscal_year"] = fiscal_year
            table_name = f"raw_hrrp_fy{fiscal_year}"
            load_to_bigquery(df, BQ_DATASET_HISTORICAL, table_name)
        else:
            logger.warning(f"FY{fiscal_year}: no data parsed")

    logger.info("Historical ingestion complete")


def run_current_ingestion() -> None:
    """Fetch and load all current snapshot datasets from the CMS API."""
    logger.info("=" * 60)
    logger.info("STARTING CURRENT SNAPSHOT INGESTION")
    logger.info("=" * 60)

    for name, dataset_id in CURRENT_DATASETS.items():
        logger.info(f"--- Fetching {name} ---")
        records = fetch_dataset(dataset_id, name)

        if records:
            df = pd.DataFrame(records)
            table_name = f"raw_{name}"
            load_to_bigquery(df, BQ_DATASET_CURRENT, table_name)
        else:
            logger.warning(f"No records returned for {name}, skipping load")

    logger.info("Current snapshot ingestion complete")


def run_all() -> None:
    """Run the full ingestion pipeline."""
    run_historical_ingestion()
    run_current_ingestion()
    logger.info("=" * 60)
    logger.info("ALL INGESTION COMPLETE")
    logger.info("=" * 60)


if __name__ == "__main__":
    run_all()