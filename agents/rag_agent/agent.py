"""Module 2: vector RAG - adds search over team documents embedded in BigQuery."""

from google.adk.agents import Agent

from de_context.agent_kit import bigquery_toolset, load_prompt
from de_context.config import get_settings
from de_context.tools import search_docs

settings = get_settings()

root_agent = Agent(
    name="rag_agent",
    model=settings.agent_model,
    description="Answers data engineering questions grounded in team standards, specs and glossary.",
    instruction=load_prompt(__file__),
    tools=[bigquery_toolset(allow_writes=False), search_docs],
)
