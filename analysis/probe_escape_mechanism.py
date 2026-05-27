"""
Story 10.1.7: Probe the escape mechanism.

Background: backtest_escapers_vs_chronic.py showed escapers have meaningfully
larger bed counts, higher revenue, and more FTEs than chronic hospitals — but
once bed_count is added as a covariate, the cohort coefficient mostly collapses.
That means "scale" is doing the explanatory work, but it doesn't tell us WHICH
scale-linked mechanism actually drove the escape.

This script probes five candidate mechanisms using scale-normalized metrics
derived from the HCRIS financials mart (which now includes total_discharges):

    H1 (volume intensity):    discharges per bed         — occupancy proxy
    H2 (case mix / pricing):  revenue per discharge      — acuity / payer-mix proxy
    H3 (cost efficiency):     expense per discharge      — unit-cost proxy
    H4 (labor density):       FTE per bed, FTE per discharge
    H5 (ERR trajectory):      mean ERR by fiscal year for each cohort
                              + duration-penalized-before-escape

For each per-hospital metric: descriptive stats, Welch's t-test, Mann-Whitney U,
and (where appropriate) an OLS check that the cohort effect survives controlling
for bed_count. ERR trajectory is reported as a year-by-year panel.
"""

from google.cloud import bigquery
import pandas as pd
import numpy as np
from scipy import stats

client = bigquery.Client(project="data-viz-sandbox-495114")
DS = "data-viz-sandbox-495114.cms_raw_historical"


# ─────────────────────────────────────────────────────────────────────────
# Pull the per-hospital frame: cohort + financials, escapers and chronic only
# ─────────────────────────────────────────────────────────────────────────
sql_financials = f"""
select
    c.facility_id,
    c.penalty_cohort,
    c.total_years_penalized,
    f.bed_count,
    f.fte_employees,
    f.total_discharges,
    f.net_patient_revenue,
    f.total_operating_expenses,
    f.operating_margin
from `{DS}.fct_hospital_current_performance` c
left join `{DS}.fct_hospital_financials` f using (facility_id)
where c.penalty_cohort in ('chronic', 'escaper')
"""

df = client.query(sql_financials).to_dataframe()

# Coerce BQ NUMERIC -> float (it arrives as Decimal/object)
for col in ['bed_count', 'fte_employees', 'total_discharges',
            'net_patient_revenue', 'total_operating_expenses', 'operating_margin']:
    df[col] = pd.to_numeric(df[col], errors='coerce')

# Derive the scale-normalized probes.
# Guard against zero/null denominators so we don't manufacture infinities.
df['discharges_per_bed']    = df['total_discharges']        / df['bed_count'].where(df['bed_count'] > 0)
df['revenue_per_discharge'] = df['net_patient_revenue']     / df['total_discharges'].where(df['total_discharges'] > 0)
df['expense_per_discharge'] = df['total_operating_expenses']/ df['total_discharges'].where(df['total_discharges'] > 0)
df['fte_per_bed']           = df['fte_employees']           / df['bed_count'].where(df['bed_count'] > 0)
df['fte_per_discharge']     = df['fte_employees']           / df['total_discharges'].where(df['total_discharges'] > 0)

# Strip the long tails before testing — HCRIS has a handful of facilities with
# absurd ratios (e.g., 4 beds reporting 50k discharges) that swamp Welch's t.
# We winsorize at the 1st/99th percentile per metric.
def winsorize(s, lo=0.01, hi=0.99):
    s = s.dropna()
    if s.empty:
        return s
    q_lo, q_hi = s.quantile(lo), s.quantile(hi)
    return s.clip(q_lo, q_hi)


# ─────────────────────────────────────────────────────────────────────────
# Two-sample tests on each scale-normalized metric
# ─────────────────────────────────────────────────────────────────────────
print("=" * 72)
print("SCALE-NORMALIZED MECHANISM PROBES — escapers vs chronic")
print("=" * 72)
print(f"Cohort sizes: chronic = {(df['penalty_cohort'] == 'chronic').sum()}, "
      f"escaper = {(df['penalty_cohort'] == 'escaper').sum()}\n")

probes = [
    ('discharges_per_bed',    'H1  Discharges per bed (volume intensity)',     1),
    ('revenue_per_discharge', 'H2  Revenue per discharge ($, case-mix proxy)', 0),
    ('expense_per_discharge', 'H3  Expense per discharge ($, unit cost)',      0),
    ('fte_per_bed',           'H4a FTE per bed (staffing density)',            2),
    ('fte_per_discharge',     'H4b FTE per discharge (labor intensity)',       4),
]

two_sample_results = []
for col, label, decimals in probes:
    c = winsorize(df.loc[df['penalty_cohort'] == 'chronic', col])
    e = winsorize(df.loc[df['penalty_cohort'] == 'escaper', col])

    if len(c) < 5 or len(e) < 5:
        print(f"=== {label} ===\n  skipped (n too small)\n")
        continue

    welch = stats.ttest_ind(c, e, equal_var=False)
    mwu   = stats.mannwhitneyu(c, e, alternative='two-sided')

    row = {
        'metric': label,
        'chronic_n':      len(c),
        'chronic_mean':   round(c.mean(),   decimals + 2),
        'chronic_median': round(c.median(), decimals + 2),
        'escaper_n':      len(e),
        'escaper_mean':   round(e.mean(),   decimals + 2),
        'escaper_median': round(e.median(), decimals + 2),
        'welch_t':        round(welch.statistic, 3),
        'welch_p':        welch.pvalue,
        'mwu_p':          mwu.pvalue,
    }
    two_sample_results.append(row)

    sig = ('***' if row['mwu_p'] < 0.001 else
           '**'  if row['mwu_p'] < 0.01  else
           '*'   if row['mwu_p'] < 0.05  else 'ns')

    print(f"=== {label} ===")
    print(f"  chronic:  n={row['chronic_n']:>5}  mean={row['chronic_mean']:>12}  median={row['chronic_median']:>12}")
    print(f"  escaper:  n={row['escaper_n']:>5}  mean={row['escaper_mean']:>12}  median={row['escaper_median']:>12}")
    print(f"  Welch's t:       t={row['welch_t']:>7}  p={row['welch_p']:.4g}")
    print(f"  Mann-Whitney U:                p={row['mwu_p']:.4g}  {sig}")
    print()

pd.DataFrame(two_sample_results).to_csv(
    "analysis/probe_escape_mechanism_two_sample.csv", index=False
)


# ─────────────────────────────────────────────────────────────────────────
# Bed-controlled OLS — does the cohort effect on per-discharge economics
# survive after accounting for size?
# ─────────────────────────────────────────────────────────────────────────
print("=" * 72)
print("BED-CONTROLLED OLS (outcome ~ is_escaper + bed_count)")
print("=" * 72)
print()


def ols_with_covariate(y, is_escaper, covariate):
    n = len(y)
    X = np.column_stack([np.ones(n), is_escaper, covariate])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
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
        'cohort_coef': beta[1],
        'cohort_se':   se[1],
        'cohort_t':    t[1],
        'cohort_p':    p[1],
        'beds_coef':   beta[2],
        'beds_p':      p[2],
        'r_squared':   r2,
        'n':           n,
    }


ols_results = []
# We don't run OLS on the metrics where bed_count is already in the denominator
# in a near-tautological way (discharges_per_bed, fte_per_bed) — for those, the
# two-sample test is the meaningful comparison. Per-discharge economics, on the
# other hand, are not mechanically pinned to bed_count.
ols_metrics = [
    ('revenue_per_discharge', 'H2 Revenue per discharge'),
    ('expense_per_discharge', 'H3 Expense per discharge'),
    ('fte_per_discharge',     'H4b FTE per discharge'),
]
for col, label in ols_metrics:
    sub = df.dropna(subset=[col, 'bed_count']).copy()
    sub[col] = winsorize(sub[col])
    sub = sub.dropna(subset=[col])

    y          = sub[col].to_numpy(dtype=float)
    is_escaper = (sub['penalty_cohort'] == 'escaper').astype(int).to_numpy()
    beds       = sub['bed_count'].to_numpy(dtype=float)

    r = ols_with_covariate(y, is_escaper, beds)
    r['metric'] = label
    ols_results.append(r)

    sig = ('***' if r['cohort_p'] < 0.001 else
           '**'  if r['cohort_p'] < 0.01  else
           '*'   if r['cohort_p'] < 0.05  else 'ns')
    print(f"=== {label} ===")
    print(f"  n = {r['n']}, R^2 = {r['r_squared']:.3f}")
    print(f"  Escaper effect (controlling for beds): {r['cohort_coef']:+.4g}  "
          f"(SE {r['cohort_se']:.4g}, t={r['cohort_t']:.2f}, p={r['cohort_p']:.4g})  {sig}")
    print(f"  Each additional bed:                   {r['beds_coef']:+.4g}  (p={r['beds_p']:.4g})")
    print()

pd.DataFrame(ols_results).to_csv(
    "analysis/probe_escape_mechanism_ols.csv", index=False
)


# ─────────────────────────────────────────────────────────────────────────
# H5: ERR trajectory — did escapers show a downward ERR trend over the
# panel, or did chronic hospitals stay flat? Cohort lives on the current
# performance table; ERR lives on the year-by-year trajectory table.
# ─────────────────────────────────────────────────────────────────────────
print("=" * 72)
print("H5  ERR TRAJECTORY BY FISCAL YEAR — escapers vs chronic")
print("=" * 72)

sql_trajectory = f"""
select
    t.fiscal_year,
    c.penalty_cohort,
    avg(t.avg_excess_readmission_ratio) as mean_err,
    approx_quantiles(t.avg_excess_readmission_ratio, 100)[offset(50)] as median_err,
    count(*) as n_hospitals
from `{DS}.fct_hospital_penalty_trajectory` t
join `{DS}.fct_hospital_current_performance` c using (facility_id)
where c.penalty_cohort in ('chronic', 'escaper')
  and t.avg_excess_readmission_ratio is not null
group by t.fiscal_year, c.penalty_cohort
order by t.fiscal_year, c.penalty_cohort
"""

traj = client.query(sql_trajectory).to_dataframe()
traj['mean_err']   = pd.to_numeric(traj['mean_err'],   errors='coerce')
traj['median_err'] = pd.to_numeric(traj['median_err'], errors='coerce')

pivot_mean   = traj.pivot(index='fiscal_year', columns='penalty_cohort', values='mean_err')
pivot_median = traj.pivot(index='fiscal_year', columns='penalty_cohort', values='median_err')

print("\nMean ERR by cohort by fiscal year:")
print(pivot_mean.round(4).to_string())
print("\nMedian ERR by cohort by fiscal year:")
print(pivot_median.round(4).to_string())

# Linear trend in mean ERR over the panel for each cohort
for cohort in ['chronic', 'escaper']:
    sub = traj[traj['penalty_cohort'] == cohort].dropna(subset=['mean_err'])
    if len(sub) >= 3:
        slope, intercept, r_value, p_value, _ = stats.linregress(
            sub['fiscal_year'], sub['mean_err']
        )
        print(f"\n{cohort:>8}:  ERR trend slope = {slope:+.5f} per year  "
              f"(R^2 = {r_value**2:.3f}, p = {p_value:.4g})")

traj.to_csv("analysis/probe_escape_mechanism_err_trajectory.csv", index=False)


# ─────────────────────────────────────────────────────────────────────────
# H6: How many years did escapers spend in penalty before escaping?
# Quick descriptive — not a hypothesis test, just useful context.
# ─────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 72)
print("H6  PENALTY YEARS BEFORE ESCAPE (descriptive)")
print("=" * 72)

escapers_years = df.loc[df['penalty_cohort'] == 'escaper', 'total_years_penalized'].dropna()
chronic_years  = df.loc[df['penalty_cohort'] == 'chronic',  'total_years_penalized'].dropna()
print(f"\nEscapers — years penalized before exit:")
print(f"  n = {len(escapers_years)},  mean = {escapers_years.mean():.2f},  "
      f"median = {escapers_years.median():.0f},  "
      f"p25/p75 = {escapers_years.quantile(0.25):.0f}/{escapers_years.quantile(0.75):.0f}")
print(f"Chronic — years penalized (reference):")
print(f"  n = {len(chronic_years)},  mean = {chronic_years.mean():.2f},  "
      f"median = {chronic_years.median():.0f}")

print("\nAll probe results saved under analysis/probe_escape_mechanism_*.csv")
