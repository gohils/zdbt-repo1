-- Link: order <-> product, with order_line_id as dependent child key.
select order_line_hk, order_hk, product_hk, order_line_id, load_ts, record_source
from {{ ref('stg_shop_order_lines') }}
where is_valid_bk
qualify row_number() over (partition by order_line_hk order by load_ts) = 1
