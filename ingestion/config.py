"""
Configuration for CMS data ingestion.
All dataset endpoints, file mappings, and project settings.
"""
import os

# GCP / BigQuery settings
GCP_PROJECT = "data-viz-sandbox-495114"
BQ_DATASET_HISTORICAL = "cms_raw_historical"
BQ_DATASET_CURRENT = "cms_raw_current"
BQ_DATASET_COSTREPORTS = "cms_raw_costreports"

# CMS Provider Data API base
CMS_API_BASE = "https://data.cms.gov/provider-data/api/1/datastore/query"

# Current snapshot datasets (API-based ingestion)
CURRENT_DATASETS = {
    "hcahps": "dgck-syfz",
    "readmissions": "9n3s-kdb3",
    "hospital_info": "xubh-q36u",
    "unplanned_visits": "cvcs-xecj",
    "spending": "rrqw-56er",
    "complications": "ynj2-r877",
    "hac": "77hc-ibv8",
    "timely_care": "yv7e-xc69",
    "payment_value": "c7us-v4mf",
}

# Local path to historical data files
RAW_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "raw")

# Historical HRRP supplemental data files (local ZIPs)
# Maps fiscal year to local filename
HRRP_LOCAL_FILES = {
    2013: "FY_2013_FR_Readmissions_File.zip",
    2014: "FY 2014 Final Rule Readmissions Supplemental Data PUF-CN_Sept 2013.zip",
    2015: "FY 2015 IPPS Final Rule Readmissions PUF-Oct 2014 CN.zip",
    2016: "FY 2016 IPPS Final Rule Readmissions PUF_revised 8-4-15.zip",
    2017: "FY 2017 IPPS Final Rule Readmissions Supplemental Data File.zip",
    2018: "fy_2018_ipps_final_rule_readmissions_supplemental_data_file.zip",
    2019: "fy_2019_ipps_final_rule_hrrp_supplemental_file.zip",
    2020: "FY2020_IPPS_Final_Rule_HRRP_Supplemental_File tab4.zip",
    2021: "FY2021_Final_Rule_Supplemental_File-v1.zip",
    2022: "FY2022_Final_Rule_Supplemental_File.zip",
    2023: "FY2023_Final_Rule_HRRP_Supplemental_File.zip",
    2024: "FY2024_Final_Rule_Supplemental_File Variations.zip",
    2025: "fy2025_final_rule_supplemental_file.zip",
}

# Pagination settings for API calls
API_PAGE_SIZE = 500
API_MAX_RETRIES = 3
API_RETRY_DELAY = 2  # seconds