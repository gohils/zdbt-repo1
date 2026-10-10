# Troubleshooting

## Setup

**`GOOGLE_CLOUD_PROJECT is not set`**
Copy `.env.example` to `.env` and fill it in. Scripts look for `.env` in the current folder and its parents, then the repo root.

**`No Application Default Credentials`**
Run `gcloud auth application-default login`. If you use several accounts, check `gcloud auth list` and that the active one can access the project.

**`dbt: command not found`**
Activate the virtual environment (`source .venv/bin/activate`) and `pip install -r requirements.txt`.

**dbt: `Env var required but not provided: 'GOOGLE_CLOUD_PROJECT'`**
dbt does not read `.env`. When running dbt yourself: `set -a; source .env; set +a` first. `setup/run_all.py` does this for you.

**Step 5: `bq mk --connection` or IAM binding fails**
You need rights to create BigQuery connections and grant project IAM roles. Ask an admin to run step 5 once, or to grant `roles/aiplatform.user` to the connection's service account (shown in the step output).

**Step 5: `Permission denied` / `does not have access to the endpoint` when embedding**
IAM propagation can take 1-2 minutes; the step retries automatically. If it still fails, re-run `python setup/run_all.py --from-step 5`. Check that the Vertex AI API is enabled and that `EMBEDDING_ENDPOINT` is available in your `BQ_LOCATION`.

**Step 5: some chunks have a non-empty `embedding_status`**
Usually quota. Re-run step 5.

**Step 4 with `GRAPH_MODE=gql`: error creating the property graph**
Your project's BigQuery edition / reservation may not support Graph. Use `GRAPH_MODE=sql` (results are equivalent) or run in a project with an Enterprise or Enterprise Plus reservation.

## Agents

**Model not found / 404 / `Publisher model ... not found`**
`AGENT_MODEL` is not available in `GOOGLE_CLOUD_LOCATION`. Check Vertex AI Model Garden for available models; try `GOOGLE_CLOUD_LOCATION=global`, or a regional location such as `us-central1`, or another current Gemini model.

**Agent dropdown is empty in `adk web`**
Start `adk web` from the `agents` folder (`cd agents && adk web`), or pass it: `adk web agents`.

**`ModuleNotFoundError: No module named 'de_context'`**
Run `pip install -r requirements.txt` from the repo root (installs the package in editable mode).

**`Query exceeded limit for bytes billed`**
The query hit `MAX_BYTES_BILLED`. This is the guardrail working. Ask the agent for a narrower query, or raise the cap in `.env` (restart `adk web`).

**`search_docs` returns errors**
Check that setup step 5 completed and `demo_context.doc_chunks` exists. The tool also needs permission to use the connection (`bigquery.connectionUser`; included in BigQuery Admin).

**Graph tools return `NOT_FOUND`**
Use the table name as in dbt (e.g. `hub_customer`, `crm_customers`), or `dataset.table`. Rebuild the graph after model changes: `python setup/run_all.py --from-step 4 --to-step 4`.

**Synthetic data agent: `Blocked by sandbox guard`**
The agent tried to write outside `demo_sandbox`, used an unqualified table name, or sent several statements at once. It normally corrects itself; if not, tell it to write one `CREATE OR REPLACE TABLE <project>.demo_sandbox.<table> AS ...` per call.

## Evaluation

**All questions fail with errors**
Run one agent in `adk web` first to confirm models and credentials work. Then `python evals/run_evals.py --agents base_agent --only std-hashing`.

## Cloud Run

**403 when opening the URL**
Your account needs `roles/iap.httpsResourceAccessor` on the service (the deploy script grants it to the member you pass). Allow a minute for propagation.

**Service starts but tools fail with permission errors**
Check the service account roles in `deploy/deploy_cloud_run.sh` were applied, especially `bigquery.connectionUser` for `search_docs` and `dataViewer` on `demo_context`.
