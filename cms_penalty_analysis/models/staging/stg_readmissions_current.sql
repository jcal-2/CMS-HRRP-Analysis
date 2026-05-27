with source as (
    select * from {{ source('cms_raw_current', 'raw_readmissions') }}
),

final as (
    select
        cast(facility_id as string) as facility_id,
        facility_name,
        state,
        measure_name,
        safe_cast(number_of_discharges as int64) as number_of_discharges,
        safe_cast(excess_readmission_ratio as float64) as excess_readmission_ratio,
        safe_cast(predicted_readmission_rate as float64) as predicted_readmission_rate,
        safe_cast(expected_readmission_rate as float64) as expected_readmission_rate,
        safe_cast(number_of_readmissions as int64) as number_of_readmissions
    from source
    where facility_id is not null
)

select * from final