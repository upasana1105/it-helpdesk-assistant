"""Native ADK IT Helpdesk Agent following official ADK agent container deployment conventions."""
import os
from pathlib import Path
import sys
import logging

_AGENT_DIR = Path(__file__).resolve().parent
_APP_DIR = _AGENT_DIR.parents[1] / "app"
for _p in (str(_AGENT_DIR), str(_APP_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "true"
os.environ["GOOGLE_CLOUD_LOCATION"] = "global"

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp_discovery import discover_jira_mcp_url, get_auth_token
from app_utils.model_armor_plugin import ModelArmorSecurityPlugin

logger = logging.getLogger(__name__)


async def _call_live_cloud_run_jira_mcp(tool_name: str, arguments: dict) -> str:
    """Invokes a tool on the live Cloud Run jira-mcp-server via a fresh SSE session."""
    jira_sse_url = discover_jira_mcp_url()
    token = get_auth_token()
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with sse_client(url=jira_sse_url, headers=headers) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)
            parts = [getattr(c, "text", str(c)) for c in (result.content or [])]
            return "\n".join(parts)


async def jira_search_issues(query: str = "") -> str:
    """Search for Jira issues across live projects using JQL or text search."""
    return await _call_live_cloud_run_jira_mcp("jira_search_issues", {"query": query})


async def jira_get_issue(issue_key: str) -> str:
    """Retrieve full live details of a specific Jira issue by its key (e.g., WAR-14)."""
    return await _call_live_cloud_run_jira_mcp("jira_get_issue", {"issue_key": issue_key})


async def jira_create_issue(
    project_key: str,
    summary: str,
    description: str,
    issue_type: str = "Task",
    priority: str = "Medium",
) -> str:
    """Create a new issue in a live Jira project."""
    return await _call_live_cloud_run_jira_mcp(
        "jira_create_issue",
        {
            "project_key": project_key,
            "summary": summary,
            "description": description,
            "issue_type": issue_type,
            "priority": priority,
        },
    )


async def jira_add_comment(issue_key: str, comment: str) -> str:
    """Add a comment to an existing live Jira issue."""
    return await _call_live_cloud_run_jira_mcp(
        "jira_add_comment", {"issue_key": issue_key, "comment": comment}
    )


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-3.8-flash"
    ),
    description="Enterprise IT Helpdesk AI Assistant with Dynamic Agent Registry Discovery.",
    instruction=(
        "You are an expert IT Helpdesk AI assistant. Use the dynamically discovered "
        "Jira MCP tools (jira_search_issues, jira_get_issue, jira_create_issue, "
        "jira_add_comment) to search, inspect, and manage "
        "real-time Jira issues in clean Markdown."
    ),
    tools=[jira_search_issues, jira_get_issue, jira_create_issue, jira_add_comment],
)

app = App(
    root_agent=root_agent,
    name="it_helpdesk",
    plugins=[ModelArmorSecurityPlugin()],
)
