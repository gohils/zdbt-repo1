with deduped as (
    select *
    from {{ ref('stg_shop_products') }}
    where is_valid_bk
    qualify row_number() over (partition by product_hk, load_ts order by product_hashdiff) = 1
),

changes as (
    select
        *,
        lag(product_hashdiff) over (partition by product_hk order by load_ts) as prev_hashdiff
    from deduped
)

select product_hk, load_ts, product_hashdiff, product_name, category, list_price, record_source
from changes
where prev_hashdiff is null or prev_hashdiff != product_hashdiff
