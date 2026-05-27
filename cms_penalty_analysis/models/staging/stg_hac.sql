with source as (
    select * from {{ source('cms_raw_current', 'raw_hac') }}
),

final as (
    select
        cast(facility_id as string) as facility_id,
        facility_name,
        state,
        measure_id,
        measure_name,
        compared_to_national,
        safe_cast(score as float64) as score
    from source
    where facility_id is not null
)

select * from final