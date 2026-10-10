with current_details as (
    select *
    from {{ ref('sat_product_details') }}
    qualify row_number() over (partition by product_hk order by load_ts desc) = 1
)

select
    h.product_hk,
    h.product_id,
    d.product_name,
    d.category,
    d.list_price
from {{ ref('hub_product') }} as h
left join current_details as d using (product_hk)
