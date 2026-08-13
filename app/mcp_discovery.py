"""Dynamic Multi-MCP Server discovery using GCP Agent Registry API."""
import logging
import requests
import subprocess
import google.auth
from google.auth.transport.requests import Request

logger = logging.getLogger(__name__)

AGENT_REGISTRY_URL = (
    "https://agentregistry.googleapis.com/v1/projects/uppdemos/locations/us-central1/mcpServers"
)
FALLBACK_JIRA_MCP_URL = "https://jira-mcp-server-850431687571.us-central1.run.app/sse"

def get_auth_token() -> str:
    try:
        credentials, _ = google.auth.default()
        credentials.refresh(Request())
        if credentials.token:
            return credentials.token
    except Exception:
        pass

    try:
        token = subprocess.check_output(
            ["gcloud", "auth", "print-access-token"],
            text=True,
            stderr=subprocess.DEVNULL
        ).strip()
        if token:
            return token
    except Exception:
        pass

    return ""

def discover_all_mcp_servers() -> list[str]:
    """Query Agent Registry API and discover all live registered SSE/MCP server endpoints."""
    discovered = []
    try:
        token = get_auth_token()
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        resp = requests.get(AGENT_REGISTRY_URL, headers=headers, timeout=5)
        if resp.status_code == 200:
            servers = resp.json().get("mcpServers", [])
            for srv in servers:
                interfaces = srv.get("interfaces", [])
                for iface in interfaces:
                    url = iface.get("url")
                    if url:
                        if "jira" in url and not url.endswith("/sse"):
                            url = f"{url}/sse"
                        if url not in discovered:
                            discovered.append(url)
            logger.info(f"Discovered {len(discovered)} MCP server(s) in Agent Registry: {discovered}")
    except Exception as err:
        logger.warning(f"Error querying Agent Registry: {err}")

    if not discovered:
        discovered = [FALLBACK_JIRA_MCP_URL]

    return discovered

def discover_jira_mcp_url() -> str:
    urls = discover_all_mcp_servers()
    for u in urls:
        if "jira" in u:
            return u
    return FALLBACK_JIRA_MCP_URL
