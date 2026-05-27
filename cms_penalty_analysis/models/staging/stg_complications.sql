with source as (
    select * from {{ source('cms_raw_current', 'raw_complications') }}
),

final as (
    select
        cast(facility_id as string) as facility_id,
        facility_name,
        state,
        measure_id,
        measure_name,
        compared_to_national,
        safe_cast(denominator as int64) as denominator,
        safe_cast(score as float64) as score,
        safe_cast(lower_estimate as float64) as lower_estimate,
        safe_cast(higher_estimate as float64) as higher_estimate
    from source
    where facility_id is not null
)

select * from final