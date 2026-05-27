"""
Generate publication-ready charts for CMS Penalty Impact Analysis.
Styled with Aptos design system: 5-color palette, clean typography.
Saves PNGs to analysis/charts/
"""

import os
from google.cloud import bigquery
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.font_manager as fm

# Setup
client = bigquery.Client(project="data-viz-sandbox-495114")
DATASET = "data-viz-sandbox-495114.cms_raw_historical"
CHARTS_DIR = os.path.join(os.path.dirname(__file__), "charts")
os.makedirs(CHARTS_DIR, exist_ok=True)

# ── Aptos Design System ─────────────────────────────────────────────────
PALETTE = {
    "primary": "#274DEA",
    "light_blue": "#8EB9FC",
    "soft_green": "#EBFFDC",
    "soft_yellow": "#FFF197",
    "coral": "#FF513D",
}
NEUTRALS = {
    "text": "#1A1A1A",
    "secondary": "#4A4A4A",
    "muted": "#6B7280",
    "border": "#D9DEE8",
    "bg_soft": "#F7F9FC",
    "white": "#FFFFFF",
}
COHORT_COLORS = {
    "chronic": PALETTE["coral"],
    "intermittent": PALETTE["light_blue"],
    "escaper": PALETTE["primary"],
    "never_penalized": "#1B9E5A",
}

FONT_FAMILY = "Segoe UI"
for candidate in ["Aptos", "Segoe UI", "Calibri", "Arial"]:
    if any(candidate.lower() in f.name.lower() for f in fm.fontManager.ttflist):
        FONT_FAMILY = candidate
        break

plt.rcParams.update({
    "font.family": FONT_FAMILY,
    "font.size": 11,
    "axes.titlesize": 13,
    "axes.titleweight": "bold",
    "axes.labelsize": 11,
    "axes.labelcolor": NEUTRALS["text"],
    "axes.edgecolor": NEUTRALS["border"],
    "axes.grid": True,
    "grid.color": NEUTRALS["border"],
    "grid.alpha": 0.5,
    "xtick.color": NEUTRALS["secondary"],
    "ytick.color": NEUTRALS["secondary"],
    "text.color": NEUTRALS["text"],
    "figure.facecolor": NEUTRALS["white"],
    "axes.facecolor": NEUTRALS["white"],
    "legend.framealpha": 0.9,
    "legend.edgecolor": NEUTRALS["border"],
})


def save_chart(fig, name):
    path = os.path.join(CHARTS_DIR, f"{name}.png")
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  Saved: {path}")


# ── Chart 1: 75-80% of Hospitals Penalized Every Year for a Decade ──────

print("Chart 1: Penalty Rate & Severity")
df1 = client.query(f"""
    SELECT fiscal_year,
        ROUND(100.0 * SUM(CASE WHEN is_penalized THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_penalized,
        ROUND(100 * AVG(CASE WHEN is_penalized THEN penalty_percentage END), 2) AS avg_penalty_pct_x100
    FROM `{DATASET}.fct_hospital_penalty_trajectory`
    GROUP BY fiscal_year ORDER BY fiscal_year
""").to_dataframe()

fig, ax1 = plt.subplots(figsize=(10, 5))
ax1.bar(df1['fiscal_year'], df1['pct_penalized'], color=PALETTE["coral"], alpha=0.85, label="% Penalized", zorder=2)
ax1.set_ylabel("% of Hospitals Penalized", color=NEUTRALS["text"])
ax1.set_ylim(0, 100)
ax1.set_xlabel("Fiscal Year")

ax2 = ax1.twinx()
ax2.plot(df1['fiscal_year'], df1['avg_penalty_pct_x100'], color=PALETTE["primary"], linewidth=2.5, marker='o', label="Avg Penalty %", zorder=3)
ax2.set_ylabel("Avg Penalty % (among penalized)", color=PALETTE["primary"])
ax2.set_ylim(0, 1.0)

fig.suptitle("75-80% of Hospitals Penalized Every Year for a Decade", fontsize=14, fontweight="bold", y=1.02, color=NEUTRALS["text"])
ax1.set_xticks(df1['fiscal_year'])
ax1.legend(loc="upper left", fontsize=10)
ax2.legend(loc="upper right", fontsize=10)
save_chart(fig, "01_penalty_rate_severity")


# ── Chart 2: 49% of Hospitals Penalized All 10 Consecutive Years ────────

print("Chart 2: Penalty Persistence")
df2 = client.query(f"""
    SELECT total_years_penalized, COUNT(*) AS hospitals
    FROM `{DATASET}.fct_hospital_current_performance`
    WHERE total_years_tracked = 10
    GROUP BY total_years_penalized ORDER BY total_years_penalized
""").to_dataframe()

fig, ax = plt.subplots(figsize=(10, 5))
colors = [PALETTE["coral"] if x == 10 else PALETTE["light_blue"] for x in df2['total_years_penalized']]
ax.bar(df2['total_years_penalized'], df2['hospitals'], color=colors, zorder=2)
ax.set_xlabel("Years Penalized (out of 10)")
ax.set_ylabel("Number of Hospitals")
ax.set_title("49% of Hospitals Were Penalized All 10 Consecutive Years", fontsize=14, fontweight="bold")
ax.set_xticks(range(0, 11))

ten_yr = df2[df2['total_years_penalized'] == 10]['hospitals'].values[0]
total = df2['hospitals'].sum()
ax.annotate(f"{ten_yr:,} hospitals ({100*ten_yr/total:.0f}%)",
            xy=(10, ten_yr), xytext=(6.5, 1100),
            arrowprops=dict(arrowstyle="->", color=PALETTE["coral"], lw=1.5),
            fontsize=12, fontweight="bold", color=PALETTE["coral"])
save_chart(fig, "02_penalty_persistence")


# ── Chart 3: Chronic Hospitals Never Improve; Escapers Diverge Early ────

print("Chart 3: Cohort ERR Trajectories")
df3 = client.query(f"""
    SELECT t.fiscal_year, cp.penalty_cohort,
        ROUND(AVG(CASE WHEN t.avg_excess_readmission_ratio > 0.3 THEN t.avg_excess_readmission_ratio END), 4) AS avg_err
    FROM `{DATASET}.fct_hospital_penalty_trajectory` t
    JOIN `{DATASET}.fct_hospital_current_performance` cp USING (facility_id)
    WHERE cp.penalty_cohort IN ('chronic', 'escaper', 'intermittent', 'never_penalized')
      AND t.avg_excess_readmission_ratio IS NOT NULL
    GROUP BY t.fiscal_year, cp.penalty_cohort
    ORDER BY t.fiscal_year
""").to_dataframe()

fig, ax = plt.subplots(figsize=(10, 5))
cohort_labels = {
    "chronic": "Chronic (all 10 yrs)",
    "intermittent": "Intermittent",
    "escaper": "Escaper",
    "never_penalized": "Never Penalized",
}
for cohort, color in COHORT_COLORS.items():
    subset = df3[df3['penalty_cohort'] == cohort]
    ax.plot(subset['fiscal_year'], subset['avg_err'], color=color, linewidth=2.5, marker='o', markersize=5, label=cohort_labels[cohort])

ax.axhline(y=1.0, color=NEUTRALS["muted"], linestyle="--", alpha=0.6, label="Expected Rate (1.0)")

ax.annotate("CMS recalibrated\nERR methodology",
            xy=(2018, 1.03), xytext=(2015.8, 1.07),
            arrowprops=dict(arrowstyle="->", color=NEUTRALS["muted"], lw=1.2),
            fontsize=9, color=NEUTRALS["muted"], fontstyle="italic")

ax.set_xlabel("Fiscal Year")
ax.set_ylabel("Avg Excess Readmission Ratio")
ax.set_title("Chronic Hospitals Never Improve; Escapers Diverge Early", fontsize=14, fontweight="bold")
ax.legend(loc="lower right", fontsize=10)
ax.set_xticks(range(2016, 2026))
ax.set_ylim(0.55, 1.10)
save_chart(fig, "03_cohort_err_trajectories")


# ── Chart 4: Chronic Hospitals Perform Worse on Every Dimension ──────────

print("Chart 4: Cohort Performance Comparison")
df4 = client.query(f"""
    SELECT penalty_cohort,
        AVG(star_rating) AS avg_stars,
        AVG(avg_current_err) AS avg_err,
        AVG(mspb_ratio) AS avg_mspb,
        AVG(measures_above_expected) AS avg_measures_above
    FROM `{DATASET}.fct_hospital_current_performance`
    WHERE penalty_cohort IS NOT NULL
    GROUP BY penalty_cohort
""").to_dataframe()

cohort_order = ['never_penalized', 'escaper', 'intermittent', 'chronic']
df4['penalty_cohort'] = pd.Categorical(df4['penalty_cohort'], categories=cohort_order, ordered=True)
df4 = df4.sort_values('penalty_cohort')

fig, axes = plt.subplots(1, 4, figsize=(16, 5))
metrics = [
    ('avg_stars', 'Star Rating\n(higher = better)'),
    ('avg_err', 'Avg Readmission\nRatio'),
    ('avg_mspb', 'Medicare Spending\nRatio'),
    ('avg_measures_above', 'Measures Above\nExpected'),
]

xlabels = ["Never\nPen.", "Escaper", "Inter-\nmittent", "Chronic"]
for ax, (col, label) in zip(axes, metrics):
    colors_list = [COHORT_COLORS[c] for c in df4['penalty_cohort']]
    ax.bar(range(len(df4)), df4[col], color=colors_list, zorder=2)
    ax.set_title(label, fontsize=10, fontweight="bold")
    ax.set_xticks(range(len(df4)))
    ax.set_xticklabels(xlabels, fontsize=8)

fig.suptitle("Chronic Hospitals Perform Worse on Every Dimension", fontsize=14, fontweight="bold", y=1.02)
fig.tight_layout()
save_chart(fig, "04_cohort_performance")


# ── Chart 5: Higher Initial Severity, Lower Chance of Escape ─────────────

print("Chart 5: Escape Rate by Severity")
df5 = client.query(f"""
    WITH first_penalty AS (
        SELECT facility_id, MIN(fiscal_year) AS first_penalty_year
        FROM `{DATASET}.fct_hospital_penalty_trajectory`
        WHERE is_penalized GROUP BY facility_id
    ),
    initial_severity AS (
        SELECT t.facility_id,
            CASE
                WHEN t.penalty_percentage <= 0.002 THEN 'Low (0-0.2%)'
                WHEN t.penalty_percentage <= 0.005 THEN 'Medium (0.2-0.5%)'
                ELSE 'High (0.5%+)'
            END AS severity_tier
        FROM `{DATASET}.fct_hospital_penalty_trajectory` t
        JOIN first_penalty fp ON t.facility_id = fp.facility_id AND t.fiscal_year = fp.first_penalty_year
    )
    SELECT s.severity_tier,
        ROUND(100.0 * SUM(CASE WHEN cp.penalty_cohort = 'escaper' THEN 1 ELSE 0 END) / COUNT(*), 1) AS escape_rate
    FROM initial_severity s
    JOIN `{DATASET}.fct_hospital_current_performance` cp USING (facility_id)
    GROUP BY severity_tier
""").to_dataframe()

tier_order = ['Low (0-0.2%)', 'Medium (0.2-0.5%)', 'High (0.5%+)']
df5['severity_tier'] = pd.Categorical(df5['severity_tier'], categories=tier_order, ordered=True)
df5 = df5.sort_values('severity_tier')

fig, ax = plt.subplots(figsize=(8, 5))
bar_colors = ["#1B9E5A", PALETTE["light_blue"], PALETTE["coral"]]
ax.bar(range(len(df5)), df5['escape_rate'], color=bar_colors, zorder=2)
ax.set_xticks(range(len(df5)))
ax.set_xticklabels(df5['severity_tier'])
ax.set_ylabel("Escape Rate (%)")
ax.set_title("Higher Initial Severity, Lower Chance of Escape", fontsize=14, fontweight="bold")

for i, v in enumerate(df5['escape_rate']):
    ax.text(i, v + 0.5, f"{v}%", ha='center', fontweight='bold', fontsize=12, color=NEUTRALS["text"])

save_chart(fig, "05_escape_rate_by_severity")


# ── Chart 6: Northeast Traps Hospitals; West Lets Them Escape ────────────

print("Chart 6: Regional Chronic vs Escaper")
df6 = client.query(f"""
    SELECT census_region,
        ROUND(100.0 * SUM(CASE WHEN penalty_cohort = 'chronic' THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_chronic,
        ROUND(100.0 * SUM(CASE WHEN penalty_cohort = 'escaper' THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_escaper
    FROM `{DATASET}.fct_hospital_current_performance`
    WHERE penalty_cohort IS NOT NULL AND census_region != 'Other'
    GROUP BY census_region
    ORDER BY pct_chronic DESC
""").to_dataframe()

fig, ax = plt.subplots(figsize=(10, 5))
x = range(len(df6))
width = 0.35
ax.bar([i - width/2 for i in x], df6['pct_chronic'], width, color=PALETTE["coral"], label="% Chronic (all 10 yrs)", zorder=2)
ax.bar([i + width/2 for i in x], df6['pct_escaper'], width, color=PALETTE["primary"], label="% Escapers", zorder=2)
ax.set_xticks(x)
ax.set_xticklabels(df6['census_region'])
ax.set_ylabel("% of Hospitals in Region")
ax.set_title("Northeast Traps Hospitals; West Lets Them Escape", fontsize=14, fontweight="bold")
ax.legend(fontsize=10)
save_chart(fig, "06_regional_chronic_vs_escaper")


# ── Chart 7: Peer Grouping Helped Safety-Net Hospitals (Modestly) ────────

print("Chart 7: Safety-Net Penalty Trend")
df7 = client.query(f"""
    SELECT fiscal_year,
        CASE WHEN dual_proportion >= 0.5 THEN 'Safety-Net (>=50% Dual)' ELSE 'Non-Safety-Net (<25% Dual)' END AS hospital_type,
        ROUND(100.0 * SUM(CASE WHEN is_penalized THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_penalized
    FROM `{DATASET}.fct_hospital_penalty_trajectory`
    WHERE fiscal_year >= 2019 AND dual_proportion IS NOT NULL
      AND (dual_proportion >= 0.5 OR dual_proportion < 0.25)
    GROUP BY fiscal_year, hospital_type
    ORDER BY fiscal_year
""").to_dataframe()

fig, ax = plt.subplots(figsize=(10, 5))
for htype, color, marker in [
    ("Safety-Net (>=50% Dual)", PALETTE["primary"], 'o'),
    ("Non-Safety-Net (<25% Dual)", PALETTE["coral"], 's'),
]:
    subset = df7[df7['hospital_type'] == htype]
    ax.plot(subset['fiscal_year'], subset['pct_penalized'], color=color, linewidth=2.5, marker=marker, markersize=7, label=htype)

ax.annotate("COVID impact on\nreadmission data",
            xy=(2023, 75), xytext=(2020.5, 63),
            arrowprops=dict(arrowstyle="->", color=NEUTRALS["muted"], lw=1.2),
            fontsize=9, color=NEUTRALS["muted"], fontstyle="italic")

ax.set_xlabel("Fiscal Year")
ax.set_ylabel("% Penalized")
ax.set_title("Peer Grouping Helped Safety-Net Hospitals (Modestly)", fontsize=14, fontweight="bold")
ax.legend(fontsize=10)
ax.set_xticks(range(2019, 2026))
ax.set_ylim(60, 90)
save_chart(fig, "07_safety_net_penalty_trend")


print(f"\nAll charts saved to {CHARTS_DIR}/")
print("Ready for embedding in research document.")