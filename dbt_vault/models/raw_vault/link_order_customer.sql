-- Link: which customer placed which order. First time the pair was seen.
select order_customer_hk, order_hk, customer_hk, load_ts, record_source
from {{ ref('stg_shop_orders') }}
where is_valid_bk
qualify row_number() over (partition by order_customer_hk order by load_ts) = 1
