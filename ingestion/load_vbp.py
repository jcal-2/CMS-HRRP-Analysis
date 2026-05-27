"""Load HVBP Total Performance Score data to BigQuery."""

import pandas as pd
from google.cloud import bigquery

# Download
url = "https://data.cms.gov/provider-data/sites/default/files/resources/5551d4839c1dd75e3f7fe1310a1e2369_1770163628/hvbp_tps.csv"
df = pd.read_csv(url)
print(f"Downloaded {len(df)} rows")

# Clean column names
df.columns = [c.lower().replace(" ", "_").replace("/", "_").replace("&", "and") for c in df.columns]
print(f"Columns: {list(df.columns)}")

# Load to BigQuery
client = bigquery.Client(project="data-viz-sandbox-495114")
table_id = "data-viz-sandbox-495114.cms_raw_current.raw_hvbp_tps"

job_config = bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE")
job = client.load_table_from_dataframe(df, table_id, job_config=job_config)
job.result()

print(f"Loaded {job.output_rows} rows to {table_id}")