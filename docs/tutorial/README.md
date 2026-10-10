# Tutorial: Enterprise Context for ADK Agents with BigQuery

A step-by-step path from a plain BigQuery agent to GraphRAG and a working synthetic test data agent for a dbt Data Vault. Every module builds on the same data and code.

| # | Module | You will | Time |
|---|---|---|---|
| 0 | [Prerequisites and setup](00-prerequisites-and-setup.md) | Create datasets, fake data, the dbt vault, the context graph and embeddings | 20 min |
| 1 | [Base agent](01-base-agent.md) | Run an ADK agent with the BigQuery toolset and find its limits | 10 min |
| 2 | [Vector RAG](02-vector-rag.md) | Search team documents with `VECTOR_SEARCH` and ground answers | 20 min |
| 3 | [Graph context](03-graph-context.md) | Build lineage and join keys from `manifest.json`; query with GQL or recursive SQL | 25 min |
| 4 | [GraphRAG](04-graphrag.md) | Combine both to turn business questions into correct SQL | 20 min |
| 5 | [Synthetic data](05-synthetic-data.md) | Generate, load and validate Data Vault test data | 30 min |
| 6 | [Evaluation](06-evaluation.md) | Score all agents on the same questions | 15 min |
| 7 | [Deploy to Cloud Run](07-deploy-cloud-run.md) | Share the agents with your team behind IAP | 15 min |

Short on time? Modules 0, 1, 2 and 5 give the core value and work on any BigQuery edition.

Design background: [high-level design](../design/high-level-design.md) and [data and graph model](../design/data-and-graph-model.md). Problems: [troubleshooting](../troubleshooting.md).
