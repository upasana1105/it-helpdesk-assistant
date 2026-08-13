import os
import logging
from google.adk.agents import Agent
from google.adk.models import Gemini
from google.genai import types

from app.tools import get_ticket_status, get_system_status, request_access

logger = logging.getLogger("it-helpdesk-assistant.agent")

SYSTEM_INSTRUCTION = """You are a warm, helpful, and personable Enterprise IT Helpdesk AI Assistant.
Your goal is to assist employees with IT ticket inquiries, system health status, and access/password reset requests.

Key Behavioral Rules:
1. Greet the user warmly.
2. Use available tools whenever answering specific ticket, system status, or Jira queries.
"""

tools_list = [get_ticket_status, get_system_status, request_access]

try:
    from google.adk.integrations.agent_registry import AgentRegistry
    from google.auth import default
    _, project_id = default()
    registry = AgentRegistry(project_id=project_id or "uppdemos", location="us-central1")
    mcp_toolset = registry.get_mcp_toolset(
        "projects/uppdemos/locations/us-central1/mcpServers/agentregistry-00000000-0000-0000-16bb-db15a254cb40"
    )
    tools_list.insert(0, mcp_toolset)
except Exception as e:
    logger.info(f"AgentRegistry MCP Toolset load status: {e}")

# Native ADK Agent Instance for Google Cloud Console Playground
root_agent = Agent(
    name="it_helpdesk_assistant",
    description="Enterprise IT Helpdesk AI Assistant with dynamic Jira MCP Server integration.",
    instruction=SYSTEM_INSTRUCTION,
    model=Gemini(
        model="gemini-3.6-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    tools=tools_list,
)
