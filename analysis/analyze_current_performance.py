"""
Analysis Agent run on fct_hospital_current_performance.
Generates Data Summary, Statistical Tests, Key Findings.
"""
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from google.cloud import bigquery
from scipy import stats

PROJECT = "data-viz-sandbox-495114"
DATASET = "cms_raw_historical"
TABLE = f"`{PROJECT}.{DATASET}.fct_hospital_current_performance`"

client = bigquery.Client(project=PROJECT)
df = client.query(f"SELECT * FROM {TABLE}").to_dataframe()

print("=" * 78)
print("  DATA SUMMARY")
print("=" * 78)
print(f"\nRow count: {len(df):,}")
print(f"Column count: {df.shape[1]}")
print(f"Unique facility_ids: {df['facility_id'].nunique():,}")

print("\n--- Penalty cohort distribution ---")
cohort_counts = df["penalty_cohort"].value_counts(dropna=False)
cohort_pct = (cohort_counts / len(df) * 100).round(1)
print(pd.concat([cohort_counts, cohort_pct], axis=1, keys=["n", "pct"]))

print("\n--- Ownership category distribution ---")
print(df["ownership_category"].value_counts(dropna=False).head(10))

print("\n--- Census region distribution ---")
print(df["census_region"].value_counts(dropna=False))

print("\n--- Star rating distribution ---")
print(df["star_rating"].value_counts(dropna=False).sort_index())

print("\n--- Missingness (top 15 columns by null count) ---")
miss = df.isna().sum().sort_values(ascending=False)
miss_pct = (miss / len(df) * 100).round(1)
print(pd.concat([miss, miss_pct], axis=1, keys=["nulls", "pct"]).head(15))

# Continuous distribution stats
cont_cols = [
    "star_rating", "total_years_penalized", "penalty_pct_fy2025", "avg_err_fy2025",
    "mspb_ratio", "avg_current_err", "measures_above_expected",
    "complications_worse_than_national", "complications_better_than_national",
    "hac_worse_than_national", "avg_hac_score",
    "avg_payment_amount", "value_of_care_worse_than_national",
]
print("\n--- Continuous distributions (p10, p25, p50, p75, p90, mean, std, IQR-outliers) ---")
rows = []
for c in cont_cols:
    if c not in df.columns:
        continue
    s = pd.to_numeric(df[c], errors="coerce").dropna()
    if len(s) == 0:
        continue
    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    iqr = q3 - q1
    lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    outliers = int(((s < lo) | (s > hi)).sum())
    rows.append({
        "col": c, "n": len(s),
        "p10": round(s.quantile(0.10), 3), "p25": round(q1, 3),
        "p50": round(s.median(), 3), "p75": round(q3, 3),
        "p90": round(s.quantile(0.90), 3),
        "mean": round(s.mean(), 3), "std": round(s.std(), 3),
        "outliers_iqr": outliers,
    })
print(pd.DataFrame(rows).to_string(index=False))

print("\n--- Per-cohort means on key performance metrics ---")
agg_cols = ["star_rating", "avg_current_err", "mspb_ratio",
            "complications_worse_than_national", "avg_hac_score",
            "avg_payment_amount", "value_of_care_worse_than_national"]
cohort_means = df.groupby("penalty_cohort")[agg_cols].mean().round(3)
print(cohort_means)

print("\n--- Cohort size sanity ---")
print(df.groupby("penalty_cohort").size())

print("\n" + "=" * 78)
print("  STATISTICAL TESTS")
print("=" * 78)

def cohens_d(a, b):
    a = np.asarray(a, dtype=float); b = np.asarray(b, dtype=float)
    a = a[~np.isnan(a)]; b = b[~np.isnan(b)]
    if len(a) < 2 or len(b) < 2:
        return float("nan")
    sa, sb = a.std(ddof=1), b.std(ddof=1)
    pooled = np.sqrt(((len(a) - 1) * sa**2 + (len(b) - 1) * sb**2) / (len(a) + len(b) - 2))
    if pooled == 0:
        return float("nan")
    return (a.mean() - b.mean()) / pooled

def label_d(d):
    ad = abs(d)
    if ad < 0.2: return "negligible"
    if ad < 0.5: return "small"
    if ad < 0.8: return "medium"
    return "large"

# TEST 1: Welch's t-test, chronic vs never_penalized: star_rating
print("\n[Test 1] Welch's t-test: star_rating, chronic vs never_penalized")
a = df.loc[df["penalty_cohort"] == "chronic", "star_rating"].dropna().astype(float)
b = df.loc[df["penalty_cohort"] == "never_penalized", "star_rating"].dropna().astype(float)
t, p = stats.ttest_ind(a, b, equal_var=False)
d = cohens_d(a, b)
print(f"  n_chronic={len(a)}, mean={a.mean():.3f}; n_never={len(b)}, mean={b.mean():.3f}")
print(f"  t={t:.3f}, p={p:.3e}, Cohen's d={d:.3f} ({label_d(d)})")

# TEST 2: Welch's t-test: avg_current_err chronic vs never
print("\n[Test 2] Welch's t-test: avg_current_err, chronic vs never_penalized")
a = df.loc[df["penalty_cohort"] == "chronic", "avg_current_err"].dropna().astype(float)
b = df.loc[df["penalty_cohort"] == "never_penalized", "avg_current_err"].dropna().astype(float)
t, p = stats.ttest_ind(a, b, equal_var=False)
d = cohens_d(a, b)
print(f"  n_chronic={len(a)}, mean={a.mean():.4f}; n_never={len(b)}, mean={b.mean():.4f}")
print(f"  t={t:.3f}, p={p:.3e}, Cohen's d={d:.3f} ({label_d(d)})")

# TEST 3: Welch's t-test: mspb_ratio chronic vs never
print("\n[Test 3] Welch's t-test: mspb_ratio (spending), chronic vs never_penalized")
a = df.loc[df["penalty_cohort"] == "chronic", "mspb_ratio"].dropna().astype(float)
b = df.loc[df["penalty_cohort"] == "never_penalized", "mspb_ratio"].dropna().astype(float)
t, p = stats.ttest_ind(a, b, equal_var=False)
d = cohens_d(a, b)
print(f"  n_chronic={len(a)}, mean={a.mean():.4f}; n_never={len(b)}, mean={b.mean():.4f}")
print(f"  t={t:.3f}, p={p:.3e}, Cohen's d={d:.3f} ({label_d(d)})")

# TEST 4: Chi-square: ownership_category x penalty_cohort
print("\n[Test 4] Chi-square: ownership_category vs penalty_cohort")
sub = df.dropna(subset=["ownership_category", "penalty_cohort"])
ct = pd.crosstab(sub["ownership_category"], sub["penalty_cohort"])
chi2, p, dof, exp = stats.chi2_contingency(ct)
n = ct.values.sum()
cramers_v = np.sqrt(chi2 / (n * (min(ct.shape) - 1)))
print(ct)
print(f"  chi2={chi2:.2f}, dof={dof}, p={p:.3e}, Cramer's V={cramers_v:.3f}")

# TEST 5: Chi-square: census_region x penalty_cohort
print("\n[Test 5] Chi-square: census_region vs penalty_cohort")
sub = df.dropna(subset=["census_region", "penalty_cohort"])
ct = pd.crosstab(sub["census_region"], sub["penalty_cohort"])
chi2, p, dof, exp = stats.chi2_contingency(ct)
n = ct.values.sum()
cramers_v = np.sqrt(chi2 / (n * (min(ct.shape) - 1)))
print(ct)
print(f"  chi2={chi2:.2f}, dof={dof}, p={p:.3e}, Cramer's V={cramers_v:.3f}")

# TEST 6: Mann-Whitney U: total_years_penalized For-profit vs Non-profit (skewed counts)
print("\n[Test 6] Mann-Whitney U: total_years_penalized, For-profit vs Non-profit")
own = df.copy()
own["own_simple"] = own["ownership_category"].str.lower()
fp = own.loc[own["own_simple"].str.contains("for-profit|proprietary", na=False), "total_years_penalized"].dropna()
np_ = own.loc[own["own_simple"].str.contains("non.?profit|voluntary", na=False), "total_years_penalized"].dropna()
if len(fp) > 0 and len(np_) > 0:
    u, p = stats.mannwhitneyu(fp, np_, alternative="two-sided")
    # rank-biserial effect size
    r_rb = 1 - (2 * u) / (len(fp) * len(np_))
    print(f"  n_for_profit={len(fp)}, median={fp.median():.1f}; n_non_profit={len(np_)}, median={np_.median():.1f}")
    print(f"  U={u:.0f}, p={p:.3e}, rank-biserial r={r_rb:.3f}")
else:
    print(f"  Insufficient sample sizes (fp={len(fp)}, np={len(np_)})")

# TEST 7: Spearman rank correlation: avg_current_err vs total_years_penalized
print("\n[Test 7] Spearman correlation: avg_current_err vs total_years_penalized")
sub = df[["avg_current_err", "total_years_penalized"]].dropna()
rho, p = stats.spearmanr(sub["avg_current_err"], sub["total_years_penalized"])
print(f"  n={len(sub)}, rho={rho:.3f}, p={p:.3e}")

# TEST 8: Spearman: mspb_ratio vs total_years_penalized
print("\n[Test 8] Spearman correlation: mspb_ratio vs total_years_penalized")
sub = df[["mspb_ratio", "total_years_penalized"]].dropna()
rho, p = stats.spearmanr(sub["mspb_ratio"], sub["total_years_penalized"])
print(f"  n={len(sub)}, rho={rho:.3f}, p={p:.3e}")

# TEST 9: Spearman: star_rating vs total_years_penalized
print("\n[Test 9] Spearman correlation: star_rating vs total_years_penalized")
sub = df[["star_rating", "total_years_penalized"]].dropna()
rho, p = stats.spearmanr(sub["star_rating"], sub["total_years_penalized"])
print(f"  n={len(sub)}, rho={rho:.3f}, p={p:.3e}")

# TEST 10: Kruskal-Wallis: avg_hac_score across all four cohorts
print("\n[Test 10] Kruskal-Wallis: avg_hac_score across the four penalty cohorts")
groups = [df.loc[df["penalty_cohort"] == c, "avg_hac_score"].dropna().astype(float)
          for c in ["chronic", "intermittent", "escaper", "never_penalized"]]
sizes = [len(g) for g in groups]
print(f"  group sizes: chronic={sizes[0]}, intermittent={sizes[1]}, escaper={sizes[2]}, never={sizes[3]}")
H, p = stats.kruskal(*groups)
# eta^2 effect size for Kruskal
N = sum(sizes); k = len(groups)
eta2 = (H - k + 1) / (N - k)
print(f"  H={H:.2f}, p={p:.3e}, eta-squared={eta2:.4f}")

print("\n" + "=" * 78)
print("  ADDITIONAL CUTS")
print("=" * 78)
print("\nCohort rates within each ownership category (row %):")
sub = df.dropna(subset=["ownership_category", "penalty_cohort"])
ct = pd.crosstab(sub["ownership_category"], sub["penalty_cohort"], normalize="index") * 100
print(ct.round(1))

print("\nCohort rates within each census region (row %):")
sub = df.dropna(subset=["census_region", "penalty_cohort"])
ct = pd.crosstab(sub["census_region"], sub["penalty_cohort"], normalize="index") * 100
print(ct.round(1))

print("\nAvg star rating by cohort (with n):")
print(df.groupby("penalty_cohort")["star_rating"].agg(["count", "mean", "median", "std"]).round(2))

print("\nDone.")
