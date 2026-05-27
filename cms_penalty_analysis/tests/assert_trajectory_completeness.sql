-- assert_trajectory_completeness.sql
-- No hospital should have more than 10 rows (FY2016-FY2025).
-- More than 10 indicates duplicate records.

select
    facility_id,
    count(*) as year_count
from {{ ref('fct_hospital_penalty_trajectory') }}
group by facility_id
having count(*) > 10