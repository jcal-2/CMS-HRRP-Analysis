-- assert_peer_group_only_post_2019.sql
-- Peer group assignments should only exist FY2019+.
-- Returns rows where pre-2019 data has a non-null peer group (a data error).

select
    facility_id,
    fiscal_year,
    peer_group_assignment
from {{ ref('stg_hrrp_penalties') }}
where fiscal_year < 2019
  and peer_group_assignment is not null