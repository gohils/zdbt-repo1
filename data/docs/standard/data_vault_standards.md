# Data Vault Modelling Standards

Team standard for all raw vault models built with dbt. Applies to every hub, link and satellite in the vault datasets.

## Layers and naming
- Staging views: `stg_<source_table>`. Staging adds hash keys, hashdiffs, `record_source` and keeps `load_ts` and `load_batch`. No business logic in staging.
- Hubs: `hub_<business_entity>` (singular, e.g. `hub_customer`).
- Links: `link_<entity1>_<entity2>` (e.g. `link_order_customer`). A link with a dependent child key keeps that key as a column (e.g. `order_line_id` in `link_order_line`).
- Satellites: `sat_<entity>_details`, or `sat_<entity>_<source>` when one entity has several sources.
- Information marts: `dim_<entity>` and `fct_<process>` in the mart dataset. Marts read only from the raw vault, never from staging or sources.

## Hash keys
- Algorithm: MD5. Store as an upper-case hexadecimal string of 32 characters: `UPPER(TO_HEX(MD5(...)))`.
- Before hashing, every business key value is cast to STRING, trimmed (`TRIM`) and upper-cased (`UPPER`). So ` c000123` and `C000123` produce the same hash key.
- NULL or blank values are replaced by the null token `^^` before hashing.
- Composite keys: values are concatenated in the documented key order with the delimiter `||`.
- Hash key column names end in `_hk` (e.g. `customer_hk`). Link hash keys combine all hub business keys of the link, plus the dependent child key if any.
- Always use the dbt macros `hash_key()` and `hash_diff()`. Never hand-write hashing SQL.

## Hashdiffs and change detection
- Every satellite has a hashdiff column named `<entity>_hashdiff`, computed with the same rules as hash keys over all descriptive attributes.
- Hashdiff input columns are sorted alphabetically by column name, so adding the same columns in a different order does not change the hashdiff.
- A satellite stores a new row only when the hashdiff differs from the previous row for the same parent key (ordered by `load_ts`).
- An unchanged reload (the same record delivered again with identical attributes) must NOT create a new satellite row.
- Exact duplicates within one load batch collapse into one satellite row.
- If one batch contains two different versions of the same key (conflicting duplicates), the row with the lowest hashdiff is kept and the conflict is reported to the source owner.

## Business keys
- A business key is invalid when it is NULL or blank after trimming. Rows with invalid business keys are not loaded into hubs, links or satellites; they remain visible in staging (`is_valid_bk = FALSE`) for data quality reporting.
- Hubs store the cleaned business key value (trimmed, upper case).
- A hub is loaded from every source that carries the business key. Example: `hub_customer` is loaded from CRM customers and from web shop orders, so a customer referenced by an order before the CRM delivers it (late-arriving data) still gets a hub row.

## Load metadata
- `load_ts` (TIMESTAMP): when the batch was loaded. Hubs and links keep the first `load_ts` at which the key was seen.
- `record_source` (STRING): `<system>.<table>`, e.g. `crm.crm_customers`.
- `load_batch` (INT64) exists in sources and staging only.

## Deletes
- Deletes in source systems are soft deletes. The CRM sends `is_deleted = TRUE`; this flag is a normal satellite attribute, so a deletion creates a new satellite version.
- Rows are never physically deleted from hubs, links or satellites.

## Mandatory tests
- Every hub: `unique` and `not_null` on the hash key.
- Every link: `unique` and `not_null` on the link hash key, and a `relationships` test from each hub hash key to its hub.
- Every satellite: `relationships` test from the parent hash key to its hub or link.
- Marts: `unique` and `not_null` on the primary key; `relationships` tests to dimensions.
