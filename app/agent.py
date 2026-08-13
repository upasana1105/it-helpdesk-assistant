"""Native ADK IT Helpdesk Agent with Pure Dynamic MCP Toolset and GCP Auth Manager integration."""
import os
import logging

os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "true"

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset, SseConnectionParams
from app.mcp_discovery import discover_jira_mcp_url, get_auth_token
from app.app_utils.model_armor_plugin import ModelArmorSecurityPlugin

logger = logging.getLogger(__name__)

def create_mcp_toolset():
    url = discover_jira_mcp_url()
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return McpToolset(connection_params=SseConnectionParams(url=url, headers=headers))

mcp_toolset = create_mcp_toolset()

# Dynamically bind Agent Identity Auth Manager (GcpAuthProvider)
auth_providers = []
try:
    from google.adk.integrations.agent_identity import GcpAuthProvider
    auth_providers.append(GcpAuthProvider())
    logger.info("Agent Identity Auth Manager (GcpAuthProvider) successfully registered.")
except Exception as e:
    logger.warning("GcpAuthProvider optional fallback: %s", e)

root_agent = Agent(
    name="it_helpdesk_assistant",
    model=Gemini(
        model="gemini-2.5-flash"
    ),
    description=(
        "Enterprise IT Helpdesk AI Assistant with dynamic Agent Registry multi-MCP and GCP Auth Manager integration."
    ),
    instruction=(
        "You are an expert IT Helpdesk AI assistant.\n"
        "SEARCH RULE: When asked to find or check for issues on any topic, keyword, or summary (e.g., 'Gateway Auth Latency', 'API latency', 'latency'), "
        "you MUST invoke `jira_search_issues` passing `project_key='WAR'` and the keyword search string in the `query` or `jql` parameter.\n"
        "Use the dynamically discovered MCP tools from Agent Registry to perform all actions:\n"
        "- Use Jira tools to find, inspect, create, or update issues.\n"
        "Always provide complete, helpful, and well-formatted answers to the user."
    ),
    tools=[mcp_toolset]
)

app = App(
    root_agent=root_agent,
    name="it_helpdesk_assistant",
    auth_providers=auth_providers if auth_providers else None,
    plugins=[ModelArmorSecurityPlugin()]
)
