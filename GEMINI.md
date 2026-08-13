# Gemini AI Rules & Guidelines

## 📌 Core Engineering Rules
1. **ADK Architecture**: Use standard Google ADK primitives (`Agent`, `Gemini`, `Tool`, `AgentRegistry`). Enforce version constraint **`google-adk>=1.36.0,<2.0.0`**. Decouple core agent definitions (`agent.py`) from HTTP serving layers (`app/fast_api_app.py`).
2. **Model Selection**: Default to `gemini-3.6-flash`. Use `gemini-3.1-pro` ONLY for complex multi-step reasoning. Do NOT use `gemini-1.5-flash`.
3. **Security Guardrails & Sanitization**:
   - Pass user prompts and model outputs through `ModelArmorPlugin` with local fallback support.
   - **Input Sanitization**: Validate string parameters and strip dangerous control tokens to block prompt injection.
   - **Output Sanitization**: Redact sensitive PII (passwords, auth tokens, emails, SSNs) and sanitize HTML/Markdown outputs before client rendering.
4. **Data Privacy**: Scope long-term memory and session context strictly by `user_id`.
5. **Secrets Handling**: Load credentials from `.env` or system env vars. Mask secrets in logs. Never hardcode keys or commit credentials.

## ✍️ Code Quality & Standards
- **Type Safety**: Python 3.12+ with explicit type hints for all parameters and return types. Avoid raw `Any`.
- **Dependencies**: Pin `google-adk>=1.36.0,<2.0.0` and `google-genai>=1.0.0` in `pyproject.toml`.
- **Linting & Formatting**: Clean, modular functions conforming to PEP 8 standards. Use non-blocking `httpx` for external I/O.
- **Test Coverage**: Require `pytest` unit tests for native tools and integration tests for FastMCP servers.
- **Logging Hygiene**: Use `logging.getLogger(__name__)`. Mask sensitive authorization headers and tokens in log outputs.

## 🧠 Regionality & Global Model Routing
- **Agent Runtime**: Hosted in regional location (`environment.region: us-central1` in `agents-cli-manifest.yaml`).
- **Global Model Endpoint**: `gemini-3.6-flash` is global/multi-region. Instantiate `Gemini(model="gemini-3.6-flash", location="global")` to route inference from regional runtime to global model servers.
- **Managed ADK Engine**: Deploy via `agents-cli deploy` for GCP managed serverless execution.
- **FastAPI A2A Protocol**: Deploy `app/fast_api_app.py` (`POST /a2a/app`) for inter-agent mesh networks and Agent Gateway routing.

## 🌿 Git & GitHub Branching Workflow
- **Branch Conventions**:
  - Features: `feature/<feature-name>` or `feat/<short-name>`
  - Fixes: `fix/<issue-id>-<short-description>`
  - Maintenance: `chore/<description>` or `refactor/<description>`
- **Check-in & PR Runbook**:
  ```bash
  git checkout main && git pull origin main
  git checkout -b feat/add-agent-tool
  pytest
  git add .
  git commit -m "feat(tools): add new tool binding"
  git push -u origin feat/add-agent-tool
  ```

## 🛠 `agents-cli` Workflow
- **Skill Scaffolding**: `agents-cli skill create <skill_name>` to define modular skills under `.agents/skills/`.
- **Evaluation & Deployment**: `agents-cli eval` for benchmarks, `agents-cli deploy` for Agent Runtime deployment. Register in GCP `AgentRegistry` for Gemini Enterprise integration.

## 📚 Skills Usage
- **Progressive Discovery**: Skills reside in `.agents/skills/<skill_name>/SKILL.md`. Read on-demand via `view_file` to keep context window lean.

## 🚀 Development Operations
```bash
# Setup & Test
cp .env.example .env && uv sync
pytest

# Run Dev Servers
python server_mcp.py
uvicorn app.fast_api_app:app --host 0.0.0.0 --port 8080 --reload
```
