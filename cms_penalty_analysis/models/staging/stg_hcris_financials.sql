{% set fiscal_years = [2022, 2023, 2024, 2025] %}

with rpt as (

    {% for fy in fiscal_years %}
    select
        rpt_rec_num,
        prvdr_num as facility_id,
        fy_bgn_dt,
        fy_end_dt,
        '{{ fy }}' as hcris_receipt_fy
    from {{ source('cms_raw_costreports', 'raw_hcris_rpt_fy' ~ fy) }}
    {% if not loop.last %}union all{% endif %}
    {% endfor %}

),

nmrc as (

    {% for fy in fiscal_years %}
    select * from {{ source('cms_raw_costreports', 'raw_hcris_nmrc_fy' ~ fy) }}
    {% if not loop.last %}union all{% endif %}
    {% endfor %}

),

-- Pivot HCRIS long-format facts to one row per cost report.
-- Codes verified against CMS Form 2552-10 (Rev. 17, 01-2022):
--   S-3 Part I, line 14, col 2   -> bed_count
--   S-3 Part I, line 14, col 10  -> fte_employees
--   S-3 Part I, line 14, col 15  -> total_discharges
--   G-3,        line 3,  col 1   -> net_patient_revenue       (= G-3 L1 - L2)
--   G-3,        line 4,  col 1   -> total_operating_expenses  (from G-2 Part II line 43)
-- HCRIS encodes line/col as zero-padded strings ("00300" = line 3); safe_cast
-- to int64 normalizes 5- vs 6-digit padding variants.
facts as (

    select
        rpt_rec_num,
        max(case
            when wksht_cd = 'S300001'
                and safe_cast(line_num as int64) = 1400
                and safe_cast(clmn_num as int64) = 200
            then safe_cast(itm_val_num as numeric)
        end) as bed_count,
        max(case
            when wksht_cd = 'S300001'
                and safe_cast(line_num as int64) = 1400
                and safe_cast(clmn_num as int64) = 1000
            then safe_cast(itm_val_num as numeric)
        end) as fte_employees,
        max(case
            when wksht_cd = 'S300001'
                and safe_cast(line_num as int64) = 1400
                and safe_cast(clmn_num as int64) = 1500
            then safe_cast(itm_val_num as numeric)
        end) as total_discharges,
        max(case
            when wksht_cd = 'G300000'
                and safe_cast(line_num as int64) = 300
                and safe_cast(clmn_num as int64) = 100
            then safe_cast(itm_val_num as numeric)
        end) as net_patient_revenue,
        max(case
            when wksht_cd = 'G300000'
                and safe_cast(line_num as int64) = 400
                and safe_cast(clmn_num as int64) = 100
            then safe_cast(itm_val_num as numeric)
        end) as total_operating_expenses
    from nmrc
    where wksht_cd in ('S300001', 'G300000')
    group by rpt_rec_num

),

final as (

    select
        r.facility_id,
        r.rpt_rec_num,
        r.hcris_receipt_fy,
        parse_date('%m/%d/%Y', r.fy_bgn_dt) as fy_begin_date,
        parse_date('%m/%d/%Y', r.fy_end_dt) as fy_end_date,
        f.bed_count,
        f.fte_employees,
        f.total_discharges,
        f.net_patient_revenue,
        f.total_operating_expenses,
        case
            when f.net_patient_revenue is null or f.net_patient_revenue = 0 then null
            else round((f.net_patient_revenue - f.total_operating_expenses) / f.net_patient_revenue, 4)
        end as operating_margin
    from rpt r
    left join facts f using (rpt_rec_num)
    where r.facility_id is not null

)

select * from final
