-- FY2016/2017 quirk: the early supplemental files encode "insufficient cases"
-- as a literal 0.0 in the ERR columns, while FY2018+ files leave them NULL.
-- Wrap each ERR in nullif(..., 0) so the trajectory's averaged ERR isn't dragged
-- toward zero by the sentinel. Real ERRs never come close to 0 (FY2018+ minima
-- are ~0.7), so this is unambiguous.
with fy2016 as (
    select
        safe_cast(provider as string) as facility_id,
        safe_cast(fy_2016_readmissions_adjustment_factor as float64) as payment_adjustment_factor,
        safe_cast(null as float64) as dual_proportion,
        safe_cast(null as int64) as peer_group_assignment,
        nullif(safe_cast(acute_myocardial_infarction_excess_readmission_ratio as float64), 0) as err_ami,
        nullif(safe_cast(chronic_obstructive_pulmonary_disease_excess_readmission_ratio as float64), 0) as err_copd,
        nullif(safe_cast(excess_readmission_ratio_for_heart_failure as float64), 0) as err_hf,
        nullif(safe_cast(excess_readmission_ratio_for_pneumonia as float64), 0) as err_pneumonia,
        safe_cast(null as float64) as err_cabg,
        nullif(safe_cast(hip_knee_arthroplasty_excess_readmission_ratio as float64), 0) as err_hip_knee,
        cast(null as string) as penalty_flag_ami,
        cast(null as string) as penalty_flag_copd,
        cast(null as string) as penalty_flag_hf,
        cast(null as string) as penalty_flag_pneumonia,
        cast(null as string) as penalty_flag_cabg,
        cast(null as string) as penalty_flag_hip_knee,
        safe_cast(fiscal_year as int64) as fiscal_year
    from {{ source('cms_raw_historical', 'raw_hrrp_fy2016') }}
),

fy2017 as (
    select
        safe_cast(provider as string) as facility_id,
        safe_cast(fy_2017_readmissions_adjustment_factor as float64) as payment_adjustment_factor,
        safe_cast(null as float64) as dual_proportion,
        safe_cast(null as int64) as peer_group_assignment,
        nullif(safe_cast(acute_myocardial_infarction_excess_readmission_ratio as float64), 0) as err_ami,
        nullif(safe_cast(chronic_obstructive_pulmonary_disease_excess_readmission_ratio as float64), 0) as err_copd,
        nullif(safe_cast(excess_readmission_ratio_for_heart_failure as float64), 0) as err_hf,
        nullif(safe_cast(excess_readmission_ratio_for_pneumoniuia as float64), 0) as err_pneumonia,
        nullif(safe_cast(coronary_artery_bypass_graft_excess_readmission_ratio as float64), 0) as err_cabg,
        nullif(safe_cast(hip_knee_arthroplasty_excess_readmission_ratio as float64), 0) as err_hip_knee,
        cast(null as string) as penalty_flag_ami,
        cast(null as string) as penalty_flag_copd,
        cast(null as string) as penalty_flag_hf,
        cast(null as string) as penalty_flag_pneumonia,
        cast(null as string) as penalty_flag_cabg,
        cast(null as string) as penalty_flag_hip_knee,
        safe_cast(fiscal_year as int64) as fiscal_year
    from {{ source('cms_raw_historical', 'raw_hrrp_fy2017') }}
),

fy2018 as (
    select
        safe_cast(provider as string) as facility_id,
        safe_cast(fy_2018_readmissions_adjustment_factor as float64) as payment_adjustment_factor,
        safe_cast(null as float64) as dual_proportion,
        safe_cast(null as int64) as peer_group_assignment,
        safe_cast(acute_myocardial_infarction_excess_readmission_ratio as float64) as err_ami,
        safe_cast(chronic_obstructive_pulmonary_disease_excess_readmission_ratio as float64) as err_copd,
        safe_cast(excess_readmission_ratio_for_heart_failure as float64) as err_hf,
        safe_cast(excess_readmission_ratio_for_pneumonia as float64) as err_pneumonia,
        safe_cast(coronary_artery_bypass_graft_excess_readmission_ratio as float64) as err_cabg,
        safe_cast(hip_knee_arthroplasty_excess_readmission_ratio as float64) as err_hip_knee,
        cast(null as string) as penalty_flag_ami,
        cast(null as string) as penalty_flag_copd,
        cast(null as string) as penalty_flag_hf,
        cast(null as string) as penalty_flag_pneumonia,
        cast(null as string) as penalty_flag_cabg,
        cast(null as string) as penalty_flag_hip_knee,
        safe_cast(fiscal_year as int64) as fiscal_year
    from {{ source('cms_raw_historical', 'raw_hrrp_fy2018') }}
),

modern_format as (
    {% set modern_years = range(2019, 2026) %}
    {% for year in modern_years %}
    select
        safe_cast(hospital_ccn as string) as facility_id,
        safe_cast(payment_adjustment_factor as float64) as payment_adjustment_factor,
        safe_cast(dual_proportion as float64) as dual_proportion,
        safe_cast(peer_group_assignment as int64) as peer_group_assignment,
        safe_cast(err_for_ami as float64) as err_ami,
        safe_cast(err_for_copd as float64) as err_copd,
        safe_cast(err_for_hf as float64) as err_hf,
        {% if year == 2023 %}
        safe_cast(null as float64) as err_pneumonia,
        {% else %}
        safe_cast(err_for_pneumonia as float64) as err_pneumonia,
        {% endif %}
        safe_cast(err_for_cabg as float64) as err_cabg,
        safe_cast(err_for_tha_tka as float64) as err_hip_knee,
        penalty_indicator_for_ami as penalty_flag_ami,
        penalty_indicator_for_copd as penalty_flag_copd,
        penalty_indicator_for_hf as penalty_flag_hf,
        {% if year == 2023 %}
        cast(null as string) as penalty_flag_pneumonia,
        {% else %}
        penalty_indicator_for_pneumonia as penalty_flag_pneumonia,
        {% endif %}
        penalty_indicator_for_cabg as penalty_flag_cabg,
        penalty_indicator_for_tha_tka as penalty_flag_hip_knee,
        safe_cast(fiscal_year as int64) as fiscal_year
    from {{ source('cms_raw_historical', 'raw_hrrp_fy' ~ year) }}
    {% if not loop.last %}union all{% endif %}
    {% endfor %}
),

combined as (
    select * from fy2016
    union all
    select * from fy2017
    union all
    select * from fy2018
    union all
    select * from modern_format
),

final as (
    select
        *,
        round(1.0 - payment_adjustment_factor, 4) as penalty_percentage,
        case when payment_adjustment_factor < 1.0 then true else false end as is_penalized,
        case
            when fiscal_year >= 2019 then 'post_peer_grouping'
            else 'pre_peer_grouping'
        end as peer_grouping_era
    from combined
    where facility_id is not null
)

select * from final