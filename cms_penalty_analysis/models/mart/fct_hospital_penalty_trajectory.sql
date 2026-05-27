-- Fact table: One row per hospital per fiscal year
-- Tracks penalty trajectory with year-over-year metrics

with penalties as (

    select * from {{ ref('stg_hrrp_penalties') }}

),

hospitals as (

    select * from {{ ref('stg_hospital_info') }}

),

trajectory as (

    select
        p.facility_id,
        p.fiscal_year,
        p.payment_adjustment_factor,
        p.penalty_percentage,
        p.is_penalized,
        p.dual_proportion,
        p.peer_group_assignment,
        p.peer_grouping_era,
        p.err_ami,
        p.err_copd,
        p.err_hf,
        p.err_pneumonia,
        p.err_cabg,
        p.err_hip_knee,

        -- Hospital attributes
        h.facility_name,
        h.state,
        h.city,
        h.ownership_category,
        h.star_rating,
        h.census_region,
        h.has_emergency_services,

        -- Year-over-year penalty change
        lag(p.penalty_percentage) over (
            partition by p.facility_id order by p.fiscal_year
        ) as prev_year_penalty_pct,

        lag(p.is_penalized) over (
            partition by p.facility_id order by p.fiscal_year
        ) as prev_year_penalized,

        -- Consecutive penalty streak
        sum(case when p.is_penalized then 1 else 0 end) over (
            partition by p.facility_id
            order by p.fiscal_year
            rows between unbounded preceding and current row
        ) as cumulative_penalties,

        -- Count of years in dataset for this hospital
        count(*) over (
            partition by p.facility_id
        ) as years_in_dataset

    from penalties p
    left join hospitals h
        on p.facility_id = h.facility_id

),

final as (

    select
        *,

        -- Year-over-year change
        penalty_percentage - coalesce(prev_year_penalty_pct, 0) as penalty_pct_change_yoy,

        -- Penalty direction
        case
            when prev_year_penalty_pct is null then 'first_year'
            when penalty_percentage > prev_year_penalty_pct + 0.001 then 'worsening'
            when penalty_percentage < prev_year_penalty_pct - 0.001 then 'improving'
            else 'stable'
        end as penalty_direction,

        -- Average ERR across all conditions
        round((
            coalesce(err_ami, 0) + coalesce(err_copd, 0) + coalesce(err_hf, 0) +
            coalesce(err_pneumonia, 0) + coalesce(err_cabg, 0) + coalesce(err_hip_knee, 0)
        ) / nullif(
            (case when err_ami is not null then 1 else 0 end) +
            (case when err_copd is not null then 1 else 0 end) +
            (case when err_hf is not null then 1 else 0 end) +
            (case when err_pneumonia is not null then 1 else 0 end) +
            (case when err_cabg is not null then 1 else 0 end) +
            (case when err_hip_knee is not null then 1 else 0 end)
        , 0), 4) as avg_excess_readmission_ratio

    from trajectory

)

select * from final