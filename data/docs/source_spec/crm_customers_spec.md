# Source Interface Spec: CRM Customers

## Overview
- System: CRM. Table: `crm_customers` in the source dataset.
- Delivery: one file per load batch. A customer is delivered when created, when any attribute changes, and sometimes again unchanged (full reloads).
- Business key: `customer_id`, format `C` followed by 6 digits (e.g. `C000123`). The CRM occasionally sends keys in lower case or with spaces; they identify the same customer.

## Columns
- `customer_id` STRING: customer number (business key).
- `first_name`, `last_name` STRING: customer name.
- `email` STRING: email address; changes when the customer updates their profile.
- `segment` STRING: one of `CONSUMER`, `SMALL_BUSINESS`, `ENTERPRISE`. Customers can move between segments.
- `country` STRING: ISO 3166-1 alpha-2 code (e.g. `GB`, `DE`, `FR`, `US`, `AU`, `IN`).
- `created_at` TIMESTAMP: creation time in the CRM; never changes.
- `is_deleted` BOOL: soft-delete flag; deletions are delivered as a final version with `is_deleted = TRUE`.
- `load_batch` INT64, `load_ts` TIMESTAMP: batch metadata.

## Typical volumes
- About 300 customers in the first batch, then 40-60 new customers per batch.
- About 10-15% of existing customers change at least one attribute per batch.
- Segment mix: roughly 70% CONSUMER, 22% SMALL_BUSINESS, 8% ENTERPRISE.

## Data quality notes
- Duplicate rows for the same customer can occur within one batch after CRM retries.
- Blank customer numbers have been seen in test exports and must be rejected.
