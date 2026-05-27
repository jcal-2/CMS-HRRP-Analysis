---
name: analyze
description: Run the Analysis Agent on a dataset or query to generate exploratory summaries, statistical tests, and chart specs.
argument-hint: "[table_name or query description]"
context: fork
agent: analyst
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

Run the Analysis Agent on: $ARGUMENTS

Steps:
1. Load or query the target table / dataset described in $ARGUMENTS.
2. Generate the full ANALYSIS REPORT with all five sections: Data Summary, Statistical Tests, Key Findings, Suggested Charts, Follow-up Questions.
3. For every statistical test, explain WHY it fits the data before running it, then report the statistic, p-value, effect size, and a plain-English interpretation.
4. Use only the Aptos palette (#274DEA, #8EB9FC, #EBFFDC, #FFF197, #FF513D) in chart specs. Titles must be insight-driven and contain no em dashes.
5. Use "correlates with" and "suggests" language only. Never make causal claims.
6. End with suggested next investigative steps: which cohorts to slice next, which confounders to control for, and which charts would best communicate the findings to a non-technical reader.
