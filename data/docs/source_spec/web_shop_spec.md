# Source Interface Spec: Web Shop (Orders, Order Lines, Products)

## Overview
- System: web shop. Tables: `shop_products`, `shop_orders`, `shop_order_lines` in the source dataset.
- Delivery: batches aligned with the CRM batches.

## shop_products
- Business key `product_id`, format `P` followed by 4 digits (e.g. `P0012`).
- `product_name` STRING, `category` STRING (one of `ELECTRONICS`, `HOME`, `GARDEN`, `SPORTS`, `BOOKS`), `list_price` NUMERIC.
- Products are delivered again when the price or name changes.
- Typical volume: about 40 products.

## shop_orders
- Business key `order_id`, format `O` followed by 7 digits (e.g. `O0000042`).
- `customer_id` STRING: the CRM customer number of the buyer (foreign key to `crm_customers.customer_id`).
- `order_date` DATE: never before the customer's `created_at` date.
- `status` STRING: `CREATED`, `PAID`, `SHIPPED` or `CANCELLED`. Allowed transitions: CREATED -> PAID -> SHIPPED, and CREATED -> CANCELLED. An order is delivered again in a later batch whenever its status changes.
- `currency` STRING: `GBP`, `EUR` or `USD`.
- Typical volume: 1-4 orders per customer.

## shop_order_lines
- `order_line_id` STRING: `<order_id>-<line number>`, e.g. `O0000042-1`.
- `order_id` STRING: foreign key to `shop_orders.order_id`.
- `product_id` STRING: foreign key to `shop_products.product_id`.
- `quantity` INT64 (1-5), `unit_price` NUMERIC (the product's list price at order time).
- Lines are delivered once, in the same batch as the order is created, and never change.
- Typical volume: 1-5 lines per order.

## Known integration points
- Orders link to CRM customers through `customer_id`. Orders can occasionally arrive before the customer record (late-arriving customers).
