"""ADK Security Plugin integrating Google Cloud Model Armor via REST API with OpenTelemetry Trace attributes."""
import logging
import os
import requests
from typing import Any, Optional
from google.adk.plugins import BasePlugin
from app.mcp_discovery import get_auth_token
from opentelemetry import trace

logger = logging.getLogger(__name__)

class ModelArmorSecurityPlugin(BasePlugin):
    """ADK Security Plugin integrating Model Armor via REST API for Cloud Run compatibility."""
    def __init__(
        self,
        name: str = "model_armor_security_plugin",
        project_id: str = "uppdemos",
        location: str = "us",
        template_id: str = "it-helpdesk-security-template"
    ):
        super().__init__(name=name)
        self.project_id = project_id
        self.location = location
        self.template_id = template_id

    @property
    def sanitize_url(self) -> str:
        return f"https://modelarmor.{self.location}.rep.googleapis.com/v1/projects/{self.project_id}/locations/{self.location}/templates/{self.template_id}:sanitizeUserPrompt"

    async def before_model_callback(
        self,
        agent: Any = None,
        callback_context: Any = None,
        llm_request: Any = None,
        **kwargs: Any,
    ) -> Optional[Any]:
        """Sanitize user prompt turns using Model Armor before LLM inference."""
        req_obj = llm_request or getattr(callback_context, "llm_request", None)
        if not req_obj or not getattr(req_obj, "contents", None):
            return None

        last_content = req_obj.contents[-1]
        if getattr(last_content, "role", None) != "user":
            return None

        user_text_parts = [
            part.text
            for part in getattr(last_content, "parts", [])
            if hasattr(part, "text") and part.text
        ]
        if not user_text_parts:
            return None

        prompt_text = " ".join(user_text_parts)
        try:
            token = get_auth_token()
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            payload = {"user_prompt_data": {"text": prompt_text}}
            resp = requests.post(self.sanitize_url, headers=headers, json=payload, timeout=3)
            if resp.status_code == 200:
                result = resp.json().get("sanitizationResult", {})
                if result.get("filterMatchState") == "MATCH_FOUND":
                    logger.warning(f"Model Armor flagged security violation in prompt: {result}")
                    current_span = trace.get_current_span()
                    if current_span and current_span.is_recording():
                        current_span.set_attribute("gcp.modelarmor.filter.match.state", "MATCH_FOUND")
                        current_span.set_attribute("gcp.modelarmor.violations", str(result.get("filterResults", {})))
        except Exception as err:
            logger.warning(f"Model Armor screening exception: {err}")
        return None
