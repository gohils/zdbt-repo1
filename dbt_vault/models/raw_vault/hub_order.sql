with candidates as (
    select order_hk, order_id, load_ts, record_source
    from {{ ref('stg_shop_orders') }}
    where is_valid_bk
    union all
    select order_hk, order_id, load_ts, record_source
    from {{ ref('stg_shop_order_lines') }}
    where is_valid_bk
)

select order_hk, order_id, load_ts, record_source
from candidates
qualify row_number() over (partition by order_hk order by load_ts, record_source) = 1
