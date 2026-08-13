"""Dynamic MCP Server discovery using Agent Registry API."""
import logging
import requests
import subprocess
import google.auth
from google.auth.transport.requests import Request

logger = logging.getLogger(__name__)

AGENT_REGISTRY_CATALOG_URL = (
    "https://agentregistry.googleapis.com/v1/projects/uppdemos/locations/us-central1/mcpServers"
)
FALLBACK_JIRA_MCP_URL = "https://jira-mcp-server-850431687571.us-central1.run.app/sse"

def get_auth_token() -> str:
    """Robustly retrieve an access token across GCP container runtime and workstation."""
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

def discover_jira_mcp_url() -> str:
    """Query Agent Registry to discover the live SSE URL for jira-mcp-server."""
    try:
        token = get_auth_token()
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        resp = requests.get(AGENT_REGISTRY_CATALOG_URL, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            servers = data.get("mcpServers", [])
            for srv in servers:
                name = srv.get("name", "")
                if "jira-mcp-server" in name:
                    sse_url = srv.get("sseUrl") or srv.get("url") or srv.get("endpoints", {}).get("sse")
                    if sse_url:
                        logger.info(f"Discovered Jira MCP Server in Agent Registry: {sse_url}")
                        return sse_url
    except Exception as err:
        logger.warning(f"Error discovering Jira MCP server in Agent Registry: {err}")

    logger.info(f"Using fallback Jira MCP URL: {FALLBACK_JIRA_MCP_URL}")
    return FALLBACK_JIRA_MCP_URL
