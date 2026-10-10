-- Staging for CRM customers: hash keys, hashdiff and load metadata.
-- One row per source row; deduplication happens in the raw vault.
with src as (
    select * from {{ source('crm', 'crm_customers') }}
)

select
    {{ hash_key('customer_id') }}                         as customer_hk,
    {{ clean_bk('customer_id') }}                         as customer_id,
    {{ is_valid_bk('customer_id') }}                      as is_valid_bk,
    first_name,
    last_name,
    email,
    segment,
    country,
    created_at,
    coalesce(is_deleted, false)                           as is_deleted,
    {{ hash_diff(['first_name', 'last_name', 'email', 'segment', 'country', 'created_at', 'is_deleted']) }}
                                                          as customer_hashdiff,
    load_batch,
    load_ts,
    'crm.crm_customers'                                   as record_source
from src
