-- dim_fiscal_year.sql
-- One row per fiscal year with policy context flags
-- Enables filtering and annotation by policy era

select
    fiscal_year,
    
    -- peer grouping era
    case
        when fiscal_year >= 2019 then true
        else false
    end as has_peer_grouping,

    -- COVID impact period
    case
        when fiscal_year between 2022 and 2024 then true
        else false
    end as covid_affected,

    -- program maturity
    case
        when fiscal_year between 2016 and 2018 then 'early'
        when fiscal_year between 2019 and 2021 then 'peer_grouping_introduced'
        when fiscal_year between 2022 and 2024 then 'covid_era'
        when fiscal_year >= 2025 then 'post_covid'
    end as policy_era,

    -- conditions tracked (CABG added FY2017)
    case
        when fiscal_year = 2016 then 5
        else 6
    end as conditions_measured,

    -- CABG inclusion
    case
        when fiscal_year >= 2017 then true
        else false
    end as includes_cabg

from unnest(generate_array(2016, 2025)) as fiscal_year