"""Module 4: GraphRAG - vector search finds the right concepts and tables, the graph
supplies relationships and join paths, BigQuery executes the SQL."""

from google.adk.agents import Agent

from de_context.agent_kit import bigquery_toolset, load_prompt
from de_context.config import get_settings
from de_context.tools import find_join_path, get_column_context, get_lineage, search_docs

settings = get_settings()

root_agent = Agent(
    name="graphrag_agent",
    model=settings.agent_model,
    description="Combines document search and the lineage graph to answer data questions accurately.",
    instruction=load_prompt(__file__),
    tools=[
        bigquery_toolset(allow_writes=False),
        search_docs,
        get_lineage,
        find_join_path,
        get_column_context,
    ],
)
