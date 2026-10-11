# Guide: Synthetic Data SQL Patterns (reviewed example)

Reviewed, reusable patterns for generating synthetic source data in BigQuery with deterministic randomness. Use these as the template for new generators.

## Deterministic random numbers
Use a seed string and the row number. The same seed always gives the same data.

```sql
-- integer between 0 and 99, deterministic for (seed, n)
MOD(ABS(FARM_FINGERPRINT(CONCAT('seed-42', '-', CAST(n AS STRING)))), 100)
```

Use a different salt per attribute so attributes are independent:
`FARM_FINGERPRINT(CONCAT(@seed, '-segment-', CAST(n AS STRING)))`.

## Customers (parent) with two batches and updates
```sql
CREATE OR REPLACE TABLE `PROJECT.demo_sandbox.crm_customers` AS
WITH base AS (
  SELECT
    n,
    FORMAT('C%06d', 900000 + n) AS customer_id,
    ['Ava','Liam','Noah','Mia','Zoe','Omar','Ivy','Leo'][OFFSET(MOD(ABS(FARM_FINGERPRINT(CONCAT('s42-fn-', CAST(n AS STRING)))), 8))] AS first_name,
    ['Stone','Rivera','Khan','Novak','Berg','Silva'][OFFSET(MOD(ABS(FARM_FINGERPRINT(CONCAT('s42-ln-', CAST(n AS STRING)))), 6))] AS last_name,
    CASE
      WHEN MOD(ABS(FARM_FINGERPRINT(CONCAT('s42-seg-', CAST(n AS STRING)))), 100) < 70 THEN 'CONSUMER'
      WHEN MOD(ABS(FARM_FINGERPRINT(CONCAT('s42-seg-', CAST(n AS STRING)))), 100) < 92 THEN 'SMALL_BUSINESS'
      ELSE 'ENTERPRISE'
    END AS segment,
    ['GB','DE','FR','US'][OFFSET(MOD(ABS(FARM_FINGERPRINT(CONCAT('s42-cty-', CAST(n AS STRING)))), 4))] AS country,
    TIMESTAMP_ADD(TIMESTAMP '2025-06-01', INTERVAL MOD(ABS(FARM_FINGERPRINT(CONCAT('s42-ca-', CAST(n AS STRING)))), 180) DAY) AS created_at
  FROM UNNEST(GENERATE_ARRAY(1, 100)) AS n
),
with_email AS (
  SELECT *, LOWER(CONCAT(first_name, '.', last_name, CAST(n AS STRING), '@example.com')) AS email
  FROM base
),
batch1 AS (
  SELECT customer_id, first_name, last_name, email, segment, country, created_at,
         FALSE AS is_deleted, 1 AS load_batch, TIMESTAMP '2026-01-05 02:00:00' AS load_ts
  FROM with_email
),
batch2 AS (
  -- every 10th customer changes segment (real change -> new satellite row)
  SELECT customer_id, first_name, last_name, email,
         IF(MOD(n, 10) = 0, IF(segment = 'ENTERPRISE', 'CONSUMER', 'ENTERPRISE'), segment) AS segment,
         country, created_at,
         FALSE AS is_deleted, 2 AS load_batch, TIMESTAMP '2026-02-05 02:00:00' AS load_ts
  FROM with_email
  WHERE MOD(n, 10) = 0      -- 10 updated customers
     OR MOD(n, 25) = 1      -- 4 unchanged reloads (must NOT create satellite rows)
)
SELECT * FROM batch1
UNION ALL
SELECT * FROM batch2;
```

## Children: orders referencing existing customers
Pick the parent by index so every foreign key exists:

```sql
-- inside an orders generator: n = order number, 100 customers exist
FORMAT('C%06d', 900000 + 1 + MOD(ABS(FARM_FINGERPRINT(CONCAT('s42-oc-', CAST(n AS STRING)))), 100)) AS customer_id
```

Keep `order_date >= DATE(created_at)` by joining the chosen customer and adding a positive number of days to its `created_at`.

## Deliberate edge cases (label them)
- Whitespace / case variation: `CONCAT(' ', LOWER(customer_id))` for a few rows.
- Invalid key: `CAST(NULL AS STRING)` or `''` as `customer_id` for 1-2 rows.
- Exact duplicate in a batch: `UNION ALL` the same row twice.
- Late-arriving customer: an order in batch 1 whose customer only appears in batch 2.

## Expected results (write them down before loading)
For the customers example: hub_customer = 100 rows; sat_customer_details = 100 (batch 1) + 10 (segment changes) = 110 rows; the 4 unchanged reloads add 0 rows.
