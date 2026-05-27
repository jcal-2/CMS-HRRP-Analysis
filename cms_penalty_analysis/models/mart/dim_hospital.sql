-- dim_hospital.sql
-- One row per hospital: static attributes only
-- Separates "who is this hospital" from "how is it performing"

select
    facility_id,
    facility_name,
    city,
    state,
    zip_code,
    county,
    hospital_type,
    hospital_ownership,
    ownership_category,
    star_rating,
    has_emergency_services,
    census_region
from {{ ref('stg_hospital_info') }}