"""Simulated & Live Jira MCP IT Helpdesk tools with Auth Manager OAuth integration."""
import os
import logging
from typing import Dict, Any, List, Optional

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

logger = logging.getLogger("it-helpdesk-assistant.tools")

env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
if os.path.exists(env_path):
    try:
        with open(env_path) as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.strip().split("=", 1)
                    os.environ[k] = v
    except Exception:
        pass


# Mock Ticket Database
MOCK_TICKETS: Dict[str, Dict[str, Any]] = {
    "INC-101": {
        "ticket_id": "INC-101",
        "summary": "VPN connection drops every 15 minutes",
        "status": "In Progress",
        "priority": "High",
        "assignee": "Sarah Connor (Network Ops)",
        "created_at": "2026-07-28T09:15:00Z",
        "last_update": "Investigating gateway routing logs."
    },
    "INC-102": {
        "ticket_id": "INC-102",
        "summary": "Request for Cloud Console Admin Access",
        "status": "Pending Approval",
        "priority": "Medium",
        "assignee": "Alex Rivera (SecOps)",
        "created_at": "2026-07-29T08:30:00Z",
        "last_update": "Awaiting manager approval."
    },
    "INC-103": {
        "ticket_id": "INC-103",
        "summary": "Monitors flickering on dual-display setup",
        "status": "Resolved",
        "priority": "Low",
        "assignee": "IT Hardware Desk",
        "created_at": "2026-07-25T14:00:00Z",
        "last_update": "Replaced DisplayPort cable. Issue resolved."
    }
}

# Mock Systems Operational Health Database
MOCK_SYSTEMS: Dict[str, Dict[str, Any]] = {
    "vpn": {"name": "Corporate VPN", "status": "Degraded Performance", "latency_ms": 140, "active_incidents": ["INC-101"]},
    "sso": {"name": "Single Sign-On (SSO)", "status": "Operational", "latency_ms": 22, "active_incidents": []},
    "email": {"name": "Gmail & Workspace", "status": "Operational", "latency_ms": 18, "active_incidents": []},
    "jira": {"name": "Jira & Confluence", "status": "Operational", "latency_ms": 45, "active_incidents": []},
    "cloud_console": {"name": "GCP Cloud Console", "status": "Operational", "latency_ms": 30, "active_incidents": []}
}


def get_ticket_status(ticket_id: str) -> Dict[str, Any]:
    """Retrieve current status, priority, and updates for an IT ticket.

    Args:
        ticket_id: The ticket ID string, e.g., 'INC-101', 'INC-102', 'INC-103'.
    """
    clean_id = ticket_id.strip().upper()
    if clean_id in MOCK_TICKETS:
        return {"success": True, "ticket": MOCK_TICKETS[clean_id]}
    
    return {
        "success": False,
        "error": f"Ticket ID '{ticket_id}' not found.",
        "available_sample_tickets": list(MOCK_TICKETS.keys())
    }


def get_atlassian_oauth_token() -> Optional[str]:
    """Exchange Client ID & Secret or Refresh Token for live Atlassian OAuth Access Token."""
    client_id = os.getenv("JIRA_CLIENT_ID", "VpI5Jg91Sry8zVOFtob2EIYMbQw9vkKl")
    client_secret = os.getenv("JIRA_CLIENT_SECRET", "YOUR_OAUTH_TOKEN")
    refresh_token = os.getenv("JIRA_OAUTH_REFRESH_TOKEN")

    if not HAS_HTTPX or not client_id or not client_secret:
        return None

    # 1. Use Refresh Token if available for user OAuth token
    if refresh_token:
        try:
            res = httpx.post(
                "https://auth.atlassian.com/oauth/token",
                json={
                    "grant_type": "refresh_token",
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": refresh_token
                },
                timeout=5.0
            )
            if res.status_code == 200:
                data = res.json()
                new_refresh_token = data.get("refresh_token")
                if new_refresh_token:
                    os.environ["JIRA_OAUTH_REFRESH_TOKEN"] = new_refresh_token
                return data.get("access_token")
        except Exception as e:
            logger.warning(f"OAuth refresh token error: {e}")

    # 2. Fallback to client credentials
    try:
        res = httpx.post(
            "https://auth.atlassian.com/oauth/token",
            json={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "audience": "api.atlassian.com"
            },
            timeout=5.0
        )
        if res.status_code == 200:
            return res.json().get("access_token")
    except Exception as e:
        logger.warning(f"OAuth client_credentials token error: {e}")

    return None



def get_jira_issue(issue_key: str, jira_domain: Optional[str] = None, user_oauth_token: Optional[str] = None) -> Dict[str, Any]:
    """Retrieve Jira issue via Jira MCP / REST API using Auth Manager OAuth token delegation or API Token.

    Args:
        issue_key: Jira issue key, e.g. 'PROJ-123', 'IT-404'.
        jira_domain: Optional Atlassian domain, e.g., 'upasanapati-1771922768188.atlassian.net'.
        user_oauth_token: User OAuth Bearer token supplied automatically by Auth Manager.
    """
    clean_key = issue_key.strip().upper()
    domain = jira_domain or os.getenv("JIRA_DOMAIN", "upasanapati-1771922768188.atlassian.net")
    cloud_id = os.getenv("JIRA_CLOUD_ID", "a6ad8509-c740-4e06-a9da-5dae46453349")
    jira_email = os.getenv("JIRA_USER_EMAIL", "upasanapati@gmail.com")
    jira_token = os.getenv("JIRA_API_TOKEN", "YOUR_JIRA_API_TOKEN")


    # 1. Live Atlassian Basic Auth (API Token) Callout
    if HAS_HTTPX and jira_email and jira_token:
        url = f"https://{domain}/rest/api/3/issue/{clean_key}"
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(url, auth=(jira_email, jira_token), headers={"Accept": "application/json"})
                if resp.status_code == 200:
                    data = resp.json()
                    fields = data.get("fields", {})
                    return {
                        "success": True,
                        "source": f"Live Jira API Token ({domain})",
                        "issue_key": clean_key,
                        "summary": fields.get("summary"),
                        "status": fields.get("status", {}).get("name"),
                        "assignee": fields.get("assignee", {}).get("displayName", "Unassigned")
                    }
                elif resp.status_code == 404:
                    return {"success": False, "error": f"Issue '{clean_key}' was not found on Jira tenant '{domain}'."}
        except Exception as e:
            logger.warning(f"Direct Jira API call error: {e}")

    # 2. Auth Manager Live OAuth Callout
    oauth_token = user_oauth_token or get_atlassian_oauth_token()
    if HAS_HTTPX and oauth_token:
        headers = {"Authorization": f"Bearer {oauth_token}", "Accept": "application/json"}
        url = f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3/issue/{clean_key}"
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    fields = data.get("fields", {})
                    return {
                        "success": True,
                        "source": f"Live Jira OAuth API ({domain})",
                        "issue_key": clean_key,
                        "summary": fields.get("summary"),
                        "status": fields.get("status", {}).get("name"),
                        "assignee": fields.get("assignee", {}).get("displayName", "Unassigned"),
                        "cloud_id": cloud_id
                    }
                elif resp.status_code == 404:
                    return {"success": False, "error": f"Issue '{clean_key}' was not found on Jira tenant '{domain}'."}
        except Exception as e:
            logger.warning(f"Jira OAuth API call error: {e}")



    # 2. Live Atlassian Basic Auth (API Token) Callout
    if HAS_HTTPX and jira_email and jira_token:
        url = f"https://{domain}/rest/api/3/issue/{clean_key}"
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(url, auth=(jira_email, jira_token), headers={"Accept": "application/json"})
                if resp.status_code == 200:
                    data = resp.json()
                    fields = data.get("fields", {})
                    return {
                        "success": True,
                        "source": f"Live Jira API ({domain})",
                        "issue_key": clean_key,
                        "summary": fields.get("summary"),
                        "status": fields.get("status", {}).get("name"),
                        "assignee": fields.get("assignee", {}).get("displayName", "Unassigned")
                    }
                elif resp.status_code == 404:
                    return {"success": False, "error": f"Issue '{clean_key}' was not found on Jira tenant '{domain}'."}
                elif resp.status_code in (401, 403):
                    return {"success": False, "error": f"Authentication failed for user '{jira_email}' on Jira tenant '{domain}'."}
        except Exception as e:
            logger.warning(f"Direct Jira Basic Auth call error: {e}")

    # 3. Direct Public API query check
    if HAS_HTTPX:
        headers = {"Accept": "application/json"}
        url = f"https://{domain}/rest/api/3/issue/{clean_key}"
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    fields = data.get("fields", {})
                    return {
                        "success": True,
                        "source": f"Live Jira API ({domain})",
                        "issue_key": clean_key,
                        "summary": fields.get("summary"),
                        "status": fields.get("status", {}).get("name"),
                        "assignee": fields.get("assignee", {}).get("displayName", "Unassigned")
                    }
                elif resp.status_code == 404:
                    return {
                        "success": False,
                        "error": f"Issue '{clean_key}' does not exist on Jira tenant '{domain}'.",
                        "jira_tenant": f"https://{domain}/"
                    }
                elif resp.status_code in (401, 403):
                    return {
                        "success": False,
                        "error": f"Jira issue '{clean_key}' requires authentication on '{domain}'. Please authorize via GCP Auth Manager.",
                        "jira_tenant": f"https://{domain}/"
                    }
        except Exception as e:
            logger.warning(f"Direct Jira API call error: {e}")

    return {
        "success": False,
        "error": f"Unable to reach Jira tenant '{domain}'.",
        "jira_tenant": f"https://{domain}/"
    }


def search_jira_issues(project_key: str = "WAR", status: Optional[str] = None, user_oauth_token: Optional[str] = None) -> Dict[str, Any]:
    """Search Jira issues for a given project key and optional status filter using JQL.

    Args:
        project_key: Jira project key, e.g., 'WAR'.
        status: Optional status string filter, e.g., 'In Progress', 'To Do', 'Done'.
        user_oauth_token: User OAuth Bearer token supplied automatically by Auth Manager.
    """
    clean_project = project_key.strip().upper()
    domain = os.getenv("JIRA_DOMAIN", "upasanapati-1771922768188.atlassian.net")
    cloud_id = os.getenv("JIRA_CLOUD_ID", "a6ad8509-c740-4e06-a9da-5dae46453349")
    jira_email = os.getenv("JIRA_USER_EMAIL", "upasanapati@gmail.com")
    jira_token = os.getenv("JIRA_API_TOKEN", "YOUR_JIRA_API_TOKEN")


    jql = f"project = '{clean_project}'"
    if status:
        jql += f" AND status = '{status}'"

    # 1. Live Atlassian Basic Auth (API Token) Search Callout
    if HAS_HTTPX and jira_email and jira_token:
        url = f"https://{domain}/rest/api/3/search/jql"
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(url, auth=(jira_email, jira_token), headers={"Accept": "application/json"}, params={"jql": jql, "fields": "summary,status,assignee,key"})
                if resp.status_code == 200:
                    data = resp.json()
                    issues = [
                        {
                            "key": i.get("key"),
                            "summary": i.get("fields", {}).get("summary", "No summary"),
                            "status": i.get("fields", {}).get("status", {}).get("name", "Unknown"),
                            "assignee": i.get("fields", {}).get("assignee", {}).get("displayName", "Unassigned") if i.get("fields", {}).get("assignee") else "Unassigned"
                        }
                        for i in data.get("issues", [])
                    ]
                    return {"success": True, "project": clean_project, "jql": jql, "count": len(issues), "issues": issues, "source": f"Live Jira API Token ({domain})"}
        except Exception as e:
            logger.warning(f"Direct Jira search call error: {e}")

    # 2. Auth Manager Live OAuth Search Callout
    oauth_token = user_oauth_token or get_atlassian_oauth_token()
    if HAS_HTTPX and oauth_token:
        headers = {"Authorization": f"Bearer {oauth_token}", "Accept": "application/json"}
        url = f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3/search/jql"
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(url, headers=headers, params={"jql": jql, "fields": "summary,status,assignee,key"})
                if resp.status_code == 200:
                    data = resp.json()
                    issues = [
                        {
                            "key": i.get("key"),
                            "summary": i.get("fields", {}).get("summary", "No summary"),
                            "status": i.get("fields", {}).get("status", {}).get("name", "Unknown"),
                            "assignee": i.get("fields", {}).get("assignee", {}).get("displayName", "Unassigned") if i.get("fields", {}).get("assignee") else "Unassigned"
                        }
                        for i in data.get("issues", [])
                    ]
                    return {"success": True, "project": clean_project, "jql": jql, "count": len(issues), "issues": issues, "source": f"Live Jira OAuth ({domain})"}

        except Exception as e:
            logger.warning(f"Jira OAuth search call error: {e}")

    # 3. Direct Public API JQL Search Callout
    if HAS_HTTPX:
        headers = {"Accept": "application/json"}
        url = f"https://{domain}/rest/api/3/search/jql"
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(url, headers=headers, params={"jql": jql})
                if resp.status_code == 200:
                    data = resp.json()
                    issues = [
                        {
                            "key": i.get("key"),
                            "summary": i.get("fields", {}).get("summary", "No summary"),
                            "status": i.get("fields", {}).get("status", {}).get("name", "Unknown"),
                            "assignee": i.get("fields", {}).get("assignee", {}).get("displayName", "Unassigned")
                        }
                        for i in data.get("issues", [])
                    ]
                    return {"success": True, "project": clean_project, "jql": jql, "count": len(issues), "issues": issues, "source": f"Live Jira Tenant ({domain})"}
                elif resp.status_code in (401, 403):
                    return {
                        "success": False,
                        "error": f"Searching Jira project '{clean_project}' requires authentication on '{domain}'. Please authorize via GCP Auth Manager.",
                        "jql": jql,
                        "jira_tenant": f"https://{domain}/"
                    }
        except Exception as e:
            logger.warning(f"Direct Jira search call error: {e}")

    return {
        "success": False,
        "error": f"Unable to reach Jira tenant '{domain}'.",
        "jira_tenant": f"https://{domain}/"
    }


def get_system_status(service_name: str) -> Dict[str, Any]:

    """Check current health, latency, and active incidents for a company IT service.

    Args:
        service_name: Name of the service, e.g., 'vpn', 'sso', 'email', 'jira', 'cloud_console'.
    """
    clean_name = service_name.strip().lower()
    if clean_name in MOCK_SYSTEMS:
        return {"success": True, "system": MOCK_SYSTEMS[clean_name], "service": MOCK_SYSTEMS[clean_name]}
    
    return {
        "success": False,
        "error": f"Service '{service_name}' not found.",
        "available_services": list(MOCK_SYSTEMS.keys()),
        "supported_services": list(MOCK_SYSTEMS.keys())
    }


def request_access(user_name: str = "default_user", resource_name: str = "", reason: str = "", **kwargs) -> Dict[str, Any]:
    """Submit an automated access request for software, cloud projects, or system permissions.

    Args:
        user_name: User requesting access.
        resource_name: Software or system name (e.g. 'Jira Admin', 'GCP Production Console').
        reason: Explanation/business justification for the access request.
    """
    if not resource_name or not reason:
        return {"success": False, "error": "Missing required arguments: resource_name and reason."}

    import random
    new_id = f"REQ-{random.randint(200, 999)}"
    return {
        "success": True,
        "request_id": new_id,
        "message": f"Access request for '{resource_name}' submitted successfully.",
        "ticket_id": new_id,
        "resource_name": resource_name,
        "reason": reason,
        "user_name": user_name,
        "status": "Submitted",
        "approval_flow": "Automated Manager Approval Queue"
    }

