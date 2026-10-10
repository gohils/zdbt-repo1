with src as (
    select * from {{ source('shop', 'shop_products') }}
)

select
    {{ hash_key('product_id') }}                          as product_hk,
    {{ clean_bk('product_id') }}                          as product_id,
    {{ is_valid_bk('product_id') }}                       as is_valid_bk,
    product_name,
    category,
    list_price,
    {{ hash_diff(['product_name', 'category', 'list_price']) }} as product_hashdiff,
    load_batch,
    load_ts,
    'shop.shop_products'                                  as record_source
from src
