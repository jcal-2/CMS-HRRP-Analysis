from google.cloud import bigquery
client = bigquery.Client(project="data-viz-sandbox-495114")

q1 = client.query("SELECT fiscal_year, COUNT(*) as cnt FROM cms_raw_historical.raw_hrrp_penalties GROUP BY fiscal_year ORDER BY fiscal_year")
print("=== HISTORICAL HRRP BY FISCAL YEAR ===")
for row in q1:
    print(f"  FY{row.fiscal_year}: {row.cnt} hospitals")

q2 = client.query("SELECT table_id, row_count FROM `cms_raw_current.__TABLES__`")
print("\n=== CURRENT SNAPSHOT TABLES ===")
for row in q2:
    print(f"  {row.table_id}: {row.row_count} rows")