-- Current view of each customer plus order activity.
-- is_active follows the glossary definition of "active customer":
-- not deleted AND at least one order in the 90 days before the latest order date.
with current_details as (
    select *
    from {{ ref('sat_customer_details') }}
    qualify row_number() over (partition by customer_hk order by load_ts desc) = 1
),

current_orders as (
    select order_hk, order_date, status
    from {{ ref('sat_order_details') }}
    qualify row_number() over (partition by order_hk order by load_ts desc) = 1
),

order_activity as (
    select
        l.customer_hk,
        min(o.order_date) as first_order_date,
        max(o.order_date) as last_order_date,
        count(distinct l.order_hk) as order_count
    from {{ ref('link_order_customer') }} as l
    join current_orders as o using (order_hk)
    where o.status != 'CANCELLED'
    group by l.customer_hk
),

reference_date as (
    select max(order_date) as max_order_date from current_orders
)

select
    h.customer_hk,
    h.customer_id,
    d.first_name,
    d.last_name,
    d.email,
    d.segment,
    d.country,
    d.created_at,
    coalesce(d.is_deleted, false)                 as is_deleted,
    a.first_order_date,
    a.last_order_date,
    coalesce(a.order_count, 0)                    as order_count,
    (
        not coalesce(d.is_deleted, false)
        and a.last_order_date >= date_sub(r.max_order_date, interval 90 day)
    )                                             as is_active
from {{ ref('hub_customer') }} as h
left join current_details as d using (customer_hk)
left join order_activity as a using (customer_hk)
cross join reference_date as r
