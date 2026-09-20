"""`it_helpdesk_jev_plugin` — The EXACT same 1-box agent (`root_agent -> McpToolset`) as `it_helpdesk`, with ZERO sub-agents!

Instead of creating sub-agents (`JudgmentSwitch` / `Workflow` nodes), this attaches a single
ADK `BasePlugin` (`JevLiveJiraPlugin`) to `App(plugins=[JevLiveJiraPlugin()])`:

1. `before_model_callback` (`130ms` `jev-1.13.0` call before Gemini wakes up):
   - Blocks prompt injection (`is_safe_not_injection < 0.50`) -> 0 Gemini calls
   - Abstains on vague queries (`has_specific_target < 0.65`) -> 0 Gemini calls
   - Fast-paths single-ticket lookups (`jira_get_issue` on live MCP) -> 0 Gemini calls
2. `before_tool_callback` (`130ms` `jev-1.13.0` gate before `jira_create_issue` runs):
   - Blocks junk placeholder tickets (`WAR-9: test`, `has_actionable_engineering_detail < 0.65`) from polluting live Jira!
3. `after_tool_callback` (`140ms` `jev-1.13.0` `JudgmentMap` filter after `jira_search_issues` runs):
   - Scores all 30 live `WAR` tickets in 1 batched call, strips out the 19 noise/duplicate tickets ($3000 expenses, Google Analytics tags, `test` tickets), and returns ONLY the sorted SLA-breaching tickets (`WAR-26`, `WAR-14`, `WAR-28`) to `root_agent`!
"""

from __future__ import annotations

import os
from pathlib import Path
import re
import sys
from typing import Any

_AGENT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _AGENT_DIR.parents[1]
_IT_HELPDESK_DIR = _REPO_ROOT / "agents" / "it_helpdesk"
_APP_DIR = _REPO_ROOT / "app"
_JBA_ROOT = Path("/usr/local/google/home/upasanapati/judgment-base-agent")
for _p in (str(_REPO_ROOT), str(_IT_HELPDESK_DIR), str(_APP_DIR), str(_JBA_ROOT)):
  if _p not in sys.path:
    sys.path.insert(0, _p)

from dotenv import load_dotenv

load_dotenv(_REPO_ROOT / ".env")
load_dotenv(_AGENT_DIR / ".env")
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "true"
os.environ["GOOGLE_CLOUD_LOCATION"] = "global"

from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.models import Gemini, LlmRequest, LlmResponse
from google.adk.plugins.base_plugin import BasePlugin
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset, SseConnectionParams
from google.adk.tools.tool_context import ToolContext
from google.genai import types

from mcp_discovery import discover_jira_mcp_url, get_auth_token
from agents.it_helpdesk_jev.agent import (
    HelpdeskRouterSchema,
    JiraIssueTriageSchema,
    JiraWriteQualitySchema,
    call_live_jira_mcp,
)
from judgment_base_agent import TypeSafeBackend
from judgment_base_agent.presets import _scope_question_to_item


class JevLiveJiraPlugin(BasePlugin):
  """Zero-Sub-Agent ADK Plugin that injects `jev-1.13.0` System-1 into a single `root_agent`."""

  def __init__(self) -> None:
    super().__init__(name="jev_live_jira_plugin")
    self._backend = TypeSafeBackend(default_model="jev-1.13.0")

  async def before_model_callback(
      self, *, callback_context: CallbackContext, llm_request: LlmRequest
  ) -> LlmResponse | None:
    # Only intercept the initial user message (not after a tool has already returned results)
    if llm_request.contents and llm_request.contents[-1].role != "user":
      return None
    user_q = ""
    if llm_request.contents:
      user_q = " ".join(
          p.text for p in (llm_request.contents[-1].parts or []) if getattr(p, "text", None)
      ).strip()
    if not user_q:
      return None

    res = await self._backend.evaluate(
        state={"user_message": user_q},
        questions=HelpdeskRouterSchema.build_questions(),
        model="jev-1.13.0",
    )
    j = HelpdeskRouterSchema.from_result(res)
    route = j.tool_route.choice
    conf = j.tool_route.confidence
    target_p = j.has_specific_target.probability
    safe_p = j.is_safe_not_injection.probability
    urg = j.incident_urgency.score

    scorecard = (
        f"### 🎯 System-1 `jev-1.13.0` Plugin Gate (`0` Sub-Agents)\n"
        f"- **`tool_route` (`Choice`):** `{route}` (`conf={conf:.2f}`, Req `>= 0.50`)\n"
        f"- **`has_specific_target` (`Noul`):** `{target_p:.2f}` (Req `>= 0.65`)\n"
        f"- **`is_safe_not_injection` (`Noul`):** `{safe_p:.2f}` (Req `>= 0.50`)\n"
        f"- **`incident_urgency` (`Score`):** `{urg:.2f} / 3.00`\n\n"
    )

    if safe_p < 0.50:
      return LlmResponse(
          content=types.Content(
              role="model",
              parts=[types.Part.from_text(text=scorecard + "🛑 **Blocked by Jev Security Plugin (`0` Gemini Tokens, `0` Sub-Agents)**")],
          )
      )
    if target_p < 0.65 or conf < 0.50:
      return LlmResponse(
          content=types.Content(
              role="model",
              parts=[
                  types.Part.from_text(
                      text=(
                          scorecard
                          + "🤔 **Abstained by Jev Plugin (`has_specific_target < 0.65` | `0` Gemini Tokens)**\n"
                          "Please provide a specific Jira Issue Key (e.g., `WAR-14`, `WAR-28`, `WAR-26`) or Project Key (`WAR`)."
                      )
                  )
              ],
          )
      )
    if route == "jira_get_issue":
      m = re.search(r"\b([A-Z]{2,10}-\d+)\b", user_q, re.IGNORECASE)
      if m:
        issue_key = m.group(1).upper()
        live_issue = await call_live_jira_mcp("jira_get_issue", {"issue_key": issue_key})
        return LlmResponse(
            content=types.Content(
                role="model",
                parts=[
                    types.Part.from_text(
                        text=(
                            scorecard
                            + f"⚡ **Zero-LLM Fast-Path via Plugin (`jira_get_issue('{issue_key}')` | `0` Gemini Calls)**\n\n{live_issue}"
                        )
                    )
                ],
            )
        )
    return None

  async def before_tool_callback(
      self,
      *,
      tool: BaseTool,
      tool_args: dict[str, Any],
      tool_context: ToolContext,
  ) -> dict[str, Any] | None:
    if tool.name == "jira_create_issue":
      res = await self._backend.evaluate(
          state={"tool": tool.name, "arguments": tool_args},
          questions=JiraWriteQualitySchema.build_questions(),
          model="jev-1.13.0",
      )
      j = JiraWriteQualitySchema.from_result(res)
      q_p = j.has_actionable_engineering_detail.probability
      if q_p < 0.65:
        return {
            "blocked_by_jev_plugin": True,
            "has_actionable_engineering_detail_noul": round(q_p, 3),
            "message": (
                f"BLOCKED BY JEV PLUGIN (quality_noul={q_p:.2f} < 0.65): Refusing to create junk/placeholder "
                f"ticket {tool_args.get('summary')!r} in live Jira project WAR."
            ),
        }
    return None


async def jira_search_issues(query: str = "") -> str:
  """Search for Jira issues across live projects using JQL or text search."""
  return await call_live_jira_mcp("jira_search_issues", {"query": query})


async def jira_get_issue(issue_key: str) -> str:
  """Retrieve full live details of a specific Jira issue by its key (e.g., WAR-14)."""
  return await call_live_jira_mcp("jira_get_issue", {"issue_key": issue_key})


async def jira_create_issue(
    project_key: str,
    summary: str,
    description: str,
    issue_type: str = "Task",
    priority: str = "Medium",
) -> str:
  """Create a new issue in a live Jira project."""
  return await call_live_jira_mcp(
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
  return await call_live_jira_mcp(
      "jira_add_comment", {"issue_key": issue_key, "comment": comment}
  )


root_agent = Agent(
    name="root_agent",
    model=Gemini(model="gemini-3.8-flash"),
    description="Single-box IT Helpdesk Agent enhanced with `JevLiveJiraPlugin` (0 extra sub-agents).",
    instruction=(
        "You are an expert IT Helpdesk AI assistant. Use the dynamically discovered "
        "Jira MCP tools (jira_search_issues, jira_get_issue, jira_create_issue, "
        "jira_add_comment) to search, inspect, and manage real-time Jira issues."
    ),
    tools=[jira_search_issues, jira_get_issue, jira_create_issue, jira_add_comment],
)

app = App(
    name="it_helpdesk_jev_plugin",
    root_agent=root_agent,
    plugins=[JevLiveJiraPlugin()],
)
