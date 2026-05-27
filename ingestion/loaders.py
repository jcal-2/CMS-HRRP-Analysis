"""
BigQuery loading functions.
Handles DataFrame-to-BigQuery writes with column sanitization and logging.
"""

import re
import logging
import time
import pandas as pd
from google.cloud import bigquery
from ingestion.config import GCP_PROJECT

logger = logging.getLogger(__name__)

client = bigquery.Client(project=GCP_PROJECT)


def sanitize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean column names for BigQuery compatibility.
    Lowercase, replace spaces/special chars with underscores, truncate to 300 chars.
    """
    clean_cols = []
    for col in df.columns:
        col = str(col).strip().lower()
        col = re.sub(r'[^a-z0-9_]', '_', col)
        col = re.sub(r'_+', '_', col)
        col = col.strip('_')
        col = col[:300]
        clean_cols.append(col)
    df.columns = clean_cols
    return df


def load_to_bigquery(
    df: pd.DataFrame,
    dataset: str,
    table_name: str,
) -> None:
    """
    Load a DataFrame to a BigQuery table using WRITE_TRUNCATE (full refresh).
    """
    table_id = f"{GCP_PROJECT}.{dataset}.{table_name}"

    df = sanitize_columns(df)

    start_time = time.time()
    logger.info(f"Loading {len(df)} rows to {table_id}...")

    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        autodetect=True,
    )

    try:
        job = client.load_table_from_dataframe(df, table_id, job_config=job_config)
        job.result()

        duration = round(time.time() - start_time, 1)
        logger.info(f"  ✓ Loaded {len(df)} rows to {table_id} in {duration}s")
    except Exception as e:
        logger.error(f"  ✗ Failed to load {table_id}: {e}")
        raise