"""Export all compound-penalized hospitals to CSV."""

from google.cloud import bigquery
import pandas as pd

client = bigquery.Client(project="data-viz-sandbox-495114")
DS = "data-viz-sandbox-495114.cms_raw_historical"

df = client.query(f"""
    WITH hrrp AS (
        SELECT facility_id, penalty_percentage as hrrp_pct, is_penalized
        FROM {DS}.fct_hospital_penalty_trajectory WHERE fiscal_year = 2025 AND is_penalized
    ),
    vbp AS (
        SELECT facility_id, total_performance_score as tps
        FROM {DS}.stg_vbp_tps WHERE total_performance_score < 29.17
    )
    SELECT h.facility_id, cp.facility_name, cp.city, cp.state, cp.census_region,
        cp.ownership_category, cp.star_rating,
        ROUND(h.hrrp_pct * 100, 2) as hrrp_penalty_pct,
        ROUND(v.tps, 1) as vbp_tps,
        cp.penalty_cohort, cp.total_years_penalized,
        ROUND(cp.avg_current_err, 4) as avg_err,
        ROUND(cp.mspb_ratio, 4) as mspb_ratio,
        ROUND(cp.avg_hac_score, 1) as hac_score
    FROM hrrp h
    JOIN vbp v USING (facility_id)
    JOIN {DS}.fct_hospital_current_performance cp USING (facility_id)
    ORDER BY h.hrrp_pct DESC, v.tps ASC
""").to_dataframe()

path = "analysis/compound_penalized_hospitals.csv"
df.to_csv(path, index=False)
print(f"Exported {len(df)} compound-penalized hospitals to {path}")
print(f"\nBreakdown:")
print(f"  Chronic: {len(df[df.penalty_cohort == 'chronic'])}")
print(f"  Intermittent: {len(df[df.penalty_cohort == 'intermittent'])}")
print(f"  Avg star rating: {df.star_rating.mean():.2f}")
print(f"  Avg HRRP penalty: {df.hrrp_penalty_pct.mean():.2f}%")
print(f"  Avg VBP TPS: {df.vbp_tps.mean():.1f}")