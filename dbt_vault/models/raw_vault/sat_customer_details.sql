-- Satellite: a new row only when the hashdiff changes for the customer.
-- Exact duplicates in one batch collapse to one row; unchanged reloads add nothing.
with deduped as (
    select *
    from {{ ref('stg_crm_customers') }}
    where is_valid_bk
    qualify row_number() over (partition by customer_hk, load_ts order by customer_hashdiff) = 1
),

changes as (
    select
        *,
        lag(customer_hashdiff) over (partition by customer_hk order by load_ts) as prev_hashdiff
    from deduped
)

select
    customer_hk,
    load_ts,
    customer_hashdiff,
    first_name,
    last_name,
    email,
    segment,
    country,
    created_at,
    is_deleted,
    record_source
from changes
where prev_hashdiff is null or prev_hashdiff != customer_hashdiff
