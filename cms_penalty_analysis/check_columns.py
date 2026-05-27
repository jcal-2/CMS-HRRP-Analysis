from google.cloud import bigquery
client = bigquery.Client(project="data-viz-sandbox-495114")

# Quick summary of the fact table
q = client.query("""
    SELECT 
        fiscal_year,
        COUNT(*) as hospitals,
        COUNTIF(is_penalized) as penalized,
        ROUND(AVG(penalty_percentage), 4) as avg_penalty_pct,
        ROUND(AVG(avg_excess_readmission_ratio), 4) as avg_err
    FROM cms_raw_historical.fct_hospital_penalty_trajectory
    GROUP BY fiscal_year
    ORDER BY fiscal_year
""")
print("FY     | Hospitals | Penalized | Avg Penalty % | Avg ERR")
print("-------|-----------|-----------|---------------|--------")
for row in q:
    print(f"FY{row.fiscal_year} | {row.hospitals:>9} | {row.penalized:>9} | {row.avg_penalty_pct:>13} | {row.avg_err}")