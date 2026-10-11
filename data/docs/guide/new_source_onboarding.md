# Guide: Onboarding a New Source into the Vault

## Steps
1. Add the source table to `_sources.yml` with column descriptions, data types and `relationships` tests for every foreign key.
2. Identify business keys. Reuse an existing hub when the key identifies the same business entity (for example, any customer number that matches the CRM customer number loads into `hub_customer`). Create a new hub only for a new business entity.
3. Create a staging view `stg_<source_table>` that computes hash keys with `hash_key()`, a hashdiff with `hash_diff()`, and `record_source`.
4. Add the new source as an additional input of the existing hub (union of candidates, first seen wins).
5. Add links for relationships between business keys, and a satellite per source for descriptive attributes (`sat_<entity>_<source>`).
6. Add the mandatory tests (see Data Vault standards) and run `dbt build`.
7. Regenerate the context graph (`python setup/run_all.py --from-step 4`) so agents see the new lineage and relationships.

## Matching keys across sources
If the new source uses a different format for the same key (e.g. `cust_ref = 'c000123 '`), the hashing standard (trim, upper case) makes it hash to the same key. If the format really differs (e.g. no `C` prefix), add a cleaning expression in staging before hashing and document it.
