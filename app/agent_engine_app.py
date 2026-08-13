"""Native ADK Agent Engine app entrypoint with tracing enabled."""
import os
import vertexai
from vertexai.agent_engines import AdkApp
from app.agent import app

vertexai.init(
    project=os.environ.get("GOOGLE_CLOUD_PROJECT", "uppdemos"),
    location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
)

adk_app = AdkApp(
    app=app,
    enable_tracing=True,
)
