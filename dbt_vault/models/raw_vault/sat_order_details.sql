with deduped as (
    select *
    from {{ ref('stg_shop_orders') }}
    where is_valid_bk
    qualify row_number() over (partition by order_hk, load_ts order by order_hashdiff) = 1
),

changes as (
    select
        *,
        lag(order_hashdiff) over (partition by order_hk order by load_ts) as prev_hashdiff
    from deduped
)

select order_hk, load_ts, order_hashdiff, order_date, status, currency, record_source
from changes
where prev_hashdiff is null or prev_hashdiff != order_hashdiff
