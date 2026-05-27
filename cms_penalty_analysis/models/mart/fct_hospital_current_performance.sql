-- fct_hospital_current_performance.sql
-- One row per hospital: current performance across all dimensions

with hospital_base as (
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
),

spending as (
    select
        facility_id,
        mspb_ratio
    from {{ ref('stg_spending') }}
),

readmissions_agg as (
    select
        facility_id,
        avg(excess_readmission_ratio) as avg_current_err,
        count(*) as readmission_measures_reported,
        sum(case when excess_readmission_ratio > 1.0 then 1 else 0 end) as measures_above_expected
    from {{ ref('stg_readmissions_current') }}
    where excess_readmission_ratio is not null
    group by facility_id
),

complications_agg as (
    select
        facility_id,
        count(*) as complication_measures_reported,
        sum(case when compared_to_national = 'Worse than the National Rate' then 1 else 0 end) as complications_worse_than_national,
        sum(case when compared_to_national = 'Better than the National Rate' then 1 else 0 end) as complications_better_than_national
    from {{ ref('stg_complications') }}
    where compared_to_national is not null
    group by facility_id
),

hac_agg as (
    select
        facility_id,
        count(*) as hac_measures_reported,
        sum(case when compared_to_national = 'Worse than the National Rate' then 1 else 0 end) as hac_worse_than_national,
        avg(score) as avg_hac_score
    from {{ ref('stg_hac') }}
    where score is not null
    group by facility_id
),

payment_agg as (
    select
        facility_id,
        avg(payment_amount) as avg_payment_amount,
        count(distinct payment_measure_id) as payment_measures_reported,
        sum(case when value_of_care_category = 'Worse than the National Rate' then 1 else 0 end) as value_of_care_worse_than_national
    from {{ ref('stg_payment_value') }}
    where payment_amount is not null
    group by facility_id
),

penalty_summary as (
    select
        facility_id,
        max(cumulative_penalties) as total_years_penalized,
        max(years_in_dataset) as total_years_tracked,
        max(case when fiscal_year = 2025 then is_penalized end) as penalized_fy2025,
        max(case when fiscal_year = 2025 then penalty_percentage end) as penalty_pct_fy2025,
        max(case when fiscal_year = 2025 then avg_excess_readmission_ratio end) as avg_err_fy2025,
        case
            when max(cumulative_penalties) = max(years_in_dataset) then 'chronic'
            when max(cumulative_penalties) = 0 then 'never_penalized'
            when max(case when fiscal_year = 2025 then is_penalized end) = false
                 and max(cumulative_penalties) > 0 then 'escaper'
            else 'intermittent'
        end as penalty_cohort
    from {{ ref('fct_hospital_penalty_trajectory') }}
    group by facility_id
)

select
    h.facility_id,
    h.facility_name,
    h.city,
    h.state,
    h.zip_code,
    h.county,
    h.hospital_type,
    h.hospital_ownership,
    h.ownership_category,
    h.star_rating,
    h.has_emergency_services,
    h.census_region,

    -- penalty trajectory
    ps.total_years_penalized,
    ps.total_years_tracked,
    ps.penalized_fy2025,
    ps.penalty_pct_fy2025,
    ps.avg_err_fy2025,
    ps.penalty_cohort,

    -- spending
    s.mspb_ratio,

    -- readmissions
    r.avg_current_err,
    r.readmission_measures_reported,
    r.measures_above_expected,

    -- complications
    c.complication_measures_reported,
    c.complications_worse_than_national,
    c.complications_better_than_national,

    -- HAC
    ha.hac_measures_reported,
    ha.hac_worse_than_national,
    ha.avg_hac_score,

    -- payment & value
    p.avg_payment_amount,
    p.payment_measures_reported,
    p.value_of_care_worse_than_national

from hospital_base h
left join penalty_summary ps on h.facility_id = ps.facility_id
left join spending s on h.facility_id = s.facility_id
left join readmissions_agg r on h.facility_id = r.facility_id
left join complications_agg c on h.facility_id = c.facility_id
left join hac_agg ha on h.facility_id = ha.facility_id
left join payment_agg p on h.facility_id = p.facility_id