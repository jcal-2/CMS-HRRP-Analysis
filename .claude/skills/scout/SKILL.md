--- 
name: scout
description: Run the Data Scout on a new data file to detect schema changes and validate against dbt models. Use when ingesting a new HRRP penalty file, CMS API dataset, or VBP TPS update.
argument-hint: "[path/to/new/file]"
context: fork
agent: data-scout
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

Run the Data Scout agent on the file at: $ARGUMENTS

Steps:
1. Read the file and detect its schema (headers, columns, data types, row count)
2. Identify which dbt staging model it maps to based on column signatures
3. Compare schemas and flag any changes (additions, removals, renames)
4. If no changes: proceed with data load and run dbt build
5. If changes found: show the diff and wait for approval before modifying any models
6. Run dbt test and report results
7. Write ingestion metadata to analysis/ingestion_metadata.jsonl
8. Output the Data Scout Report summary