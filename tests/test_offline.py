"""Offline checks (no Google Cloud access needed):

    GOOGLE_CLOUD_PROJECT=dummy pytest tests
    (run `cd dbt_vault && dbt parse` first for the manifest-based tests)
"""

import importlib.util
import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "dummy-project")
ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "dbt_vault" / "target" / "manifest.json"


def _load(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sandbox_guard():
    from de_context.tools.sandbox_guard import check_statement

    allowed = {"demo_sandbox"}
    assert check_statement("SELECT 1", allowed) is None
    assert check_statement("CREATE OR REPLACE TABLE `p.demo_sandbox.t` AS SELECT 1", allowed) is None
    assert check_statement("INSERT INTO demo_sandbox.t SELECT 1", allowed) is None
    assert check_statement("CREATE OR REPLACE TABLE p.demo_vault.hub_customer AS SELECT 1", allowed)
    assert check_statement("DROP TABLE demo_source.crm_customers", allowed)
    assert check_statement("DROP SCHEMA demo_sandbox", allowed)
    assert check_statement("CREATE TABLE t AS SELECT 1", allowed)
    assert check_statement("CREATE TABLE demo_sandbox.a AS SELECT 1; DROP TABLE demo_vault.x", allowed)


def test_source_data_is_deterministic_and_consistent():
    import sys

    sys.path.insert(0, str(ROOT / "setup"))
    gen = _load(ROOT / "setup" / "02_load_source_data.py")
    a, b = gen.generate(), gen.generate()
    assert a == b
    customers = {r["customer_id"]: r for r in a["crm_customers"]}
    orders = {r["order_id"] for r in a["shop_orders"]}
    products = {r["product_id"] for r in a["shop_products"]}
    assert all(r["customer_id"] in customers for r in a["shop_orders"])
    assert all(r["order_id"] in orders for r in a["shop_order_lines"])
    assert all(r["product_id"] in products for r in a["shop_order_lines"])
    assert len(customers) == 400


@pytest.mark.skipif(not MANIFEST.exists(), reason="run dbt parse first")
def test_graph_rows_from_manifest():
    from de_context.graph_builder import build_rows, catalog_chunks

    rows = build_rows(json.loads(MANIFEST.read_text()), None, ROOT / "data" / "glossary.csv")
    names = {o["name"] for o in rows["ctx_object"]}
    assert {"crm_customers", "hub_customer", "fct_order_lines"} <= names
    rels = {(r["child_name"], r["parent_name"]) for r in rows["ctx_relationship"]}
    assert ("shop_orders", "crm_customers") in rels
    assert ("link_order_customer", "hub_customer") in rels
    assert all(c["data_type"] for c in rows["ctx_column"])
    assert len(catalog_chunks(rows)) == len(rows["ctx_object"])


def test_doc_chunking():
    import sys

    sys.path.insert(0, str(ROOT / "setup"))
    step5 = _load(ROOT / "setup" / "05_build_doc_embeddings.py")
    chunks = []
    for path in sorted((ROOT / "data" / "docs").glob("*/*.md")):
        chunks += step5.chunk_markdown(path)
    assert chunks
    assert {c["doc_type"] for c in chunks} == {"standard", "source_spec", "glossary", "runbook", "guide"}
    assert any(c["section"] == "Hash keys" for c in chunks)
