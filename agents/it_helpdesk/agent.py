"""Native ADK IT Helpdesk Agent following official ADK agent container deployment conventions."""
import os
import logging

os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "true"

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset, SseConnectionParams
from mcp_discovery import discover_jira_mcp_url, get_auth_token
from app_utils.model_armor_plugin import ModelArmorSecurityPlugin

logger = logging.getLogger(__name__)

def create_mcp_toolset():
    try:
        jira_sse_url = discover_jira_mcp_url()
        token = get_auth_token()
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return McpToolset(
            connection_params=SseConnectionParams(
                url=jira_sse_url,
                headers=headers
            )
        )
    except Exception as e:
        logger.warning(f"Failed to create McpToolset at module import: {e}")
        return McpToolset(
            connection_params=SseConnectionParams(
                url="https://jira-mcp-server-850431687571.us-central1.run.app/sse"
            )
        )

mcp_toolset = create_mcp_toolset()

root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-3.5-flash"
    ),
    description="Enterprise IT Helpdesk AI Assistant with Dynamic Agent Registry Discovery.",
    instruction=(
        "You are an expert IT Helpdesk AI assistant. Use the dynamically discovered "
        "Jira MCP tools (jira_search_issues, jira_get_issue) to search and report "
        "real-time Jira issues to the user in clean Markdown."
    ),
    tools=[mcp_toolset]
)

app = App(
    root_agent=root_agent,
    name="app",
    plugins=[ModelArmorSecurityPlugin()]
)
