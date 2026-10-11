"""Step 2: generate the baseline fake source data and load it into BigQuery.

Three load batches with inserts, attribute changes, unchanged reloads,
soft deletes and order status transitions, so the vault has real history.
Deterministic: the same seed always produces the same data.

Run with --dry-run to generate and summarise without loading.
"""

from __future__ import annotations

import argparse
import random
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from faker import Faker
from google.cloud import bigquery

from _common import get_settings, info, step

SEED = 42
BATCHES = {
    1: datetime(2026, 1, 5, 2, 0, tzinfo=timezone.utc),
    2: datetime(2026, 2, 5, 2, 0, tzinfo=timezone.utc),
    3: datetime(2026, 3, 5, 2, 0, tzinfo=timezone.utc),
}
ORDER_WINDOWS = {  # order dates delivered in each batch
    1: (date(2025, 12, 1), date(2026, 1, 4)),
    2: (date(2026, 1, 5), date(2026, 2, 4)),
    3: (date(2026, 2, 5), date(2026, 3, 4)),
}
SEGMENTS = (["CONSUMER"] * 70) + (["SMALL_BUSINESS"] * 22) + (["ENTERPRISE"] * 8)
COUNTRIES = ["GB", "GB", "GB", "DE", "FR", "US", "US", "AU", "IN"]
CURRENCY = {"GB": "GBP", "DE": "EUR", "FR": "EUR", "US": "USD", "AU": "USD", "IN": "USD"}
CATEGORIES = ["ELECTRONICS", "HOME", "GARDEN", "SPORTS", "BOOKS"]

SCHEMAS = {
    "crm_customers": [
        ("customer_id", "STRING"), ("first_name", "STRING"), ("last_name", "STRING"),
        ("email", "STRING"), ("segment", "STRING"), ("country", "STRING"),
        ("created_at", "TIMESTAMP"), ("is_deleted", "BOOL"),
        ("load_batch", "INT64"), ("load_ts", "TIMESTAMP"),
    ],
    "shop_products": [
        ("product_id", "STRING"), ("product_name", "STRING"), ("category", "STRING"),
        ("list_price", "NUMERIC"), ("load_batch", "INT64"), ("load_ts", "TIMESTAMP"),
    ],
    "shop_orders": [
        ("order_id", "STRING"), ("customer_id", "STRING"), ("order_date", "DATE"),
        ("status", "STRING"), ("currency", "STRING"),
        ("load_batch", "INT64"), ("load_ts", "TIMESTAMP"),
    ],
    "shop_order_lines": [
        ("order_line_id", "STRING"), ("order_id", "STRING"), ("product_id", "STRING"),
        ("quantity", "INT64"), ("unit_price", "NUMERIC"),
        ("load_batch", "INT64"), ("load_ts", "TIMESTAMP"),
    ],
}


def generate() -> dict[str, list[dict]]:
    rnd = random.Random(SEED)
    fake = Faker("en_GB")
    Faker.seed(SEED)

    tables: dict[str, list[dict]] = {k: [] for k in SCHEMAS}
    ts = lambda b: BATCHES[b].isoformat()  # noqa: E731

    # ---------------------------------------------------------------- products
    products: dict[str, dict] = {}
    for i in range(1, 41):
        pid = f"P{i:04d}"
        products[pid] = {
            "product_id": pid,
            "product_name": fake.unique.catch_phrase()[:60],
            "category": rnd.choice(CATEGORIES),
            "list_price": Decimal(rnd.randint(500, 50000)) / 100,
        }
        tables["shop_products"].append({**products[pid], "load_batch": 1, "load_ts": ts(1)})
    for pid in rnd.sample(sorted(products), 6):  # price changes in batch 3
        products[pid]["list_price"] = (products[pid]["list_price"] * Decimal("1.10")).quantize(Decimal("0.01"))
        tables["shop_products"].append({**products[pid], "load_batch": 3, "load_ts": ts(3)})

    # ---------------------------------------------------------------- customers
    customers: dict[str, dict] = {}

    def new_customer(n: int, created: datetime) -> dict:
        first, last = fake.first_name(), fake.last_name()
        return {
            "customer_id": f"C{n:06d}",
            "first_name": first,
            "last_name": last,
            "email": f"{first}.{last}{n}@example.com".lower().replace(" ", "").replace("'", ""),
            "segment": rnd.choice(SEGMENTS),
            "country": rnd.choice(COUNTRIES),
            "created_at": created,
            "is_deleted": False,
        }

    def emit_customer(c: dict, batch: int) -> None:
        tables["crm_customers"].append(
            {**c, "created_at": c["created_at"].isoformat(), "load_batch": batch, "load_ts": ts(batch)}
        )

    def random_created(start: date, end: date) -> datetime:
        d = start + timedelta(days=rnd.randint(0, (end - start).days))
        return datetime(d.year, d.month, d.day, rnd.randint(8, 18), rnd.randint(0, 59), tzinfo=timezone.utc)

    # batch 1: 300 customers
    for n in range(1, 301):
        customers[f"C{n:06d}"] = new_customer(n, random_created(date(2025, 1, 1), date(2025, 12, 15)))
        emit_customer(customers[f"C{n:06d}"], 1)

    def change_some(batch: int, n_updates: int, n_reloads: int, n_deletes: int) -> None:
        active = [k for k, v in customers.items() if not v["is_deleted"]]
        picked = rnd.sample(active, n_updates + n_reloads + n_deletes)
        updates, reloads, deletes = (
            picked[:n_updates],
            picked[n_updates:n_updates + n_reloads],
            picked[n_updates + n_reloads:],
        )
        for cid in updates:
            c = customers[cid]
            what = rnd.choice(["segment", "email", "country"])
            if what == "segment":
                c["segment"] = rnd.choice([s for s in sorted(set(SEGMENTS)) if s != c["segment"]])
            elif what == "email":
                c["email"] = c["email"].replace("@example.com", f".{batch}@example.org")
            else:
                c["country"] = rnd.choice([x for x in sorted(set(COUNTRIES)) if x != c["country"]])
            emit_customer(c, batch)
        for cid in reloads:  # identical data delivered again: must not create sat rows
            emit_customer(customers[cid], batch)
        for cid in deletes:
            customers[cid]["is_deleted"] = True
            emit_customer(customers[cid], batch)

    # batch 2: 60 new, 40 updates, 10 unchanged reloads
    for n in range(301, 361):
        customers[f"C{n:06d}"] = new_customer(n, random_created(date(2026, 1, 5), date(2026, 1, 25)))
        emit_customer(customers[f"C{n:06d}"], 2)
    change_some(2, n_updates=40, n_reloads=10, n_deletes=0)

    # batch 3: 40 new, 30 updates, 8 reloads, 5 soft deletes
    for n in range(361, 401):
        customers[f"C{n:06d}"] = new_customer(n, random_created(date(2026, 2, 5), date(2026, 2, 20)))
        emit_customer(customers[f"C{n:06d}"], 3)
    change_some(3, n_updates=30, n_reloads=8, n_deletes=5)

    # ---------------------------------------------------------------- orders
    orders: dict[str, dict] = {}
    order_seq = 0

    def progress_status(status: str) -> str:
        r = rnd.random()
        if status == "CREATED":
            return "PAID" if r < 0.6 else ("CANCELLED" if r < 0.7 else "CREATED")
        if status == "PAID":
            return "SHIPPED" if r < 0.8 else "PAID"
        return status

    for batch, (start, end) in ORDER_WINDOWS.items():
        # status changes of existing open orders are delivered again
        for oid, o in orders.items():
            new_status = progress_status(o["status"])
            if new_status != o["status"]:
                o["status"] = new_status
                tables["shop_orders"].append({**o, "order_date": o["order_date"].isoformat(),
                                              "load_batch": batch, "load_ts": ts(batch)})
        # new orders
        eligible = [c for c in customers.values()
                    if not c["is_deleted"] and c["created_at"].date() <= end]
        for _ in range({1: 250, 2: 300, 3: 320}[batch]):
            c = rnd.choice(eligible)
            earliest = max(start, c["created_at"].date())
            order_date = earliest + timedelta(days=rnd.randint(0, (end - earliest).days))
            order_seq += 1
            oid = f"O{order_seq:07d}"
            r = rnd.random()
            status = "CREATED" if r < 0.2 else "PAID" if r < 0.5 else "SHIPPED" if r < 0.95 else "CANCELLED"
            orders[oid] = {
                "order_id": oid,
                "customer_id": c["customer_id"],
                "order_date": order_date,
                "status": status,
                "currency": CURRENCY[c["country"]],
            }
            tables["shop_orders"].append({**orders[oid], "order_date": order_date.isoformat(),
                                          "load_batch": batch, "load_ts": ts(batch)})
            for line_no in range(1, rnd.randint(1, 5) + 1):
                p = products[rnd.choice(sorted(products))]
                tables["shop_order_lines"].append({
                    "order_line_id": f"{oid}-{line_no}",
                    "order_id": oid,
                    "product_id": p["product_id"],
                    "quantity": rnd.randint(1, 5),
                    "unit_price": p["list_price"],
                    "load_batch": batch,
                    "load_ts": ts(batch),
                })

    # JSON-friendly values
    for rows in tables.values():
        for row in rows:
            for k, v in row.items():
                if isinstance(v, Decimal):
                    row[k] = str(v)
    return tables


def summarise(tables: dict[str, list[dict]]) -> None:
    for name, rows in tables.items():
        batches = sorted({r["load_batch"] for r in rows})
        info(f"{name}: {len(rows)} rows across batches {batches}")
    cust = tables["crm_customers"]
    info(f"expected hub_customer rows: {len({r['customer_id'] for r in cust})}")
    info(f"expected hub_order rows: {len({r['order_id'] for r in tables['shop_orders']})}")
    info(f"expected hub_product rows: {len({r['product_id'] for r in tables['shop_products']})}")


def load(tables: dict[str, list[dict]]) -> None:
    from de_context.bq import client

    s = get_settings()
    for name, rows in tables.items():
        schema = [bigquery.SchemaField(col, typ) for col, typ in SCHEMAS[name]]
        job_config = bigquery.LoadJobConfig(
            schema=schema,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        )
        table_id = f"{s.project}.{s.source_dataset}.{name}"
        client().load_table_from_json(rows, table_id, job_config=job_config).result()
        info(f"loaded {table_id}")


def main(dry_run: bool = False) -> None:
    step("Step 2: generate and load baseline source data")
    tables = generate()
    summarise(tables)
    if not dry_run:
        load(tables)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="generate and summarise only")
    main(parser.parse_args().dry_run)
