"""Turn dbt's manifest.json (+ optional catalog.json and a glossary CSV) into
node and edge rows for the context graph.

Nodes:  ctx_object, ctx_column, ctx_term
Edges:  ctx_feeds (object -> object lineage)
        ctx_relationship (child object -> parent object, from relationships tests)
        ctx_has_column (object -> column)
        ctx_describes (term -> column)
"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any

_REF = re.compile(r"ref\(\s*['\"]([^'\"]+)['\"]\s*\)")
_SOURCE = re.compile(r"source\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)")

LAYER_BY_FOLDER = {"staging": "staging", "raw_vault": "raw_vault", "marts": "mart"}


def _object_type(name: str, layer: str) -> str:
    if layer == "source":
        return "source_table"
    prefixes = {
        "stg_": "staging_view",
        "hub_": "hub",
        "link_": "link",
        "sat_": "satellite",
        "dim_": "dimension",
        "fct_": "fact",
    }
    for prefix, kind in prefixes.items():
        if name.startswith(prefix):
            return kind
    return "model"


def _resolve(expr: str, project_name: str) -> str | None:
    m = _REF.search(expr or "")
    if m:
        return f"model.{project_name}.{m.group(1)}"
    m = _SOURCE.search(expr or "")
    if m:
        return f"source.{project_name}.{m.group(1)}.{m.group(2)}"
    return None


def build_rows(
    manifest: dict[str, Any],
    catalog: dict[str, Any] | None = None,
    glossary_csv: Path | None = None,
) -> dict[str, list[dict[str, Any]]]:
    project_name = manifest["metadata"].get("project_name") or "de_vault"
    catalog_cols: dict[str, dict[str, str]] = {}
    for section in ("nodes", "sources"):
        for uid, entry in (catalog or {}).get(section, {}).items():
            catalog_cols[uid] = {c.lower(): v.get("type") for c, v in entry.get("columns", {}).items()}

    objects: list[dict[str, Any]] = []
    columns: list[dict[str, Any]] = []
    has_column: list[dict[str, Any]] = []
    name_index: dict[str, str] = {}

    def add_object(uid: str, name: str, dataset: str, layer: str, materialized: str, description: str, cols: dict) -> None:
        objects.append({
            "object_id": uid,
            "name": name,
            "dataset": dataset,
            "object_type": _object_type(name, layer),
            "layer": layer,
            "materialization": materialized,
            "description": (description or "").strip(),
        })
        name_index[name.lower()] = uid
        for col_name, col in cols.items():
            cid = f"{uid}.{col_name}"
            data_type = col.get("data_type") or catalog_cols.get(uid, {}).get(col_name.lower())
            columns.append({
                "column_id": cid,
                "object_id": uid,
                "object_name": name,
                "column_name": col_name,
                "data_type": data_type,
                "description": (col.get("description") or "").strip(),
            })
            has_column.append({"object_id": uid, "column_id": cid})

    for uid, src in manifest.get("sources", {}).items():
        add_object(uid, src.get("identifier") or src["name"], src["schema"], "source", "table",
                   src.get("description", ""), src.get("columns", {}))

    for uid, node in manifest.get("nodes", {}).items():
        if node.get("resource_type") != "model":
            continue
        folder = node["fqn"][1] if len(node["fqn"]) > 2 else "model"
        add_object(uid, node.get("alias") or node["name"], node["schema"], LAYER_BY_FOLDER.get(folder, folder),
                   node.get("config", {}).get("materialized", ""), node.get("description", ""),
                   node.get("columns", {}))

    object_ids = {o["object_id"] for o in objects}
    obj_name = {o["object_id"]: o["name"] for o in objects}

    # lineage: parent FEEDS child
    feeds = []
    for uid, node in manifest.get("nodes", {}).items():
        if node.get("resource_type") != "model":
            continue
        for parent in node.get("depends_on", {}).get("nodes", []):
            if parent in object_ids:
                feeds.append({
                    "feed_id": f"{parent}>{uid}",
                    "parent_id": parent,
                    "child_id": uid,
                    "parent_name": obj_name[parent],
                    "child_name": obj_name[uid],
                })

    # relationships tests: child column -> parent column
    relationships = []
    seen = set()
    for uid, node in manifest.get("nodes", {}).items():
        meta = node.get("test_metadata") or {}
        if node.get("resource_type") != "test" or meta.get("name") != "relationships":
            continue
        kwargs = meta.get("kwargs", {})
        child = node.get("attached_node") or _resolve(kwargs.get("model", ""), project_name)
        parent = _resolve(kwargs.get("to", ""), project_name)
        child_col, parent_col = kwargs.get("column_name"), kwargs.get("field")
        if child not in object_ids or parent not in object_ids or not child_col or not parent_col:
            continue
        rid = f"{child}.{child_col}>{parent}.{parent_col}"
        if rid in seen:
            continue
        seen.add(rid)
        relationships.append({
            "relationship_id": rid,
            "child_object_id": child,
            "child_name": obj_name[child],
            "child_column": child_col,
            "parent_object_id": parent,
            "parent_name": obj_name[parent],
            "parent_column": parent_col,
            "source": "dbt_relationships_test",
        })

    # glossary terms
    terms, describes = [], []
    column_index = {f"{c['object_name'].lower()}.{c['column_name'].lower()}": c["column_id"] for c in columns}
    if glossary_csv and Path(glossary_csv).exists():
        with open(glossary_csv, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                term_id = "term." + re.sub(r"[^a-z0-9]+", "_", row["term"].lower()).strip("_")
                terms.append({"term_id": term_id, "term": row["term"], "definition": row["definition"]})
                for ref in (row.get("columns") or "").split(";"):
                    cid = column_index.get(ref.strip().lower())
                    if cid:
                        describes.append({"term_id": term_id, "column_id": cid})

    return {
        "ctx_object": objects,
        "ctx_column": columns,
        "ctx_term": terms,
        "ctx_feeds": feeds,
        "ctx_relationship": relationships,
        "ctx_has_column": has_column,
        "ctx_describes": describes,
    }


def catalog_chunks(rows: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """One searchable 'data catalog' text chunk per table/model (for vector search)."""
    cols_by_obj: dict[str, list[dict[str, Any]]] = {}
    for c in rows["ctx_column"]:
        cols_by_obj.setdefault(c["object_id"], []).append(c)
    chunks = []
    for o in rows["ctx_object"]:
        lines = [
            f"Table {o['dataset']}.{o['name']} ({o['object_type'].replace('_', ' ')}, layer: {o['layer']}).",
            o["description"] or "",
            "Columns:",
        ]
        for c in cols_by_obj.get(o["object_id"], []):
            lines.append(f"- {c['column_name']} ({c['data_type'] or 'unknown'}): {c['description']}")
        chunks.append({
            "chunk_id": f"catalog:{o['object_id']}",
            "doc_name": f"{o['dataset']}.{o['name']}",
            "doc_type": "data_catalog",
            "section": o["object_type"],
            "content": "\n".join(line for line in lines if line is not None),
        })
    return chunks


TABLE_SCHEMAS: dict[str, list[tuple[str, str]]] = {
    "ctx_object": [("object_id", "STRING"), ("name", "STRING"), ("dataset", "STRING"), ("object_type", "STRING"),
                   ("layer", "STRING"), ("materialization", "STRING"), ("description", "STRING")],
    "ctx_column": [("column_id", "STRING"), ("object_id", "STRING"), ("object_name", "STRING"),
                   ("column_name", "STRING"), ("data_type", "STRING"), ("description", "STRING")],
    "ctx_term": [("term_id", "STRING"), ("term", "STRING"), ("definition", "STRING")],
    "ctx_feeds": [("feed_id", "STRING"), ("parent_id", "STRING"), ("child_id", "STRING"),
                  ("parent_name", "STRING"), ("child_name", "STRING")],
    "ctx_relationship": [("relationship_id", "STRING"), ("child_object_id", "STRING"), ("child_name", "STRING"),
                         ("child_column", "STRING"), ("parent_object_id", "STRING"), ("parent_name", "STRING"),
                         ("parent_column", "STRING"), ("source", "STRING")],
    "ctx_has_column": [("object_id", "STRING"), ("column_id", "STRING")],
    "ctx_describes": [("term_id", "STRING"), ("column_id", "STRING")],
}


def property_graph_ddl(dataset: str, graph_name: str) -> str:
    """BigQuery Graph DDL over the context tables (GQL mode only)."""
    d = dataset
    return f"""
CREATE OR REPLACE PROPERTY GRAPH {d}.{graph_name}
  NODE TABLES (
    {d}.ctx_object KEY (object_id) LABEL DataObject,
    {d}.ctx_column KEY (column_id) LABEL DataColumn,
    {d}.ctx_term   KEY (term_id)   LABEL BusinessTerm
  )
  EDGE TABLES (
    {d}.ctx_feeds KEY (feed_id)
      SOURCE KEY (parent_id) REFERENCES ctx_object (object_id)
      DESTINATION KEY (child_id) REFERENCES ctx_object (object_id)
      LABEL FEEDS,
    {d}.ctx_relationship KEY (relationship_id)
      SOURCE KEY (child_object_id) REFERENCES ctx_object (object_id)
      DESTINATION KEY (parent_object_id) REFERENCES ctx_object (object_id)
      LABEL JOINS_TO,
    {d}.ctx_has_column KEY (object_id, column_id)
      SOURCE KEY (object_id) REFERENCES ctx_object (object_id)
      DESTINATION KEY (column_id) REFERENCES ctx_column (column_id)
      LABEL HAS_COLUMN,
    {d}.ctx_describes KEY (term_id, column_id)
      SOURCE KEY (term_id) REFERENCES ctx_term (term_id)
      DESTINATION KEY (column_id) REFERENCES ctx_column (column_id)
      LABEL DESCRIBES
  )
""".strip()
