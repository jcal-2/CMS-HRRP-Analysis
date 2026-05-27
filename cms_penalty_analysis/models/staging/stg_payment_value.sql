with source as (
    select * from {{ source('cms_raw_current', 'raw_payment_value') }}
),

final as (
    select
        cast(facility_id as string) as facility_id,
        facility_name,
        state,
        payment_measure_id,
        payment_measure_name,
        payment_category,
        safe_cast(denominator as int64) as denominator,
        safe_cast(replace(replace(payment, '$', ''), ',', '') as float64) as payment_amount,
        value_of_care_display_id,
        value_of_care_display_name,
        value_of_care_category
    from source
    where facility_id is not null
)

select * from final