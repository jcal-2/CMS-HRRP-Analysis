---
name: scenario
description: Run a policy scenario simulation to model the impact of CMS rule changes on penalized hospitals.
argument-hint: "[policy scenario description]"
context: fork
agent: policy-engine
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

Run the Policy Engine agent on the scenario: $ARGUMENTS

Steps:
1. Map the scenario to one (or a combination) of the four policy solutions: aggregate penalty cap, extended peer grouping, reinvestment mandate, improvement trajectory scoring. State the mapping explicitly in the report.
2. Simulate the rule change against `analysis/compound_penalized_hospitals_enriched.csv` (872 compound-penalized hospitals) and the relevant mart tables (`fct_hospital_penalty_trajectory`, `fct_hospital_current_performance`). Compute counterfactual penalty exposure per hospital.
3. Produce the full SCENARIO REPORT with all six sections: Policy Change Description, Affected Hospitals, Financial Impact Estimate, Cohort Redistribution, Stakeholder Brief (CMS administrator, hospital CEO, health IT vendor, congressional staffer), Limitations and Assumptions.
4. Reference compound severity score, sales tiers, and intervention priority tiers as they appear in the enriched CSV.
5. Use "correlates with" and "suggests" language only. Label the scenario explicitly as an "untested hypothesis informed by observational data".
6. End with the four stakeholder briefs already written. Do not summarize them away.
