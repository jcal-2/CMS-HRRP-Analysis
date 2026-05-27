-- No HRRP penalty should exceed 3% (adjustment factor >= 0.97)
-- The 3% cap has been in effect since FY2015

select
    facility_id,
    fiscal_year,
    payment_adjustment_factor,
    penalty_percentage
from {{ ref('stg_hrrp_penalties') }}
where payment_adjustment_factor < 0.97
    and fiscal_year >= 2016