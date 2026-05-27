with source as (
    select * from {{ source('cms_raw_current', 'raw_spending') }}
),

final as (
    select
        cast(facility_id as string) as facility_id,
        facility_name,
        state,
        safe_cast(score as float64) as mspb_ratio
    from source
    where facility_id is not null
        and score is not null
        and score != 'Not Available'
)

select * from final