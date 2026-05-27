-- One row per hospital: most recent HCRIS cost report, preferring full-year reports.
-- Short-period reports (e.g., 2-3 month transitions) produce extreme operating margins
-- because annual fixed costs concentrate against partial revenue; we prefer reports
-- covering >= 300 days but fall back to whatever is most recent if no full-year exists.

with reports as (

    select
        facility_id,
        rpt_rec_num,
        hcris_receipt_fy,
        fy_begin_date,
        fy_end_date,
        bed_count,
        fte_employees,
        total_discharges,
        net_patient_revenue,
        total_operating_expenses,
        operating_margin,
        date_diff(fy_end_date, fy_begin_date, day) as report_period_days
    from {{ ref('stg_hcris_financials') }}
    where fy_begin_date is not null
      and fy_end_date is not null

),

ranked as (

    select
        *,
        row_number() over (
            partition by facility_id
            order by
                case when report_period_days >= 300 then 0 else 1 end,
                fy_end_date desc
        ) as rn
    from reports

),

final as (

    select
        facility_id,
        rpt_rec_num,
        hcris_receipt_fy,
        fy_begin_date,
        fy_end_date,
        report_period_days,
        report_period_days >= 300 as is_full_year_report,
        bed_count,
        fte_employees,
        total_discharges,
        net_patient_revenue,
        total_operating_expenses,
        operating_margin
    from ranked
    where rn = 1

)

select * from final
