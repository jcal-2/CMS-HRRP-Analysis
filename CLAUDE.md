# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Research pipeline analyzing whether CMS financial penalties (HRRP + VBP) drive hospital improvement or a decline feedback loop. Tracks ~3,000 US hospitals across 10 fiscal years (FY2016–FY2025) plus a current cross-sectional snapshot of 9 CMS Provider Data API datasets.

## Architecture

The pipeline is **Ingestion (Python) → Warehouse (BigQuery) → Transform (dbt) → Analysis (Python/JSON exports)**, optionally orchestrated by Dagster.

### Three top-level layers

1. **`ingestion/`** — Pulls raw data into BigQuery.
   - `cms_file_client.py` parses local HRRP supplemental ZIPs (one file per FY, schemas differ year-to-year) → `cms_raw_historical.raw_hrrp_fy{YYYY}` tables.
   - `cms_api_client.py` pages through 9 CMS Provider Data API endpoints (IDs in `config.py:CURRENT_DATASETS`) → `cms_raw_current.raw_{name}` tables.
   - `loaders.py` handles the BigQuery load; `run.py` runs both phases sequentially.
   - All GCP / dataset / file-mapping config lives in `ingestion/config.py`. Project is `data-viz-sandbox-495114`.

2. **`cms_penalty_analysis/`** — dbt project (profile name: `cms_penalty_analysis`, target `dev`, BigQuery oauth).
   - **staging/** unifies raw sources. `stg_hrrp_penalties.sql` is the load-bearing one: it normalizes 10 fiscal years of HRRP files (each with different column names and ERR conditions) into a single per-hospital-per-year shape. The other `stg_*` models flatten current-snapshot API tables.
   - **mart/** holds the analytic surface:
     - `fct_hospital_penalty_trajectory` — one row per hospital × fiscal year, with YoY penalty changes, cumulative penalty streak, ERR per condition, and hospital attributes joined in. This is the primary table for trend / persistence / Sankey analysis.
     - `fct_hospital_current_performance` — one row per hospital, joining current performance across all CMS dimensions with a `penalty_cohort` classification (`chronic` / `escaper` / `intermittent` / `never_penalized`).
     - `dim_hospital`, `dim_fiscal_year` (the latter encodes policy eras: pre/post peer-grouping introduction in FY2019, COVID era, etc.).
   - **tests/** — custom SQL data tests that encode domain invariants:
     - `assert_penalty_cap.sql` — HRRP penalty is capped at 3% (payment factor ≥ 0.97) for FY2016+.
     - `assert_peer_group_only_post_2019.sql` — peer grouping was introduced FY2019; rows with peer assignments before then are errors.
     - `assert_trajectory_completeness.sql`, `assert_no_duplicate_hospital_years.sql`.
   - Sources are declared in `models/staging/sources.yml`. Adding a new fiscal year means: drop the ZIP into `data/raw/`, register the filename in `config.py:HRRP_LOCAL_FILES`, add the table to `sources.yml`, and add a new CTE branch to `stg_hrrp_penalties.sql` (column names vary every year — check the raw file).

3. **`orchestration/definitions.py`** — Dagster assets that wrap the above as four steps: `ingest_historical_files` → `ingest_current_snapshots` → `dbt_build` → `generate_dbt_docs`. The first two shell out to the ingestion scripts; the dbt step runs `dbt build` from `cms_penalty_analysis/`.

### Root-level analysis scripts

`analysis.py`, `analysis_deep.py`, `export_data.py`, `validate.py`, and the `analysis/` directory are **ad-hoc query scripts** that read directly from BigQuery (mostly `cms_raw_historical.fct_hospital_penalty_trajectory`) to produce CSVs, charts, and `dashboard_data.json`. They are not part of the orchestrated pipeline — treat them as notebook-style explorations of the marts.

## Common commands

All run from the repo root unless noted.

```bash
# Ingestion
python -m ingestion.run                              # full pipeline (historical + current)
python ingestion/cms_file_client.py                  # historical HRRP files only
python ingestion/cms_api_client.py                   # current-snapshot API only

# dbt — MUST be run from cms_penalty_analysis/
cd cms_penalty_analysis
dbt build                                            # run + test all models
dbt run --select stg_hrrp_penalties+                 # run a model and its descendants
dbt test --select fct_hospital_penalty_trajectory    # run all tests for one model
dbt test --select assert_penalty_cap                 # run a single custom test

# Orchestration (Dagster UI)
dagster dev -f orchestration/definitions.py

# Analysis / exports
python export_data.py                                # regenerates dashboard_data.json
```

## Domain notes that affect modeling

- **`facility_id` is the CMS Certification Number (CCN)** — the universal hospital key across every source.
- **HRRP penalty cap = 3%** (payment factor = 0.97). Any value below that is a data error, not an extreme penalty.
- **Peer grouping was introduced in FY2019.** Pre-2019 rows have null `peer_group_assignment` and `dual_proportion` by design; the `peer_grouping_era` column distinguishes the regimes and several analyses must segment on it.
- **HRRP supplemental file schemas change every year** — column names, included conditions (CABG was added in FY2017), and casing all drift. `stg_hrrp_penalties.sql` is the canonical place to handle this; do not try to standardize the raw layer.
