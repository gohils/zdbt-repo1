"""Module 1: base agent - BigQuery metadata and SQL only (no enterprise context)."""

from google.adk.agents import Agent

from de_context.agent_kit import bigquery_toolset, load_prompt
from de_context.config import get_settings

settings = get_settings()

root_agent = Agent(
    name="base_agent",
    model=settings.agent_model,
    description="Answers questions about BigQuery data using only table metadata and SQL.",
    instruction=load_prompt(__file__),
    tools=[bigquery_toolset(allow_writes=False)],
)
