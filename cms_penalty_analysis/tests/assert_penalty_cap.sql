select
    facility_id,
    fiscal_year,
    payment_adjustment_factor
from {{ ref('stg_hrrp_penalties') }}
where payment_adjustment_factor < 0.97
    and fiscal_year >= 2016