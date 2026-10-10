"""Module 5: synthetic data generation for Data Vault testing.

Generates source-layer test data in the sandbox dataset with SQL, keeping
referential integrity (parents before children, from the graph) and following
the team's standards (from vector search). Writes are limited to the sandbox
dataset by IAM and by a before_tool_callback guard.
"""

from google.adk.agents import Agent

from de_context.agent_kit import bigquery_toolset, load_prompt
from de_context.config import get_settings
from de_context.tools import (
    get_column_context,
    get_generation_order,
    profile_source_tables,
    sandbox_write_guard,
    save_generator_script,
    search_docs,
    validate_vault,
)

settings = get_settings()

root_agent = Agent(
    name="synthetic_data_agent",
    model=settings.agent_model,
    description="Generates and validates synthetic Data Vault test data in the sandbox.",
    instruction=load_prompt(__file__),
    tools=[
        bigquery_toolset(allow_writes=True),
        search_docs,
        get_generation_order,
        get_column_context,
        profile_source_tables,
        validate_vault,
        save_generator_script,
    ],
    before_tool_callback=sandbox_write_guard,
)
