# Synthetic Test Data Policy

## Purpose
Synthetic data lets developers test dbt Data Vault loads and downstream models end to end without production data.

## Data handling rules
- Generate fake values only. Never copy, sample or transform production rows.
- Names: invented. Emails: only `@example.com`, `@example.org` or `@example.net` domains. No real phone numbers or addresses.
- Aggregated production profiles (row counts, null rates, value frequencies) may be used only if approved by the data owner.

## Where synthetic data lives
- Synthetic source tables are written only to the sandbox dataset (`demo_sandbox`), using the same table names and columns as the real source dataset.
- The sandbox vault is built by dbt into `demo_sandbox_vault`.
- Sandbox tables expire automatically after 7 days.

## Generate at the source layer
- Generate source-shaped tables, then build the vault with the normal dbt project. Do not write directly into hubs, links or satellites; that would bypass hashing and change detection, which is what we want to test.

## Reproducibility
- Generators are SQL scripts saved in Git. Randomness must be deterministic: derive values from `FARM_FINGERPRINT(CONCAT(<seed>, ...))` so the same seed produces the same data.
- Every generator states its seed, volumes, number of batches and the edge cases it includes.

## Referential integrity
- Generate parents before children: customers and products first, then orders, then order lines.
- Every foreign key must point to an existing parent unless a row is a deliberate, labelled orphan for a negative test.
- Child dates never precede parent dates (order_date >= customer created_at date).

## Edge cases to cover (pick per test)
- Several load batches with inserts, attribute updates and unchanged reloads.
- Soft deletes (`is_deleted = TRUE`).
- Exact duplicates within a batch.
- Business keys with lower case or surrounding whitespace (must hash to the same key).
- NULL or blank business keys (must be excluded from the vault).
- Late-arriving data: an order referencing a customer that only arrives in a later batch.
- Order status transitions across batches: CREATED -> PAID -> SHIPPED, or CREATED -> CANCELLED.

## Expected results manifest
Every generator run states the expected counts, for example: distinct valid customer keys (= hub_customer rows), satellite rows per entity (= number of real changes), and number of deliberate orphans or invalid keys.
