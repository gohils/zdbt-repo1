-- One row per order line with the current order status.
-- line_amount = quantity * unit_price (glossary: "order value").
with current_orders as (
    select order_hk, order_date, status, currency
    from {{ ref('sat_order_details') }}
    qualify row_number() over (partition by order_hk order by load_ts desc) = 1
),

current_lines as (
    select order_line_hk, quantity, unit_price
    from {{ ref('sat_order_line_details') }}
    qualify row_number() over (partition by order_line_hk order by load_ts desc) = 1
)

select
    ll.order_line_hk,
    ll.order_line_id,
    ho.order_id,
    ll.order_hk,
    lc.customer_hk,
    ll.product_hk,
    o.order_date,
    o.status,
    o.currency,
    l.quantity,
    l.unit_price,
    l.quantity * l.unit_price as line_amount
from {{ ref('link_order_line') }} as ll
join {{ ref('hub_order') }} as ho using (order_hk)
left join {{ ref('link_order_customer') }} as lc using (order_hk)
left join current_orders as o using (order_hk)
left join current_lines as l using (order_line_hk)
