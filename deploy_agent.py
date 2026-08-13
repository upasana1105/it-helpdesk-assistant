"""Deploy IT Helpdesk Assistant to Vertex AI Reasoning Engine."""
import os
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("deploy_agent")

import vertexai
from vertexai.preview import reasoning_engines
from app.agent import ITHelpdeskAgent

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "uppdemos")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
STAGING_BUCKET = f"gs://{PROJECT_ID}-agent-staging"

def deploy():
    logger.info(f"Initializing Vertex AI for project: {PROJECT_ID}, location: {LOCATION}...")
    vertexai.init(project=PROJECT_ID, location=LOCATION, staging_bucket=STAGING_BUCKET)

    logger.info("Instantiating ITHelpdeskAgent...")
    agent_instance = ITHelpdeskAgent()

    logger.info("Deploying to Vertex AI Reasoning Engine...")
    remote_agent = reasoning_engines.ReasoningEngine.create(
        agent_instance,
        requirements=[
            "google-genai>=0.1.0",
            "pydantic>=2.6.0",
            "httpx>=0.27.0",
            "python-dotenv>=1.0.0",
            "fastapi>=0.110.0"
        ],
        extra_packages=["app"],
        display_name="it-helpdesk-assistant",
        description="Enterprise IT Helpdesk AI Assistant with Vertex Memory Bank and Model Armor guardrails."
    )

    logger.info("Successfully deployed Reasoning Engine!")
    logger.info(f"Resource Name: {remote_agent.resource_name}")
    print(f"\nDEPLOYMENT_SUCCESS: {remote_agent.resource_name}\n")
    return remote_agent.resource_name

if __name__ == "__main__":
    deploy()
