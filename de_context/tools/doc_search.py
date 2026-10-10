"""Vector RAG over team documents stored in BigQuery.

Documents (standards, source specs, glossary, runbooks, guides) and the data
catalog (one chunk per table) are chunked, embedded with ML.GENERATE_EMBEDDING
and stored in <context_dataset>.doc_chunks. This tool embeds the question with
the same remote model and runs VECTOR_SEARCH.
"""

from __future__ import annotations

from typing import Any

from ..bq import compact, run_query
from ..config import get_settings

DOC_TYPES = ("standard", "source_spec", "glossary", "runbook", "guide", "data_catalog")


def search_docs(question: str, doc_type: str = "", top_k: int = 5) -> dict[str, Any]:
    """Searches the team's documentation by meaning (vector search in BigQuery).

    Use this before answering questions about team standards, Data Vault rules,
    hashing, naming conventions, source system specs, business definitions,
    runbooks, synthetic data rules, or to find which tables hold a concept
    (doc_type 'data_catalog').

    Args:
        question: The question or topic to search for, in natural language.
        doc_type: Optional filter. One of: standard, source_spec, glossary,
            runbook, guide, data_catalog. Leave empty to search everything.
        top_k: Number of chunks to return (1-10).

    Returns:
        A dict with 'status' and 'results': a list of chunks with doc_name,
        section, doc_type, content and distance (lower is more relevant).
    """
    s = get_settings()
    top_k = max(1, min(int(top_k or 5), 10))
    doc_type = (doc_type or "").strip().lower()
    if doc_type and doc_type not in DOC_TYPES:
        return {
            "status": "ERROR",
            "error_details": f"doc_type must be one of {', '.join(DOC_TYPES)} or empty",
        }

    sql = f"""
    SELECT
      base.doc_name,
      base.section,
      base.doc_type,
      base.content,
      ROUND(distance, 4) AS distance
    FROM VECTOR_SEARCH(
      (SELECT * FROM {s.ctx('doc_chunks')}
       WHERE @doc_type = '' OR doc_type = @doc_type),
      'embedding',
      (
        SELECT ml_generate_embedding_result AS embedding
        FROM ML.GENERATE_EMBEDDING(
          MODEL {s.embedding_model},
          (SELECT @question AS content),
          STRUCT(TRUE AS flatten_json_output, 'RETRIEVAL_QUERY' AS task_type)
        )
      ),
      'embedding',
      top_k => @top_k,
      distance_type => 'COSINE'
    )
    ORDER BY distance
    """
    try:
        rows = run_query(
            sql,
            {"question": question, "doc_type": doc_type, "top_k": top_k},
            label="search-docs",
        )
    except Exception as exc:  # surface the error to the agent instead of crashing
        return {"status": "ERROR", "error_details": str(exc)[:500]}
    return {"status": "SUCCESS", "results": compact(rows, top_k)}
