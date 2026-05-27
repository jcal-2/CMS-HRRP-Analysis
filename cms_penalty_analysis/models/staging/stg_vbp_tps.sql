-- stg_vbp_tps.sql
-- Hospital Value-Based Purchasing Total Performance Scores

select
    cast(facility_id as string) as facility_id,
    fiscal_year,
    cast(total_performance_score as float64) as total_performance_score,
    cast(weighted_normalized_clinical_outcomes_domain_score as float64) as clinical_outcomes_score,
    cast(weighted_person_and_community_engagement_domain_score as float64) as patient_experience_score,
    cast(weighted_safety_domain_score as float64) as safety_score,
    cast(weighted_efficiency_and_cost_reduction_domain_score as float64) as efficiency_score
from `data-viz-sandbox-495114.cms_raw_current.raw_hvbp_tps`