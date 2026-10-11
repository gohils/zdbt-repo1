with src as (
    select * from {{ source('shop', 'shop_orders') }}
)

select
    {{ hash_key('order_id') }}                            as order_hk,
    {{ hash_key('customer_id') }}                         as customer_hk,
    {{ hash_key(['order_id', 'customer_id']) }}           as order_customer_hk,
    {{ clean_bk('order_id') }}                            as order_id,
    {{ clean_bk('customer_id') }}                         as customer_id,
    {{ is_valid_bk('order_id') }} and {{ is_valid_bk('customer_id') }} as is_valid_bk,
    order_date,
    status,
    currency,
    {{ hash_diff(['order_date', 'status', 'currency']) }} as order_hashdiff,
    load_batch,
    load_ts,
    'shop.shop_orders'                                    as record_source
from src
