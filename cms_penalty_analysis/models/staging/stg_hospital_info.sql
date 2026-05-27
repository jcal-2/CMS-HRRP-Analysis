with source as (

    select * from {{ source('cms_raw_current', 'raw_hospital_info') }}

),

final as (

    select
        cast(facility_id as string) as facility_id,
        facility_name,
        citytown as city,
        state,
        zip_code,
        countyparish as county,
        hospital_type,
        hospital_ownership,

        -- Simplify ownership into 3 categories
        case
            when hospital_ownership in ('Voluntary non-profit - Private',
                                         'Voluntary non-profit - Church',
                                         'Voluntary non-profit - Other')
                then 'Non-Profit'
            when hospital_ownership in ('Proprietary')
                then 'For-Profit'
            when hospital_ownership in ('Government - Federal',
                                         'Government - Hospital District or Authority',
                                         'Government - Local',
                                         'Government - State',
                                         'Department of Defense',
                                         'Tribal')
                then 'Government'
            else 'Other'
        end as ownership_category,

        -- Star rating (handle "Not Available")
        case
            when hospital_overall_rating in ('Not Available', '')
                then null
            else cast(hospital_overall_rating as int64)
        end as star_rating,

        case when emergency_services = 'Yes' then true else false end as has_emergency_services,

        -- Census region from state
        case
            when state in ('CT','ME','MA','NH','RI','VT','NJ','NY','PA') then 'Northeast'
            when state in ('IL','IN','MI','OH','WI','IA','KS','MN','MO','NE','ND','SD') then 'Midwest'
            when state in ('DE','FL','GA','MD','NC','SC','VA','DC','WV',
                           'AL','KY','MS','TN','AR','LA','OK','TX') then 'South'
            when state in ('AZ','CO','ID','MT','NV','NM','UT','WY',
                           'AK','CA','HI','OR','WA') then 'West'
            else 'Other'
        end as census_region

    from source
    where hospital_type = 'Acute Care Hospitals'

)

select * from final