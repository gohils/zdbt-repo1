with src as (
    select * from {{ source('shop', 'shop_order_lines') }}
)

select
    {{ hash_key(['order_id', 'product_id', 'order_line_id']) }} as order_line_hk,
    {{ hash_key('order_id') }}                            as order_hk,
    {{ hash_key('product_id') }}                          as product_hk,
    {{ clean_bk('order_line_id') }}                       as order_line_id,
    {{ clean_bk('order_id') }}                            as order_id,
    {{ clean_bk('product_id') }}                          as product_id,
    {{ is_valid_bk('order_id') }} and {{ is_valid_bk('product_id') }}
        and {{ is_valid_bk('order_line_id') }}            as is_valid_bk,
    quantity,
    unit_price,
    {{ hash_diff(['quantity', 'unit_price']) }}           as order_line_hashdiff,
    load_batch,
    load_ts,
    'shop.shop_order_lines'                               as record_source
from src
