"""Module 3: graph context - lineage, join paths and column usage from the context graph."""

from google.adk.agents import Agent

from de_context.agent_kit import bigquery_toolset, load_prompt
from de_context.config import get_settings
from de_context.tools import find_join_path, get_column_context, get_lineage

settings = get_settings()

root_agent = Agent(
    name="graph_agent",
    model=settings.agent_model,
    description="Impact analysis, root cause analysis and join paths using the lineage graph.",
    instruction=load_prompt(__file__),
    tools=[bigquery_toolset(allow_writes=False), get_lineage, find_join_path, get_column_context],
)
