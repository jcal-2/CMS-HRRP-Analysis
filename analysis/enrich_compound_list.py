"""Enrich compound-penalized hospital list with sales tiers and themes."""

import pandas as pd

df = pd.read_csv("analysis/compound_penalized_hospitals.csv")

# ── Sales Tier ──────────────────────────────────────────────────────────
def assign_tier(row):
    if row['penalty_cohort'] == 'chronic' and row['hrrp_penalty_pct'] >= 0.5:
        return 'Tier 1 - Critical'
    elif row['penalty_cohort'] == 'chronic':
        return 'Tier 2 - High Priority'
    elif row['total_years_penalized'] >= 5:
        return 'Tier 3 - At Risk'
    else:
        return 'Tier 4 - Emerging'

df['sales_tier'] = df.apply(assign_tier, axis=1)

# ── Estimated Annual HRRP Revenue Loss ──────────────────────────────────
# Avg acute care hospital Medicare revenue ~$50M (CMS Cost Report benchmark)
# Actual varies widely, but gives a directional $ figure for sales decks
EST_MEDICARE_REV = 50_000_000
df['est_hrrp_loss'] = (df['hrrp_penalty_pct'] / 100 * EST_MEDICARE_REV).round(0).astype(int)

# ── Combined Penalty Severity Score (0-100) ─────────────────────────────
# Normalize HRRP penalty (0-3% range) and VBP TPS (0-100, inverted) to 0-100 each
df['hrrp_severity'] = (df['hrrp_penalty_pct'] / 3.0 * 100).clip(0, 100).round(1)
df['vbp_severity'] = ((29.17 - df['vbp_tps']) / 29.17 * 100).clip(0, 100).round(1)
df['compound_severity_score'] = ((df['hrrp_severity'] + df['vbp_severity']) / 2).round(1)

# ── Primary Sales Theme ─────────────────────────────────────────────────
def assign_theme(row):
    themes = []
    if row['hrrp_penalty_pct'] >= 1.0:
        themes.append('Readmission Reduction (urgent)')
    elif row['avg_err'] > 1.0:
        themes.append('Readmission Reduction')

    if row['vbp_tps'] < 20:
        themes.append('Quality Improvement Program')

    if row['star_rating'] <= 2:
        themes.append('Star Rating Recovery')

    if row['mspb_ratio'] > 1.02:
        themes.append('Cost Reduction / Care Efficiency')

    if row['hac_score'] and row['hac_score'] > 4000:
        themes.append('Patient Safety / HAC Reduction')

    if row['total_years_penalized'] >= 8:
        themes.append('Comprehensive Performance Turnaround')

    return ' | '.join(themes[:3]) if themes else 'General Performance Improvement'

df['sales_themes'] = df.apply(assign_theme, axis=1)

# ── Recommended Vendor Categories ───────────────────────────────────────
def recommend_vendors(row):
    vendors = []
    if row['avg_err'] > 1.0:
        vendors.append('Discharge Planning / Care Coordination')
    if row['avg_err'] > 1.02:
        vendors.append('Remote Patient Monitoring')
    if row['star_rating'] <= 2:
        vendors.append('Quality Analytics Platform')
    if row['mspb_ratio'] > 1.02:
        vendors.append('Revenue Cycle / Cost Management')
    if row['vbp_tps'] < 20:
        vendors.append('Value-Based Care Consulting')
    if row['hac_score'] and row['hac_score'] > 5000:
        vendors.append('Patient Safety / Infection Prevention')
    return ' | '.join(vendors[:3]) if vendors else 'Performance Improvement Consulting'

df['recommended_vendor_categories'] = df.apply(recommend_vendors, axis=1)

# ── Reorder columns ─────────────────────────────────────────────────────
col_order = [
    'sales_tier', 'compound_severity_score', 'est_hrrp_loss',
    'facility_id', 'facility_name', 'city', 'state', 'census_region',
    'ownership_category', 'star_rating',
    'hrrp_penalty_pct', 'vbp_tps',
    'penalty_cohort', 'total_years_penalized',
    'avg_err', 'mspb_ratio', 'hac_score',
    'sales_themes', 'recommended_vendor_categories'
]
df = df[col_order].sort_values(['sales_tier', 'compound_severity_score'], ascending=[True, False])

# ── Export ───────────────────────────────────────────────────────────────
path = "analysis/compound_penalized_hospitals_enriched.csv"
df.to_csv(path, index=False)

print(f"Enriched {len(df)} hospitals saved to {path}\n")
print("Tier Distribution:")
print(df['sales_tier'].value_counts().to_string())
print(f"\nTop 10 by Compound Severity Score:")
print(df[['sales_tier', 'compound_severity_score', 'est_hrrp_loss', 'facility_name', 'state', 'sales_themes']].head(10).to_string(index=False))