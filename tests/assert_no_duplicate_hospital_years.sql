-- No hospital should appear more than once in the same fiscal year

select
    facility_id,
    fiscal_year,
    count(*) as record_count
from {{ ref('stg_hrrp_penalties') }}
group by facility_id, fiscal_year
having count(*) > 1