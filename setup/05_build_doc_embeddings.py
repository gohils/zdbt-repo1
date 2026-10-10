"""Step 5: chunk documents, create the embedding model and embed everything.

1. Creates (or reuses) a BigQuery Cloud resource connection and grants its
   service account the Vertex AI User role (needs gcloud and IAM rights).
2. Creates a remote embedding model in the context dataset.
3. Chunks data/docs/**.md by '## ' sections, adds one 'data catalog' chunk per
   table from the context graph, and stores embeddings in doc_chunks.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

from google.cloud import bigquery

from _common import REPO_ROOT, get_settings, info, run, step
from de_context.bq import client, run_query, run_statement
from de_context.graph_builder import build_rows, catalog_chunks

DOCS_DIR = REPO_ROOT / "data" / "docs"
DBT_DIR = REPO_ROOT / "dbt_vault"


def ensure_connection() -> None:
    s = get_settings()
    show = ["bq", "show", "--format=json", "--connection", s.connection_id]
    result = run(show, check=False, capture=True)
    if result.returncode != 0:
        run([
            "bq", "mk", "--connection", f"--location={s.bq_location}", f"--project_id={s.project}",
            "--connection_type=CLOUD_RESOURCE", s.bq_connection,
        ])
        result = run(show, capture=True)
    sa = json.loads(result.stdout)["cloudResource"]["serviceAccountId"]
    info(f"connection service account: {sa}")
    run([
        "gcloud", "projects", "add-iam-policy-binding", s.project,
        f"--member=serviceAccount:{sa}", "--role=roles/aiplatform.user",
        "--condition=None", "--quiet", "--format=none",
    ])


def chunk_markdown(path: Path) -> list[dict]:
    doc_type = path.parent.name  # folder name = doc type
    text = path.read_text(encoding="utf-8")
    title_match = re.search(r"^# (.+)$", text, re.M)
    title = title_match.group(1).strip() if title_match else path.stem
    sections = re.split(r"^## ", text, flags=re.M)
    chunks = []
    intro = sections[0].strip()
    if intro and intro != f"# {title}":
        chunks.append(("Overview", intro))
    for sec in sections[1:]:
        heading, _, body = sec.partition("\n")
        chunks.append((heading.strip(), body.strip()))
    return [
        {
            "chunk_id": f"{path.stem}:{i}",
            "doc_name": title,
            "doc_type": doc_type,
            "section": heading,
            # Title and heading inside the text improve retrieval quality
            "content": f"{title} - {heading}\n{body}",
        }
        for i, (heading, body) in enumerate(chunks)
        if body
    ]


def main() -> None:
    step("Step 5: embed documents and the data catalog")
    s = get_settings()

    ensure_connection()

    chunks: list[dict] = []
    for path in sorted(DOCS_DIR.glob("*/*.md")):
        chunks += chunk_markdown(path)
    manifest = json.loads((DBT_DIR / "target" / "manifest.json").read_text())
    chunks += catalog_chunks(build_rows(manifest))
    info(f"{len(chunks)} chunks ({sum(c['doc_type'] == 'data_catalog' for c in chunks)} data catalog)")

    raw_table = f"{s.project}.{s.context_dataset}.doc_chunks_raw"
    schema = [bigquery.SchemaField(c, "STRING") for c in ("chunk_id", "doc_name", "doc_type", "section", "content")]
    job_config = bigquery.LoadJobConfig(
        schema=schema,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
    )
    client().load_table_from_json(chunks, raw_table, job_config=job_config).result()
    info(f"loaded {raw_table}")

    run_statement(
        f"""
        CREATE OR REPLACE MODEL {s.embedding_model}
        REMOTE WITH CONNECTION `{s.connection_id}`
        OPTIONS (ENDPOINT = '{s.embedding_endpoint}')
        """,
        label="setup-embeddings",
    )
    info(f"remote model {s.embedding_model} -> {s.embedding_endpoint}")

    embed_sql = f"""
    CREATE OR REPLACE TABLE {s.ctx('doc_chunks')} AS
    SELECT
      chunk_id, doc_name, doc_type, section, content,
      ml_generate_embedding_result AS embedding,
      ml_generate_embedding_status AS embedding_status
    FROM ML.GENERATE_EMBEDDING(
      MODEL {s.embedding_model},
      (SELECT * FROM `{raw_table}`),
      STRUCT(TRUE AS flatten_json_output, 'RETRIEVAL_DOCUMENT' AS task_type)
    )
    """
    # IAM for the new connection can take a minute or two to propagate.
    for attempt in range(1, 6):
        try:
            run_statement(embed_sql, label="setup-embeddings")
            break
        except Exception as exc:
            if attempt == 5:
                raise
            info(f"embedding attempt {attempt} failed ({str(exc)[:120]}...); retrying in 30s")
            time.sleep(30)

    status = run_query(
        f"""
        SELECT COUNT(*) AS chunks, COUNTIF(embedding_status != '') AS failed
        FROM {s.ctx('doc_chunks')}
        """
    )[0]
    info(f"doc_chunks: {status['chunks']} chunks, {status['failed']} failed embeddings")
    if status["failed"]:
        raise SystemExit("Some chunks failed to embed. Re-run step 5 (see docs/troubleshooting.md).")


if __name__ == "__main__":
    main()
