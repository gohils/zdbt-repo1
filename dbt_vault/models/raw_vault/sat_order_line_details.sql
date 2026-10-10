-- Satellite on the order line link.
with deduped as (
    select *
    from {{ ref('stg_shop_order_lines') }}
    where is_valid_bk
    qualify row_number() over (partition by order_line_hk, load_ts order by order_line_hashdiff) = 1
),

changes as (
    select
        *,
        lag(order_line_hashdiff) over (partition by order_line_hk order by load_ts) as prev_hashdiff
    from deduped
)

select order_line_hk, load_ts, order_line_hashdiff, quantity, unit_price, record_source
from changes
where prev_hashdiff is null or prev_hashdiff != order_line_hashdiff
