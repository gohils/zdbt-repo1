# Runbook: dbt Vault Pipeline Failures

## Relationships test fails on a link or satellite
Cause: a hash key in a link or satellite has no matching hub row. Usually the hub model filters rows differently from the link (for example, the hub ignores a source that carries the key). Check that the hub is loaded from every source that carries the business key, and that both use the same `hash_key()` macro and column order.

## Unique test fails on a hub hash key
Cause: the hub is not deduplicated to the first-seen row, or business keys are not cleaned consistently. Check `qualify row_number() over (partition by <hk> order by load_ts) = 1` and that the key is trimmed and upper-cased before hashing.

## Satellite grows on every reload
Cause: the hashdiff changes although attributes did not, typically because a timestamp-of-load or batch column is included in the hashdiff, or columns are hashed in an unstable order. Exclude load metadata from hashdiffs and use the `hash_diff()` macro (sorts columns).

## Source relationships test warns: orders without customer
Cause: late-arriving customers or bad test data. In production, wait for the next CRM batch. In synthetic data, confirm the orphans were deliberate and labelled.

## Query exceeded maximum bytes billed
Cause: a query scans more than the configured cap (`MAX_BYTES_BILLED`). Select fewer columns, filter on load_batch or dates, or ask for a higher cap for that job.

## Embedding or vector search errors in the agent
Cause: the BigQuery connection's service account lacks `roles/aiplatform.user`, or IAM has not propagated yet (wait 1-2 minutes). Re-run `python setup/run_all.py --from-step 5`.
