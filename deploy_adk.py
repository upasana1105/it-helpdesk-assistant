import subprocess
import vertexai
from google.oauth2 import credentials
from vertexai._genai.client import Client
from app.agent import root_agent

print("Starting native ADK Agent Engine deployment via Client(agent=root_agent)...")

token = subprocess.check_output(['gcloud', 'auth', 'print-access-token', 'admin@upasanapati.altostrat.com'], text=True).strip()
creds = credentials.Credentials(token)

client = Client(
    project='uppdemos',
    location='us-central1',
    credentials=creds
)

config = {
    'display_name': 'it-helpdesk-adk-v5',
    'description': 'Enterprise IT Helpdesk AI Assistant with ADK & MCP Server integration.',
    'requirements': [
        'google-genai>=1.0.0',
        'google-adk>=1.36.0',
        'fastapi>=0.110.0',
        'uvicorn>=0.30.0',
        'httpx>=0.27.0',
        'mcp>=1.2.0'
    ]
}

remote_agent = client.agent_engines.create(
    agent=root_agent,
    config=config,
    staging_bucket='gs://uppdemos-agent-staging'
)


print("\n✅ Native ADK Agent Engine successfully created!")
print("Resource Name:", getattr(remote_agent, 'name', remote_agent))
