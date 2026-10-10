# Module 6: Evaluate the Agents

**Goal:** measure, not just demo, how answers improve as context is added, and get a repeatable check for prompt and tool changes.
**Time:** 15 minutes (plus run time).

## The evaluation set

`evals/questions.yaml` has 12 questions across the patterns:

| Category | Example | Needs |
|---|---|---|
| Standards, glossary, source specs | "What hashing algorithm and null handling do we use?" | Vector RAG |
| Impact and root cause | "If customer_id changes format, what is affected?" | Graph |
| Join path | "How do I join shop_order_lines to crm_customers?" | Graph |
| NL to SQL | "Total order value of shipped orders by segment?" | GraphRAG |
| Engineering | "Which hub should cust_ref load into?" | GraphRAG |
| Synthetic data | "In which order must source tables be generated?" | Graph |

Each question lists:
- `expect_all`: terms that must appear in the answer (`a | b` means either),
- `expect_tools`: at least one of these tools must be called.

The scoring is plain string matching on purpose: transparent, free and easy to discuss. It is a smoke test, not a benchmark; read the answers too.

## Step 1: Run it

```bash
python evals/run_evals.py
```

This runs every question against `base_agent`, `rag_agent`, `graph_agent` and `graphrag_agent` through the ADK runner (real Gemini and BigQuery calls, a few cents) and prints one line per question:

```
[rag_agent] std-hashing: PASS (6s) tools=['search_docs'] missing=[]
[base_agent] join-lines-customers: FAIL (9s) tools=['get_table_info', 'list_table_ids'] missing=['tool:find_join_path']
```

A markdown table is saved in `evals/results/` (the values below are illustrative; your run will differ):

| Question | Category | base_agent | rag_agent | graph_agent | graphrag_agent |
|---|---|---|---|---|---|
| std-hashing | standards (vector RAG) | fail | PASS | fail | PASS |
| join-lines-customers | join path (graph) | fail | fail | PASS | PASS |
| ... | | | | | |

Expected trend: `base_agent` passes few, `rag_agent` passes the document questions, `graph_agent` the structural ones, `graphrag_agent` most of them.

Useful options:

```bash
python evals/run_evals.py --agents graphrag_agent              # one agent
python evals/run_evals.py --only sql-segment-shipped onboarding-hub
```

## Step 2: Use it while iterating

1. Change a prompt (e.g. `agents/graphrag_agent/prompt.md`) or a tool docstring.
2. Re-run the affected questions with `--only`.
3. Keep the change only if scores do not drop.

Add a question whenever you find a failure in normal use; the set becomes your regression suite.

## Step 3: Conversation-level evals in the ADK web UI

For multi-turn behaviour (like the module 5 flow), use the web UI's **Eval** tab: run a conversation, add it to an eval set, then re-run the set after changes. ADK compares tool trajectories and responses. Eval sets are stored with the agent, so they can be committed.

## Going further

- Replace string checks with an LLM judge or Vertex AI's Gen AI evaluation service for nuanced scoring.
- Log real usage with ADK's BigQuery Agent Analytics plugin and turn real questions into eval cases.

## Checkpoint

- [ ] You have a results table in `evals/results/`.
- [ ] `graphrag_agent` scores clearly higher than `base_agent`.

Next: [Module 7: Deploy to Cloud Run](07-deploy-cloud-run.md)
