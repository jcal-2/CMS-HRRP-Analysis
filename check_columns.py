from google.cloud import bigquery
client = bigquery.Client(project="data-viz-sandbox-495114")

tables = ['raw_readmissions', 'raw_spending', 'raw_complications', 
          'raw_hac', 'raw_payment_value', 'raw_unplanned_visits']

for table in tables:
    q = client.query(f"SELECT * FROM cms_raw_current.{table} LIMIT 1")
    print(f"\n=== {table.upper()} ===")
    for row in q:
        for k, v in dict(row).items():
            print(f"  {k}: {v}")
        break