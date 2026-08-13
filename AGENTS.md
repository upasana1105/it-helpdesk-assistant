# Agent & Tool Specifications

## 🤖 Agent Specs & Model Routing
- **Framework & ADK Version**: `google-adk>=1.36.0,<2.0.0` (Google Agent Development Kit v1.36+)
- **Model Selection**: Default `gemini-3.6-flash`. Complex reasoning `gemini-3.1-pro`. (No `gemini-1.5-flash`).
- **Runtime Regionality vs Model Routing**:
  - **Agent Runtime**: Hosted in a specific **region** (e.g. `us-central1`). Set `environment.region: us-central1` in `agents-cli-manifest.yaml`.
  - **`gemini-3.6-flash` Location**: `gemini-3.6-flash` is served via **global & multi-region** endpoints.
  - **Inference Routing**: Explicitly set `location="global"` on model wrapper: `Gemini(model="gemini-3.6-flash", location="global")`.

## 🛠 Tool Rules, Code Quality & Sanitization
1. **Docstrings & Types**: All tools must have explicit docstrings and strict Python parameter/return type annotations.
2. **Input Sanitization**: Validate string inputs in tools to prevent prompt injection and unauthorized API queries.
3. **Output Sanitization**: Redact sensitive keys, authorization headers, or PII from tool return values.
4. **Native Tools**: Function call tools bound directly to ADK `Agent(tools=[...])`.
5. **FastMCP Tools**: Exposed via HTTP/SSE. Registered via GCP `AgentRegistry` (`projects/{PROJECT_ID}/locations/{REGION}/mcpServers/*`). Must fall back to native tools if offline.

## 🔒 Execution & Sanitization Pipeline
```
User Input ➡️ Sanitize Input ➡️ ModelArmor Pre-Hook ➡️ Memory Preload ➡️ Reasoning & Tools ➡️ ModelArmor Post-Hook ➡️ Redact Output ➡️ Client Response
```

## 🛠 `agents-cli` Skills & Agent Lifecycle
- **Scaffold Agent**: `agents-cli init`
- **Create Skills**: `agents-cli skill create <skill_name>` (creates `.agents/skills/<skill_name>/SKILL.md`).
- **Evaluate Agent**: `agents-cli eval`
- **Deploy Agent**: `agents-cli deploy --no-confirm-project`
- **Register in GE**: Publish deployed Agent Engine or FastMCP server to GCP `AgentRegistry` (`projects/{PROJECT_ID}/locations/{REGION}/mcpServers/*`) and bind URI to Gemini Enterprise Data Connectors.

## 🌐 A2A Protocol Specs
- **Endpoint**: `POST /a2a/app`
- **Payload**: `{"user_id": str, "session_id": str, "message": str, "context": dict}`

## 📚 Skills
- `adk-agent-deployment`: Production deployment runbook (ModelArmor fallback, Agent Gateway A2A routing, `AgentRegistry` lookups).
