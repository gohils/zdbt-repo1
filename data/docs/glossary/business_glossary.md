# Business Glossary

## Customer
A person or business registered in the CRM, identified by the CRM customer number (`customer_id`). In the vault: `hub_customer`; current attributes in `dim_customer`.

## Active customer
A customer who is not deleted (`is_deleted = FALSE`) and has at least one non-cancelled order in the 90 days before the latest order date in the data. Implemented as `dim_customer.is_active`.

## Customer segment
Commercial classification of a customer: `CONSUMER`, `SMALL_BUSINESS` or `ENTERPRISE`. Stored in `crm_customers.segment`, historised in `sat_customer_details.segment`, current value in `dim_customer.segment`.

## Order
A purchase placed in the web shop, identified by `order_id`. Header attributes (date, status, currency) are in `sat_order_details`; current status in `fct_order_lines.status`.

## Shipped order
An order whose current status is `SHIPPED`.

## Order value / revenue
Sum of `line_amount` (= `quantity * unit_price`) over order lines, from `fct_order_lines`. Revenue excludes `CANCELLED` orders. Amounts are in the order currency; do not add amounts across currencies without conversion.

## Product
An item sold in the web shop, identified by `product_id`; current attributes in `dim_product`.

## Business key
The identifier the business uses for an entity (customer number, order number, product code). Hash keys in the vault are derived from business keys.
