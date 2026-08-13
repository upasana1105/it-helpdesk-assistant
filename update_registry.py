import subprocess
import httpx
import json

print("Patching Agent Registry entry agentregistry-00000000-0000-0000-e990-7934b15623d6...")

token = subprocess.check_output(['gcloud', 'auth', 'print-access-token', 'admin@upasanapati.altostrat.com'], text=True).strip()

headers = {
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json'
}

url = 'https://us-central1-aiplatform.googleapis.com/v1beta1/projects/uppdemos/locations/us-central1/agents/agentregistry-00000000-0000-0000-e990-7934b15623d6?updateMask=description,version,card,protocols,attributes'


card_payload = {
    'type': 'A2A_AGENT_CARD',
    'content': {
        'name': 'it-helpdesk-adk-v3',
        'description': 'Enterprise IT Helpdesk AI Assistant with ADK & MCP Server integration.',
        'version': '0.1.0',
        'url': 'https://us-central1-aiplatform.googleapis.com/v1beta1/projects/850431687571/locations/us-central1/reasoningEngines/8405037967894118400/a2a',
        'preferredTransport': 'HTTP+JSON',
        'protocolVersion': '0.3.0',
        'capabilities': {'streaming': True},
        'defaultInputModes': ['text/plain'],
        'defaultOutputModes': ['text/plain']
    }
}

protocols_payload = [
    {
        'type': 'A2A_AGENT',
        'protocolVersion': '0.3.0',
        'interfaces': [
            {
                'url': 'https://us-central1-aiplatform.googleapis.com/v1beta1/projects/850431687571/locations/us-central1/reasoningEngines/8405037967894118400/a2a',
                'protocolBinding': 'HTTP_JSON'
            }
        ]
    },
    {
        'type': 'CUSTOM',
        'interfaces': [
            {
                'url': 'https://us-central1-aiplatform.googleapis.com/v1/projects/850431687571/locations/us-central1/reasoningEngines/8405037967894118400:query',
                'protocolBinding': 'HTTP_JSON'
            },
            {
                'url': 'https://us-central1-aiplatform.googleapis.com/v1/projects/850431687571/locations/us-central1/reasoningEngines/8405037967894118400:streamQuery',
                'protocolBinding': 'HTTP_JSON'
            }
        ]
    }
]

attributes_payload = {
    'agentregistry.googleapis.com/system/Framework': {
        'framework': 'google-adk'
    },
    'agentregistry.googleapis.com/system/RuntimeIdentity': {
        'principal': 'principal://agents.global.org-430279468368.system.id.goog/resources/aiplatform/projects/850431687571/locations/us-central1/reasoningEngines/8405037967894118400'
    },
    'agentregistry.googleapis.com/system/RuntimeReference': {
        'uri': '//aiplatform.googleapis.com/projects/850431687571/locations/us-central1/reasoningEngines/8405037967894118400'
    }
}

payload = {
    'description': 'Enterprise IT Helpdesk AI Assistant with ADK & MCP Server integration.',
    'version': '0.1.0',
    'card': card_payload,
    'protocols': protocols_payload,
    'attributes': attributes_payload
}

resp = httpx.patch(url, headers=headers, json=payload)
print('Patch Status:', resp.status_code)
print('Patch Response:\n', resp.text[:1000])
