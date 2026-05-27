"""
Story 10.1.6: Backtest escapers vs chronic on financial profiles.

Question: Do hospitals that ESCAPED HRRP penalties (penalized in earlier years
but not in FY2025) look financially different from CHRONIC hospitals (penalized
every year 2016-2025), as observed in their most recent HCRIS cost report?

Compares bed_count, operating_margin, net_patient_revenue, fte_employees
between cohorts. Reports descriptive stats plus Welch's t-test (means)
and Mann-Whitney U (medians, robust to skewed distributions).
"""

from google.cloud import bigquery
import pandas as pd
import numpy as np
from scipy import stats

client = bigquery.Client(project="data-viz-sandbox-495114")
DS = "data-viz-sandbox-495114.cms_raw_historical"

sql = f"""
select
    c.facility_id,
    c.penalty_cohort,
    c.total_years_penalized,
    f.bed_count,
    f.operating_margin,
    f.net_patient_revenue,
    f.fte_employees
from `{DS}.fct_hospital_current_performance` c
left join `{DS}.fct_hospital_financials` f using (facility_id)
where c.penalty_cohort in ('chronic', 'escaper')
"""

df = client.query(sql).to_dataframe()

chronic = df[df['penalty_cohort'] == 'chronic']
escaper = df[df['penalty_cohort'] == 'escaper']

print(f"Sample sizes: chronic = {len(chronic)}, escaper = {len(escaper)}")
print(f"HCRIS-matched:  chronic = {chronic['bed_count'].notna().sum()}, "
      f"escaper = {escaper['bed_count'].notna().sum()}")
print()

metrics = [
    ('bed_count', 'Bed count', 0),
    ('operating_margin', 'Operating margin (%)', 4),
    ('net_patient_revenue', 'Net patient revenue ($M)', 1),
    ('fte_employees', 'FTE employees', 0),
]

results = []

for col, label, decimals in metrics:
    # BQ NUMERIC comes back as Decimal (object dtype); coerce for scipy.
    c = pd.to_numeric(chronic[col], errors='coerce').dropna()
    e = pd.to_numeric(escaper[col], errors='coerce').dropna()

    # Convert revenue to millions for readability
    if col == 'net_patient_revenue':
        c, e = c / 1e6, e / 1e6
    if col == 'operating_margin':
        c, e = c * 100, e * 100

    welch_t = stats.ttest_ind(c, e, equal_var=False)
    mwu = stats.mannwhitneyu(c, e, alternative='two-sided')

    row = {
        'metric': label,
        'chronic_n': len(c),
        'chronic_mean': round(c.mean(), decimals + 2),
        'chronic_median': round(c.median(), decimals + 2),
        'chronic_std': round(c.std(), decimals + 2),
        'escaper_n': len(e),
        'escaper_mean': round(e.mean(), decimals + 2),
        'escaper_median': round(e.median(), decimals + 2),
        'escaper_std': round(e.std(), decimals + 2),
        'welch_t': round(welch_t.statistic, 3),
        'welch_p': welch_t.pvalue,
        'mwu_p': mwu.pvalue,
    }
    results.append(row)

    print(f"=== {label} ===")
    print(f"  chronic:  n={row['chronic_n']:>5}  mean={row['chronic_mean']:>10}  "
          f"median={row['chronic_median']:>10}  std={row['chronic_std']}")
    print(f"  escaper:  n={row['escaper_n']:>5}  mean={row['escaper_mean']:>10}  "
          f"median={row['escaper_median']:>10}  std={row['escaper_std']}")
    print(f"  Welch's t-test:    t={row['welch_t']:>7}  p={row['welch_p']:.4g}  "
          f"{'***' if row['welch_p'] < 0.001 else '**' if row['welch_p'] < 0.01 else '*' if row['welch_p'] < 0.05 else 'ns'}")
    print(f"  Mann-Whitney U:                p={row['mwu_p']:.4g}  "
          f"{'***' if row['mwu_p'] < 0.001 else '**' if row['mwu_p'] < 0.01 else '*' if row['mwu_p'] < 0.05 else 'ns'}")
    print()

# Persist results for the record
results_df = pd.DataFrame(results)
out_path = "analysis/backtest_escapers_vs_chronic.csv"
results_df.to_csv(out_path, index=False)
print(f"Results saved to {out_path}\n")


# ─────────────────────────────────────────────────────────────────────────
# Covariate-controlled analysis: does cohort still matter after beds?
# ─────────────────────────────────────────────────────────────────────────
print("=" * 72)
print("CONTROLLING FOR BED_COUNT (OLS: outcome ~ is_escaper + bed_count)")
print("=" * 72)
print()


def ols_with_covariate(y, is_escaper, covariate):
    """
    Fit y = b0 + b1 * is_escaper + b2 * covariate via numpy lstsq.
    Returns dict with coefficient on is_escaper, its t-stat, p-value, and R^2.
    """
    n = len(y)
    X = np.column_stack([np.ones(n), is_escaper, covariate])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    y_hat = X @ beta
    resid = y - y_hat
    ss_res = (resid ** 2).sum()
    ss_tot = ((y - y.mean()) ** 2).sum()
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float('nan')

    dof = n - X.shape[1]
    sigma2 = ss_res / dof
    cov_beta = sigma2 * np.linalg.inv(X.T @ X)
    se = np.sqrt(np.diag(cov_beta))
    t = beta / se
    p = 2 * (1 - stats.t.cdf(np.abs(t), df=dof))

    return {
        'intercept': beta[0],
        'cohort_coef': beta[1],          # effect of being an escaper vs chronic
        'cohort_se': se[1],
        'cohort_t': t[1],
        'cohort_p': p[1],
        'beds_coef': beta[2],            # effect of one additional bed
        'beds_p': p[2],
        'r_squared': r2,
        'n': n,
    }


# Bed count is itself one of the four metrics — it's the covariate now,
# not an outcome — so we skip it in this loop.
covariate_metrics = [m for m in metrics if m[0] != 'bed_count']

cov_results = []
for col, label, decimals in covariate_metrics:
    sub = df.dropna(subset=[col, 'bed_count']).copy()
    sub[col] = pd.to_numeric(sub[col], errors='coerce')
    sub['bed_count'] = pd.to_numeric(sub['bed_count'], errors='coerce')
    sub = sub.dropna(subset=[col, 'bed_count'])

    y = sub[col].to_numpy(dtype=float)
    if col == 'net_patient_revenue':
        y = y / 1e6  # millions for readability
    if col == 'operating_margin':
        y = y * 100  # percentage points

    is_escaper = (sub['penalty_cohort'] == 'escaper').astype(int).to_numpy()
    beds = sub['bed_count'].to_numpy(dtype=float)

    r = ols_with_covariate(y, is_escaper, beds)
    r['metric'] = label
    cov_results.append(r)

    sig = '***' if r['cohort_p'] < 0.001 else '**' if r['cohort_p'] < 0.01 else '*' if r['cohort_p'] < 0.05 else 'ns'
    print(f"=== {label} ===")
    print(f"  n = {r['n']}, R^2 = {r['r_squared']:.3f}")
    print(f"  Escaper effect (controlling for beds): {r['cohort_coef']:+.4g}  "
          f"(SE {r['cohort_se']:.4g}, t={r['cohort_t']:.2f}, p={r['cohort_p']:.4g})  {sig}")
    print(f"  Each additional bed: {r['beds_coef']:+.4g}  (p={r['beds_p']:.4g})")
    print()

pd.DataFrame(cov_results).to_csv("analysis/backtest_escapers_vs_chronic_controlled.csv", index=False)


# ─────────────────────────────────────────────────────────────────────────
# Stratified view: median margin within bed brackets
# ─────────────────────────────────────────────────────────────────────────
print("=" * 72)
print("STRATIFIED BY BED BRACKET — Operating margin medians (%)")
print("=" * 72)

stratified = df.dropna(subset=['bed_count', 'operating_margin']).copy()
stratified['bed_count'] = pd.to_numeric(stratified['bed_count'], errors='coerce')
stratified['operating_margin'] = pd.to_numeric(stratified['operating_margin'], errors='coerce') * 100

def bed_bracket(b):
    if pd.isna(b): return 'null'
    if b < 100: return '<100'
    if b < 300: return '100-299'
    return '300+'

stratified['bed_bracket'] = stratified['bed_count'].apply(bed_bracket)

pivot = stratified.pivot_table(
    index='bed_bracket',
    columns='penalty_cohort',
    values='operating_margin',
    aggfunc=['median', 'count'],
).reindex(['<100', '100-299', '300+'])

print(pivot.to_string())
print()

# Mann-Whitney within each bracket
for bracket in ['<100', '100-299', '300+']:
    sub = stratified[stratified['bed_bracket'] == bracket]
    c = sub[sub['penalty_cohort'] == 'chronic']['operating_margin']
    e = sub[sub['penalty_cohort'] == 'escaper']['operating_margin']
    if len(c) > 5 and len(e) > 5:
        mwu = stats.mannwhitneyu(c, e, alternative='two-sided')
        sig = '***' if mwu.pvalue < 0.001 else '**' if mwu.pvalue < 0.01 else '*' if mwu.pvalue < 0.05 else 'ns'
        print(f"  {bracket}:  chronic median {c.median():+.2f}%  vs  escaper median {e.median():+.2f}%  (MWU p={mwu.pvalue:.4g})  {sig}")
