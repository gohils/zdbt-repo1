"""Graph context tools: lineage, join paths and column context.

The graph is built from dbt's manifest.json (see setup/04_build_context_graph.py):

    DataObject  --FEEDS-->      DataObject   (model / source lineage)
    DataObject  --JOINS_TO-->   DataObject   (child -> parent, from dbt relationships tests)
    DataObject  --HAS_COLUMN--> DataColumn
    BusinessTerm --DESCRIBES--> DataColumn   (from the business glossary)

GRAPH_MODE=gql runs fixed, parameter-validated GQL against BigQuery Graph.
GRAPH_MODE=sql runs the same logic with recursive SQL / Python over the same
node and edge tables, so the tutorial also works without an Enterprise
reservation. The agent never writes GQL itself.
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

from ..bq import compact, run_query, safe_identifier
from ..config import get_settings


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _normalise_name(name: str) -> str:
    name = (name or "").strip().strip("`").lower()
    parts = name.split(".")
    # project.dataset.table -> dataset.table
    return ".".join(parts[-2:]) if len(parts) > 2 else name


def _resolve_object(name: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    s = get_settings()
    n = _normalise_name(name)
    rows = run_query(
        f"""
        SELECT object_id, name, dataset, object_type, layer
        FROM {s.ctx('ctx_object')}
        WHERE LOWER(name) = @n
           OR LOWER(CONCAT(dataset, '.', name)) = @n
           OR LOWER(object_id) = @n
        """,
        {"n": n},
        label="graph-resolve",
    )
    if len(rows) == 1:
        return rows[0], rows
    return None, rows


def _not_found(name: str, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    if candidates:
        return {
            "status": "AMBIGUOUS",
            "message": f"'{name}' matches several objects; call again with dataset.table",
            "candidates": compact(candidates),
        }
    return {
        "status": "NOT_FOUND",
        "message": f"No table or model named '{name}' in the lineage graph. "
        "Use list_table_ids or search_docs(doc_type='data_catalog') to find the right name.",
    }


# ---------------------------------------------------------------------------
# get_lineage
# ---------------------------------------------------------------------------
def get_lineage(table_name: str, direction: str = "downstream", max_hops: int = 5) -> dict[str, Any]:
    """Finds upstream or downstream lineage of a table or dbt model (graph traversal).

    Use for impact analysis ("what breaks if I change X?") and root cause
    analysis ("where does this model get its data from?").

    Args:
        table_name: Table or model name, e.g. 'crm_customers', 'hub_customer'
            or 'demo_vault.hub_customer'.
        direction: 'downstream' (what depends on it) or 'upstream' (what it
            depends on).
        max_hops: Maximum number of hops to traverse (1-10).

    Returns:
        A dict with the resolved object and the related objects (name,
        dataset, object_type, layer and, in sql mode, hops).
    """
    s = get_settings()
    direction = (direction or "downstream").lower()
    if direction not in ("downstream", "upstream"):
        return {"status": "ERROR", "error_details": "direction must be 'downstream' or 'upstream'"}
    max_hops = max(1, min(int(max_hops or 5), 10))

    try:
        obj, candidates = _resolve_object(table_name)
        if obj is None:
            return _not_found(table_name, candidates)
        oid = safe_identifier(obj["object_id"])

        if s.graph_mode == "gql":
            if direction == "downstream":
                pattern = f"(start:DataObject {{object_id: '{oid}'}})-[e:FEEDS]->{{1,{max_hops}}}(other:DataObject)"
            else:
                pattern = f"(other:DataObject)-[e:FEEDS]->{{1,{max_hops}}}(start:DataObject {{object_id: '{oid}'}})"
            sql = f"""
            GRAPH {s.graph}
            MATCH {pattern}
            RETURN DISTINCT other.name AS name, other.dataset AS dataset,
                   other.object_type AS object_type, other.layer AS layer
            """
            rows = run_query(sql, label="graph-lineage-gql")
            rows.sort(key=lambda r: (r.get("layer") or "", r.get("name") or ""))
        else:
            near, far = ("parent_id", "child_id") if direction == "downstream" else ("child_id", "parent_id")
            sql = f"""
            WITH RECURSIVE walk AS (
              SELECT {far} AS object_id, 1 AS hops
              FROM {s.ctx('ctx_feeds')}
              WHERE {near} = @oid
              UNION ALL
              SELECT f.{far} AS object_id, w.hops + 1 AS hops
              FROM walk AS w
              JOIN {s.ctx('ctx_feeds')} AS f ON f.{near} = w.object_id
              WHERE w.hops < @max_hops
            )
            SELECT o.name, o.dataset, o.object_type, o.layer, MIN(w.hops) AS hops
            FROM walk AS w
            JOIN {s.ctx('ctx_object')} AS o USING (object_id)
            GROUP BY o.name, o.dataset, o.object_type, o.layer
            ORDER BY hops, name
            """
            rows = run_query(sql, {"oid": oid, "max_hops": max_hops}, label="graph-lineage-sql")
    except Exception as exc:
        return {"status": "ERROR", "error_details": str(exc)[:500]}

    return {
        "status": "SUCCESS",
        "graph_mode": s.graph_mode,
        "object": {k: obj[k] for k in ("name", "dataset", "object_type", "layer")},
        "direction": direction,
        "related_objects": compact(rows, 100),
        "count": len(rows),
    }


# ---------------------------------------------------------------------------
# find_join_path
# ---------------------------------------------------------------------------
def _edge_text(e: dict[str, Any]) -> str:
    return f"{e['child_name']}.{e['child_column']} = {e['parent_name']}.{e['parent_column']}"


def _join_path_gql(a_id: str, b_id: str, max_hops: int) -> list[dict[str, Any]] | None:
    s = get_settings()
    for hops in range(1, max_hops + 1):
        nodes = [f"(n0:DataObject {{object_id: '{a_id}'}})"]
        for i in range(1, hops):
            nodes.append(f"(n{i}:DataObject)")
        nodes.append(f"(n{hops}:DataObject {{object_id: '{b_id}'}})")
        pattern = nodes[0]
        returns = []
        for i in range(1, hops + 1):
            pattern += f"-[r{i}:JOINS_TO]-" + nodes[i]
            returns += [
                f"r{i}.child_name AS child_name_{i}",
                f"r{i}.child_column AS child_column_{i}",
                f"r{i}.parent_name AS parent_name_{i}",
                f"r{i}.parent_column AS parent_column_{i}",
            ]
        sql = f"GRAPH {s.graph}\nMATCH {pattern}\nRETURN {', '.join(returns)}\nLIMIT 1"
        rows = run_query(sql, label="graph-joinpath-gql")
        if rows:
            r = rows[0]
            return [
                {
                    "child_name": r[f"child_name_{i}"],
                    "child_column": r[f"child_column_{i}"],
                    "parent_name": r[f"parent_name_{i}"],
                    "parent_column": r[f"parent_column_{i}"],
                }
                for i in range(1, hops + 1)
            ]
    return None


def _join_path_sql(a_id: str, b_id: str, max_hops: int) -> list[dict[str, Any]] | None:
    s = get_settings()
    edges = run_query(
        f"""
        SELECT child_object_id, child_name, child_column,
               parent_object_id, parent_name, parent_column
        FROM {s.ctx('ctx_relationship')}
        """,
        label="graph-joinpath-sql",
    )
    adjacency: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    for e in edges:
        adjacency[e["child_object_id"]].append((e["parent_object_id"], e))
        adjacency[e["parent_object_id"]].append((e["child_object_id"], e))
    # breadth-first search = shortest path in number of joins
    queue = deque([(a_id, [])])
    seen = {a_id}
    while queue:
        node, path = queue.popleft()
        if node == b_id:
            return path
        if len(path) >= max_hops:
            continue
        for nxt, edge in adjacency.get(node, []):
            if nxt not in seen:
                seen.add(nxt)
                queue.append((nxt, path + [edge]))
    return None


def find_join_path(table_a: str, table_b: str, max_hops: int = 3) -> dict[str, Any]:
    """Finds how to join two tables: the shortest chain of key relationships.

    Relationships come from dbt relationships tests (foreign keys), so the
    join keys are the ones the team has declared and tested. Use this before
    writing SQL that joins tables you have not joined before.

    Args:
        table_a: First table or model name.
        table_b: Second table or model name.
        max_hops: Maximum number of joins in the path (1-4).

    Returns:
        A dict with 'joins': ordered join conditions, and the intermediate
        tables needed, or status NO_PATH.
    """
    s = get_settings()
    max_hops = max(1, min(int(max_hops or 3), 4))
    try:
        a, a_c = _resolve_object(table_a)
        if a is None:
            return _not_found(table_a, a_c)
        b, b_c = _resolve_object(table_b)
        if b is None:
            return _not_found(table_b, b_c)
        a_id, b_id = safe_identifier(a["object_id"]), safe_identifier(b["object_id"])
        if a_id == b_id:
            return {"status": "SUCCESS", "message": "Same table; no join needed.", "joins": []}
        if s.graph_mode == "gql":
            path = _join_path_gql(a_id, b_id, max_hops)
        else:
            path = _join_path_sql(a_id, b_id, max_hops)
    except Exception as exc:
        return {"status": "ERROR", "error_details": str(exc)[:500]}

    if not path:
        return {
            "status": "NO_PATH",
            "message": f"No declared relationship path between {a['name']} and {b['name']} "
            f"within {max_hops} joins.",
        }
    tables = []
    for e in path:
        for t in (e["child_name"], e["parent_name"]):
            if t not in tables:
                tables.append(t)
    return {
        "status": "SUCCESS",
        "graph_mode": s.graph_mode,
        "from": f"{a['dataset']}.{a['name']}",
        "to": f"{b['dataset']}.{b['name']}",
        "tables_involved": tables,
        "joins": [_edge_text(e) for e in path],
    }


# ---------------------------------------------------------------------------
# get_column_context
# ---------------------------------------------------------------------------
def get_column_context(column_name: str) -> dict[str, Any]:
    """Shows where a column is used: tables, key relationships and business terms.

    Args:
        column_name: Column name, e.g. 'customer_id' or 'customer_hk'.

    Returns:
        A dict with the tables containing the column, relationships the column
        takes part in, and business glossary terms that describe it.
    """
    s = get_settings()
    c = (column_name or "").strip().lower().split(".")[-1]
    try:
        safe_identifier(c)
        tables = run_query(
            f"""
            SELECT o.name AS table_name, o.dataset, o.layer, c.data_type, c.description
            FROM {s.ctx('ctx_column')} AS c
            JOIN {s.ctx('ctx_object')} AS o USING (object_id)
            WHERE LOWER(c.column_name) = @c
            ORDER BY o.layer, o.name
            """,
            {"c": c},
            label="graph-column",
        )
        rels = run_query(
            f"""
            SELECT child_name, child_column, parent_name, parent_column
            FROM {s.ctx('ctx_relationship')}
            WHERE LOWER(child_column) = @c OR LOWER(parent_column) = @c
            ORDER BY child_name
            """,
            {"c": c},
            label="graph-column",
        )
        terms = run_query(
            f"""
            SELECT DISTINCT t.term, t.definition
            FROM {s.ctx('ctx_describes')} AS d
            JOIN {s.ctx('ctx_term')} AS t USING (term_id)
            JOIN {s.ctx('ctx_column')} AS c USING (column_id)
            WHERE LOWER(c.column_name) = @c
            """,
            {"c": c},
            label="graph-column",
        )
    except Exception as exc:
        return {"status": "ERROR", "error_details": str(exc)[:500]}
    return {
        "status": "SUCCESS",
        "column": c,
        "tables": compact(tables, 100),
        "relationships": compact(rels, 100),
        "business_terms": compact(terms, 20),
    }


# ---------------------------------------------------------------------------
# get_generation_order (used by the synthetic data agent)
# ---------------------------------------------------------------------------
def get_generation_order() -> dict[str, Any]:
    """Returns the order in which source tables must be generated so that
    every foreign key points to an existing parent row.

    Parents (referenced tables) come before children. Derived from the
    JOINS_TO relationships between source tables in the context graph.

    Returns:
        A dict with 'order' (list of tables with the foreign keys each one
        must satisfy) and 'columns' per table.
    """
    s = get_settings()
    try:
        objects = run_query(
            f"""
            SELECT object_id, name, dataset
            FROM {s.ctx('ctx_object')}
            WHERE layer = 'source'
            ORDER BY name
            """,
            label="graph-genorder",
        )
        rels = run_query(
            f"""
            SELECT r.child_object_id, r.child_name, r.child_column,
                   r.parent_object_id, r.parent_name, r.parent_column
            FROM {s.ctx('ctx_relationship')} AS r
            JOIN {s.ctx('ctx_object')} AS c ON c.object_id = r.child_object_id
            JOIN {s.ctx('ctx_object')} AS p ON p.object_id = r.parent_object_id
            WHERE c.layer = 'source' AND p.layer = 'source'
            """,
            label="graph-genorder",
        )
        columns = run_query(
            f"""
            SELECT o.name AS table_name, c.column_name, c.data_type, c.description
            FROM {s.ctx('ctx_column')} AS c
            JOIN {s.ctx('ctx_object')} AS o USING (object_id)
            WHERE o.layer = 'source'
            ORDER BY o.name, c.column_name
            """,
            label="graph-genorder",
        )
    except Exception as exc:
        return {"status": "ERROR", "error_details": str(exc)[:500]}

    names = {o["object_id"]: o["name"] for o in objects}
    parents: dict[str, set[str]] = {oid: set() for oid in names}
    fks: dict[str, list[str]] = defaultdict(list)
    for r in rels:
        if r["child_object_id"] != r["parent_object_id"]:
            parents.setdefault(r["child_object_id"], set()).add(r["parent_object_id"])
        fks[r["child_name"]].append(_edge_text(r))

    # Kahn's algorithm (topological sort)
    order: list[str] = []
    remaining = {k: set(v) for k, v in parents.items()}
    while remaining:
        ready = sorted([k for k, v in remaining.items() if not v], key=lambda k: names.get(k, k))
        if not ready:  # cycle: report the rest as-is
            order += sorted(remaining, key=lambda k: names.get(k, k))
            break
        for k in ready:
            order.append(k)
            remaining.pop(k)
        for v in remaining.values():
            v.difference_update(ready)

    cols: dict[str, list[str]] = defaultdict(list)
    for c in columns:
        cols[c["table_name"]].append(f"{c['column_name']} {c['data_type'] or ''}".strip())

    return {
        "status": "SUCCESS",
        "dataset": objects[0]["dataset"] if objects else s.source_dataset,
        "order": [
            {"step": i + 1, "table": names.get(oid, oid), "foreign_keys": fks.get(names.get(oid, oid), [])}
            for i, oid in enumerate(order)
        ],
        "columns": dict(cols),
    }
