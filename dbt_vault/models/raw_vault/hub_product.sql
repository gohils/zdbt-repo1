with candidates as (
    select product_hk, product_id, load_ts, record_source
    from {{ ref('stg_shop_products') }}
    where is_valid_bk
    union all
    select product_hk, product_id, load_ts, record_source
    from {{ ref('stg_shop_order_lines') }}
    where is_valid_bk
)

select product_hk, product_id, load_ts, record_source
from candidates
qualify row_number() over (partition by product_hk order by load_ts, record_source) = 1
