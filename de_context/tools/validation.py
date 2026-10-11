"""Data validation tools for synthetic source data and the Data Vault built from it.

All queries are fixed; the agent only chooses which allowed dataset to check.
"""

from __future__ import annotations

from typing import Any

from ..bq import run_query
from ..config import get_settings

SOURCE_TABLES = {
    "crm_customers": "customer_id",
    "shop_products": "product_id",
    "shop_orders": "order_id",
    "shop_order_lines": "order_line_id",
}


def _allowed(dataset: str, options: list[str]) -> str | None:
    return None if dataset in options else f"dataset must be one of: {', '.join(options)}"


def profile_source_tables(dataset: str = "") -> dict[str, Any]:
    """Profiles the four source tables: volumes, keys, duplicates, orphans and history.

    Use after generating synthetic data to compare what was generated with
    what you intended (expected counts and edge cases).

    Args:
        dataset: Dataset holding crm_customers, shop_products, shop_orders and
            shop_order_lines. Defaults to the sandbox dataset.

    Returns:
        A dict with per-table metrics and referential integrity metrics.
    """
    s = get_settings()
    dataset = dataset or s.sandbox_dataset
    err = _allowed(dataset, [s.sandbox_dataset, s.source_dataset])
    if err:
        return {"status": "ERROR", "error_details": err}
    t = lambda name: s.table(dataset, name)  # noqa: E731

    try:
        tables = {}
        for table, key in SOURCE_TABLES.items():
            rows = run_query(
                f"""
                SELECT
                  COUNT(*) AS row_count,
                  COUNT(DISTINCT load_batch) AS load_batches,
                  COUNT(DISTINCT {key}) AS distinct_keys,
                  COUNTIF({key} IS NULL OR TRIM({key}) = '') AS null_or_blank_keys,
                  (SELECT COUNT(*) FROM (
                     SELECT {key}, load_batch FROM {t(table)}
                     WHERE {key} IS NOT NULL
                     GROUP BY {key}, load_batch HAVING COUNT(*) > 1)) AS duplicate_keys_within_batch,
                  COUNTIF({key} != TRIM({key}) OR {key} != UPPER({key})) AS keys_with_case_or_whitespace_variation
                FROM {t(table)}
                """,
                label="validate-source",
            )
            tables[table] = rows[0]

        ri = run_query(
            f"""
            SELECT
              (SELECT COUNT(*) FROM {t('shop_orders')} o
                WHERE o.customer_id IS NOT NULL AND NOT EXISTS (
                  SELECT 1 FROM {t('crm_customers')} c
                  WHERE UPPER(TRIM(c.customer_id)) = UPPER(TRIM(o.customer_id)))) AS orders_without_customer,
              (SELECT COUNT(*) FROM {t('shop_order_lines')} l
                WHERE NOT EXISTS (SELECT 1 FROM {t('shop_orders')} o
                  WHERE UPPER(TRIM(o.order_id)) = UPPER(TRIM(l.order_id)))) AS lines_without_order,
              (SELECT COUNT(*) FROM {t('shop_order_lines')} l
                WHERE NOT EXISTS (SELECT 1 FROM {t('shop_products')} p
                  WHERE UPPER(TRIM(p.product_id)) = UPPER(TRIM(l.product_id)))) AS lines_without_product,
              (SELECT COUNT(*) FROM {t('shop_orders')} o
                JOIN {t('crm_customers')} c
                  ON UPPER(TRIM(c.customer_id)) = UPPER(TRIM(o.customer_id))
                WHERE o.order_date < DATE(c.created_at)) AS orders_before_customer_created,
              (SELECT COUNT(*) FROM (
                 SELECT customer_id FROM {t('crm_customers')}
                 GROUP BY customer_id
                 HAVING COUNT(DISTINCT TO_JSON_STRING(STRUCT(first_name, last_name, email, segment, country, is_deleted))) > 1
              )) AS customers_with_attribute_changes,
              (SELECT COUNTIF(is_deleted) FROM {t('crm_customers')}) AS soft_deleted_customer_rows
            """,
            label="validate-source",
        )[0]
    except Exception as exc:
        return {"status": "ERROR", "error_details": str(exc)[:500]}

    return {"status": "SUCCESS", "dataset": dataset, "tables": tables, "integrity": ri}


HUBS = {"hub_customer": "customer_hk", "hub_order": "order_hk", "hub_product": "product_hk"}
LINKS = {
    "link_order_customer": {"order_hk": "hub_order", "customer_hk": "hub_customer"},
    "link_order_line": {"order_hk": "hub_order", "product_hk": "hub_product"},
}
SATS = {
    "sat_customer_details": ("customer_hk", "customer_hashdiff", "hub_customer"),
    "sat_order_details": ("order_hk", "order_hashdiff", "hub_order"),
    "sat_product_details": ("product_hk", "product_hashdiff", "hub_product"),
    "sat_order_line_details": ("order_line_hk", "order_line_hashdiff", "link_order_line"),
}


def validate_vault(dataset: str = "") -> dict[str, Any]:
    """Runs Data Vault integrity checks on hubs, links and satellites.

    Checks: hub keys unique and not null, links point to existing hub keys,
    satellites point to existing parents, and no satellite row repeats the
    previous hashdiff for the same key (an unchanged reload must not create
    a new satellite row). Also returns row counts to compare with expected
    counts.

    Args:
        dataset: Vault dataset to check. Defaults to the sandbox vault dataset.

    Returns:
        A dict with 'checks' (name, value, expected, result) and 'row_counts'.
    """
    s = get_settings()
    dataset = dataset or s.sandbox_vault_dataset
    err = _allowed(dataset, [s.sandbox_vault_dataset, s.vault_dataset])
    if err:
        return {"status": "ERROR", "error_details": err}
    t = lambda name: s.table(dataset, name)  # noqa: E731

    checks: list[dict[str, Any]] = []
    counts: dict[str, int] = {}

    def add(name: str, value: int, expected: int = 0) -> None:
        checks.append(
            {"check": name, "value": value, "expected": expected,
             "result": "PASS" if value == expected else "FAIL"}
        )

    try:
        for hub, hk in HUBS.items():
            r = run_query(
                f"""
                SELECT COUNT(*) AS n,
                       COUNT(*) - COUNT(DISTINCT {hk}) AS dup,
                       COUNTIF({hk} IS NULL) AS nulls
                FROM {t(hub)}
                """,
                label="validate-vault",
            )[0]
            counts[hub] = r["n"]
            add(f"{hub}: duplicate {hk}", r["dup"])
            add(f"{hub}: null {hk}", r["nulls"])

        for link, refs in LINKS.items():
            counts[link] = run_query(f"SELECT COUNT(*) AS n FROM {t(link)}", label="validate-vault")[0]["n"]
            for col, hub in refs.items():
                r = run_query(
                    f"""
                    SELECT COUNT(*) AS orphans FROM {t(link)} l
                    WHERE NOT EXISTS (SELECT 1 FROM {t(hub)} h WHERE h.{col} = l.{col})
                    """,
                    label="validate-vault",
                )[0]
                add(f"{link}: {col} missing in {hub}", r["orphans"])

        for sat, (key, hashdiff, parent) in SATS.items():
            r = run_query(
                f"""
                WITH ordered AS (
                  SELECT {key}, {hashdiff},
                         LAG({hashdiff}) OVER (PARTITION BY {key} ORDER BY load_ts) AS prev
                  FROM {t(sat)}
                )
                SELECT
                  (SELECT COUNT(*) FROM {t(sat)}) AS n,
                  COUNTIF(prev = {hashdiff}) AS repeated_hashdiff,
                  (SELECT COUNT(*) FROM {t(sat)} s
                   WHERE NOT EXISTS (SELECT 1 FROM {t(parent)} p WHERE p.{key} = s.{key})) AS orphans
                FROM ordered
                """,
                label="validate-vault",
            )[0]
            counts[sat] = r["n"]
            add(f"{sat}: row repeats previous hashdiff (unchanged reload stored)", r["repeated_hashdiff"])
            add(f"{sat}: {key} missing in {parent}", r["orphans"])
    except Exception as exc:
        return {"status": "ERROR", "error_details": str(exc)[:500]}

    failed = [c for c in checks if c["result"] == "FAIL"]
    return {
        "status": "SUCCESS",
        "dataset": dataset,
        "summary": f"{len(checks) - len(failed)} of {len(checks)} checks passed",
        "checks": checks,
        "row_counts": counts,
    }


def save_generator_script(name: str, sql: str) -> dict[str, Any]:
    """Saves a synthetic data generator SQL script so it can be reviewed,
    committed and re-run.

    Args:
        name: Short file name without extension, e.g. 'customers_orders_v1'.
        sql: The full generator SQL (one or more statements).

    Returns:
        A dict with the saved file path.
    """
    s = get_settings()
    safe = "".join(ch for ch in name if ch.isalnum() or ch in "_-")[:60] or "generator"
    s.generated_dir.mkdir(parents=True, exist_ok=True)
    path = s.generated_dir / f"{safe}.sql"
    path.write_text(sql.strip() + "\n", encoding="utf-8")
    return {"status": "SUCCESS", "path": str(path)}
