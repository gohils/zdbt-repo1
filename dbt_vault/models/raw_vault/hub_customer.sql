-- Hub: one row per customer business key, first time it was seen in ANY source.
-- Orders also carry customer_id, so a customer referenced by an order before the
-- CRM delivers it (late-arriving data) still gets a hub row.
with candidates as (
    select customer_hk, customer_id, load_ts, record_source
    from {{ ref('stg_crm_customers') }}
    where is_valid_bk
    union all
    select customer_hk, customer_id, load_ts, record_source
    from {{ ref('stg_shop_orders') }}
    where is_valid_bk
)

select customer_hk, customer_id, load_ts, record_source
from candidates
qualify row_number() over (partition by customer_hk order by load_ts, record_source) = 1
