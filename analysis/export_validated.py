"""
Story 10.1.5: Export compound-penalized list with validated tier classification.

Pulls all 872 compound-penalized hospitals, joins HCRIS financials
(beds, margin, revenue, expenses, FTE), and assigns a "validated" sales
tier that combines penalty severity with financial viability.

Validated tier logic (Story 10.1.4):
  - Tier 1 Qualified: chronic + hrrp_penalty_pct >= 0.5 + positive margin + 100+ beds
  - Tier 1 Marginal:  chronic + hrrp_penalty_pct >= 0.5 but failing the margin or bed gate
  - Tier 2-4 unchanged, with positive_margin + bed_bracket columns for filtering
"""

from google.cloud import bigquery
import pandas as pd

client = bigquery.Client(project="data-viz-sandbox-495114")
DS = "data-viz-sandbox-495114.cms_raw_historical"

sql = f"""
with base as (
    select
        c.*,
        f.bed_count,
        f.fte_employees,
        f.net_patient_revenue,
        f.total_operating_expenses as total_expenses,
        f.operating_margin
    from `{DS}.compound_penalized_hospitals` c
    left join `{DS}.fct_hospital_financials` f using (facility_id)
)
select
    *,
    case
        when operating_margin is null then null
        else operating_margin > 0
    end as positive_margin,
    case
        when operating_margin is null then 'null'
        when operating_margin > 0 then 'positive'
        else 'negative'
    end as margin_status,
    case
        when bed_count is null then 'null'
        when bed_count < 100 then '<100'
        when bed_count < 300 then '100-299'
        else '300+'
    end as bed_bracket,
    case
        when penalty_cohort = 'chronic' and hrrp_penalty_pct >= 0.5 then
            case
                when operating_margin > 0 and bed_count >= 100 then 'Tier 1 Qualified'
                else 'Tier 1 Marginal'
            end
        when penalty_cohort = 'chronic' then 'Tier 2 - High Priority'
        when total_years_penalized >= 5 then 'Tier 3 - At Risk'
        else 'Tier 4 - Emerging'
    end as validated_tier
from base
"""

df = client.query(sql).to_dataframe()

# Column order: original 14 first, then financials, then derived flags/tier
original_cols = [
    'facility_id', 'facility_name', 'city', 'state', 'census_region',
    'ownership_category', 'star_rating', 'hrrp_penalty_pct', 'vbp_tps',
    'penalty_cohort', 'total_years_penalized', 'avg_err', 'mspb_ratio', 'hac_score',
]
financial_cols = [
    'bed_count', 'operating_margin', 'net_patient_revenue', 'total_expenses', 'fte_employees',
]
derived_cols = [
    'positive_margin', 'margin_status', 'bed_bracket', 'validated_tier',
]
df = df[original_cols + financial_cols + derived_cols]

# Sort by tier (Qualified first), then severity proxy (HRRP penalty desc)
tier_order = {
    'Tier 1 Qualified': 1,
    'Tier 1 Marginal': 2,
    'Tier 2 - High Priority': 3,
    'Tier 3 - At Risk': 4,
    'Tier 4 - Emerging': 5,
}
df['_tier_rank'] = df['validated_tier'].map(tier_order)
df = df.sort_values(['_tier_rank', 'hrrp_penalty_pct'], ascending=[True, False])
df = df.drop(columns=['_tier_rank'])

path = "analysis/compound_penalized_hospitals_validated.csv"
df.to_csv(path, index=False)

print(f"Exported {len(df)} hospitals to {path}\n")
print("Validated tier distribution:")
print(df['validated_tier'].value_counts().sort_index().to_string())
print(f"\nMargin status:")
print(df['margin_status'].value_counts().to_string())
print(f"\nBed bracket:")
print(df['bed_bracket'].value_counts().to_string())
print(f"\nTier 1 Qualified summary (n={len(df[df.validated_tier == 'Tier 1 Qualified'])}):")
tier1q = df[df['validated_tier'] == 'Tier 1 Qualified']
print(f"  Median beds: {tier1q['bed_count'].median():.0f}")
print(f"  Median revenue: ${tier1q['net_patient_revenue'].median() / 1e6:.1f}M")
print(f"  Median margin: {tier1q['operating_margin'].median() * 100:.2f}%")
print(f"  Median FTE: {tier1q['fte_employees'].median():.0f}")
