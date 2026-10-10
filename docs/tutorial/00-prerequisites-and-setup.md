# Module 0: Prerequisites and Setup

**Goal:** create everything the tutorial needs in a sandbox Google Cloud project with one command.
**Time:** about 20 minutes (most of it waiting for dbt and embeddings).

## What you will build

| Dataset | Contents |
|---|---|
| `demo_source` | Fake CRM and web shop tables, 3 load batches |
| `demo_vault` | dbt Data Vault: staging views, hubs, links, satellites |
| `demo_mart` | `dim_customer`, `dim_product`, `fct_order_lines` |
| `demo_context` | Document embeddings, lineage graph tables (+ property graph in GQL mode) |
| `demo_sandbox`, `demo_sandbox_vault` | Empty, used in module 5 |

## Step 1: Check what you need

- A **sandbox** Google Cloud project where you can create datasets, BigQuery connections and IAM bindings (roles: BigQuery Admin, Vertex AI User, Project IAM Admin or equivalent; ask your platform team if unsure).
- Billing enabled. Expected cost of the whole tutorial: well under 5 USD (small data, a few hundred Gemini calls).
- Python 3.10 or newer, `git`, and the [gcloud CLI](https://cloud.google.com/sdk/docs/install) (includes `bq`).

## Step 2: Enable APIs

```bash
gcloud config set project YOUR_PROJECT_ID
gcloud services enable bigquery.googleapis.com bigqueryconnection.googleapis.com aiplatform.googleapis.com
```

## Step 3: Log in with your own identity

```bash
gcloud auth login
gcloud auth application-default login
```

The agents, dbt and setup scripts all use these Application Default Credentials, so BigQuery audit logs show your user and your existing IAM permissions apply. No service account keys are needed.

## Step 4: Clone and install

```bash
git clone https://github.com/gohils/zdbt-repo1.git
cd zdbt-repo1
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

`requirements.txt` installs ADK, the BigQuery client, dbt-bigquery, Faker, and this repo's shared `de_context` package (in editable mode).

## Step 5: Configure

```bash
cp .env.example .env
```

Edit `.env`:

| Setting | What to put |
|---|---|
| `GOOGLE_CLOUD_PROJECT` | Your sandbox project ID |
| `GOOGLE_CLOUD_LOCATION` | Where Gemini is called. `global` works for most current models; use e.g. `us-central1` if your model needs a region |
| `AGENT_MODEL` | A Gemini model your project can use (check Vertex AI Model Garden). Prefer a current Flash model |
| `BQ_LOCATION` | BigQuery location for all datasets, e.g. `US` or `EU` |
| `GRAPH_MODE` | `sql` (works everywhere). Use `gql` only if your project has a BigQuery edition with Graph support (Enterprise / Enterprise Plus reservation) |

Leave the dataset names as they are unless they clash with something.

## Step 6: Run the setup

```bash
python setup/run_all.py
```

What each step does:

| Step | Script | What happens |
|---|---|---|
| 0 | `00_check_prereqs.py` | Checks Python, gcloud/bq/dbt, credentials and BigQuery access |
| 1 | `01_create_datasets.py` | Creates the six datasets (sandbox ones with 7-day table expiry) |
| 2 | `02_load_source_data.py` | Generates deterministic fake data (3 batches) and loads `demo_source` |
| 3 | `03_build_vault.py` | `dbt build` (models + tests) and `dbt docs generate` in `dbt_vault/` |
| 4 | `04_build_context_graph.py` | Flattens `manifest.json` + glossary into `ctx_*` node/edge tables; creates the property graph in GQL mode |
| 5 | `05_build_doc_embeddings.py` | Creates the BigQuery connection and remote embedding model, chunks `data/docs` + one catalog chunk per table, embeds everything into `doc_chunks` |

If a step fails, fix the cause and resume, for example `python setup/run_all.py --from-step 3`. See [troubleshooting](../troubleshooting.md).

## Step 7: Check the result

In the BigQuery console, or with `bq`:

```bash
bq query --use_legacy_sql=false '
SELECT "hub_customer" AS t, COUNT(*) AS n FROM demo_vault.hub_customer
UNION ALL SELECT "sat_customer_details", COUNT(*) FROM demo_vault.sat_customer_details
UNION ALL SELECT "fct_order_lines", COUNT(*) FROM demo_mart.fct_order_lines
UNION ALL SELECT "doc_chunks", COUNT(*) FROM demo_context.doc_chunks
UNION ALL SELECT "ctx_relationship", COUNT(*) FROM demo_context.ctx_relationship'
```

Expected: `hub_customer` 400, `sat_customer_details` 475, `fct_order_lines` 2,576, `doc_chunks` about 70, `ctx_relationship` 13.

Notice `sat_customer_details` has 475 rows although the source has 493 customer rows: the 18 unchanged reloads correctly created no new satellite rows. You will rely on this behaviour in module 5.

## Checkpoint

- [ ] `setup/run_all.py` finished with "Setup complete".
- [ ] Row counts match the expected values.

Next: [Module 1: Base agent](01-base-agent.md)
