"""
CMS Provider Data API client.
Handles pagination, retry logic, and rate limiting for DKAN datastore endpoints.
"""

import time
import logging
import requests
from typing import Optional
from ingestion.config import CMS_API_BASE, API_PAGE_SIZE, API_MAX_RETRIES, API_RETRY_DELAY

logger = logging.getLogger(__name__)


def fetch_dataset(dataset_id: str, dataset_name: str) -> list[dict]:
    """
    Fetch all records from a CMS Provider Data API endpoint using POST.
    """
    all_records = []
    offset = 0

    logger.info(f"Starting fetch for {dataset_name} (ID: {dataset_id})")

    while True:
        url = f"{CMS_API_BASE}/{dataset_id}/0"
        payload = {
            "offset": offset,
            "count": True,
            "limit": API_PAGE_SIZE,
        }

        response = _request_with_retry(url, payload, dataset_name)

        if response is None:
            logger.error(f"Failed to fetch {dataset_name} after {API_MAX_RETRIES} retries")
            break

        data = response.json()
        results = data.get("results", [])
        all_records.extend(results)

        total_count = data.get("count", "unknown")
        logger.info(
            f"  {dataset_name}: fetched {len(all_records)} / {total_count} records"
        )

        if len(results) < API_PAGE_SIZE:
            break

        offset += API_PAGE_SIZE
        time.sleep(0.5)

    logger.info(f"Completed {dataset_name}: {len(all_records)} total records")
    return all_records


def _request_with_retry(
    url: str, payload: dict, dataset_name: str
) -> Optional[requests.Response]:
    """
    Make an HTTP POST request with exponential backoff retry logic.
    """
    for attempt in range(1, API_MAX_RETRIES + 1):
        try:
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            return response
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response else "unknown"
            if status_code in (429, 500, 502, 503, 504):
                wait_time = API_RETRY_DELAY * (2 ** (attempt - 1))
                logger.warning(
                    f"  {dataset_name}: HTTP {status_code}, "
                    f"retrying in {wait_time}s (attempt {attempt}/{API_MAX_RETRIES})"
                )
                time.sleep(wait_time)
            else:
                logger.error(f"  {dataset_name}: HTTP {status_code} - {e}")
                return None
        except requests.exceptions.RequestException as e:
            wait_time = API_RETRY_DELAY * (2 ** (attempt - 1))
            logger.warning(
                f"  {dataset_name}: Request failed ({e}), "
                f"retrying in {wait_time}s (attempt {attempt}/{API_MAX_RETRIES})"
            )
            time.sleep(wait_time)

    return None