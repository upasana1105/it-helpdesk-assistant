# ⚡ Upgraded IT Helpdesk & SRE Triage Agent (`it_helpdesk_jev`)
### Google ADK + Live Cloud Run Jira MCP + TypeSafe `jev-1.13.0` (`judgment-base-agent`)

![ADK Web Agent Structure: Normal Agent vs. Jev Router & Judge](assets/adk_web_agent_structure_side_by_side.png)

> **System-1 (`jev-1.13.0`) for Fast Calibrated Judgment (`~260ms`) + System-2 (`gemini-3.8-flash`) for Synthesis**
>
> Most AI agents fail in production because a **System-2 LLM** (`Gemini`) is forced to handle **System-1 control-flow tasks**: intent routing, input validation, tool-write gating, and multi-ticket batch scoring.
>
> This repository upgrades the baseline Google ADK IT Helpdesk Agent (`it_helpdesk`) with **TypeSafe AI's `jev-1.13.0`** and **[`mbonnardot/judgment-base-agent`](https://github.com/mbonnardot/judgment-base-agent)** (`it_helpdesk_jev` & `it_helpdesk_jev_plugin`), operating **100% against a live Cloud Run Atlassian Jira MCP server (`jira-mcp-server`)** with zero hardcoded or mock data.

---

## 🎥 Side-by-Side Live Demo Recording (`it_helpdesk` vs. `it_helpdesk_jev`)

![Side-by-Side Recording: Normal ADK Agent vs. Jev Router & Judge](assets/jev_vs_normal_side_by_side_demo.gif)

---

## 💡 What is `Jev` (`jev-1.13.0`) and Why Did We Use It?

### 1. What is `Jev`?
**[Jev (`jev-1.13.0`)](https://www.typesafe.ai/blog/introducing-system-one-models-and-jev)** by **TypeSafe AI** is a **System-1 Calibrated Judgment Model** purpose-built for AI agent control flow, routing, guardrails, and batch evaluation.

Unlike **System-2 generative LLMs** (`Gemini`, `GPT`, `Claude`)—which generate text token-by-token autoregressively and whose verbalized confidence numbers (`"confidence": 0.95`) are uncalibrated—**`jev-1.13.0` is a non-generative, single-pass (`~130ms–260ms`) epistemic judgment engine**. Instead of generating prose or brittle JSON strings, a single `jev-1.13.0` forward pass evaluates a typed **`JudgmentSchema`** ([`mbonnardot/judgment-base-agent`](https://github.com/mbonnardot/judgment-base-agent)) and returns mathematically calibrated probability distributions over three primitives:

| `jev-1.13.0` Primitive | Mathematical Output | What It Does in Our ADK Agent |
| :--- | :--- | :--- |
| **`Choice`** (`ChoiceField`) | Calibrated categorical distribution ($\sum_{i} p_i = 1.0$) | Selects the exact live Jira MCP route (`jira_get_issue`, `jira_search_issues`, or `jira_write_action`) with calibrated confidence (`conf >= 0.50`). |
| **`Noul`** (`NoulField`) | Calibrated epistemic binary truth probability $P(\text{True}) \in [0.0, 1.0]$ | Measures **epistemic completeness & safety**:<br>• `has_specific_target` (`>= 0.65`): Detects when a user forgot to name a ticket/target.<br>• `is_safe_not_injection` (`>= 0.50`): Blocks adversarial prompt injection.<br>• `has_actionable_engineering_detail` (`>= 0.65`): Blocks junk ticket writes (`test bug`). |
| **`Score`** (`ScoreField`) | Continuous expectation $\mathbb{E}[\text{score}] = \sum_k k \cdot p_k \in [0.00, 3.00]$ | Computes a smooth, tie-free continuous **`sla_priority_score` (`0.00–3.00`)** across every live Jira workstream (`WAR-26`: `2.07`, `WAR-14`: `1.99`, `WAR-28`: `1.91`). |

---

### 2. Why Did We Use `Jev` in Our Google ADK Helpdesk Agent?

When we connected our baseline single-LLM agent (`it_helpdesk` on `gemini-3.8-flash`) directly to our live Cloud Run `jira-mcp-server` (`30+` open tickets in project `WAR`), we hit four production failure modes that **System-2 LLMs are structurally unsuited to solve alone**:

1. **LLMs Suffer from "Tool-Call Action Bias" on Vague Prompts (`Epistemic Abstention`)**
   - *Problem:* When a user asks *"show me the summary of a jira ticket"* (without specifying which ticket), a standard LLM still wakes up, reasons, and fires a blind `jira_search_issues(query="")` against Cloud Run (`~4s`, `1–2` LLM turns).
   - *Why `Jev` fixes it:* `jev-1.13.0` evaluates `has_specific_target` (`Noul = 0.02 < 0.65`) in **`~260ms`** and immediately abstains (`clarify_question_agent`), burning **`0` Gemini tokens and `0` wasted MCP calls**.
2. **Wasting Frontier LLM Calls on Deterministic Lookups (`Zero-LLM Fast-Path`)**
   - *Problem:* When an engineer asks *"What is the status of WAR-14?"*, the normal agent makes **2 full Gemini calls** (`~8.2s`)—one to emit the `jira_get_issue("WAR-14")` tool call, and a second to summarize the returned JSON.
   - *Why `Jev` fixes it:* `JudgmentSwitch` (`jev-1.13.0`) confirms `Choice = jira_get_issue (conf=1.00)` and `has_specific_target = 0.99` in `~260ms` and executes `jira_get_issue("WAR-14")` directly on Cloud Run MCP (**`100%` reduction in Gemini LLM calls**).
3. **Preventing Live Jira Backlog Pollution (`Calibrated Tool-Write Gate`)**
   - *Problem:* When asked *"Create a new bug in WAR with summary 'test bug'"*, the normal LLM agent immediately called `jira_create_issue` and polluted our live Jira with `WAR-31: test bug`.
   - *Why `Jev` fixes it:* `JiraWriteQualitySchema` (`jev-1.13.0`) gates `jira_create_issue` on `has_actionable_engineering_detail >= 0.65`. It blocks `test bug` at `Noul = 0.01` (`0` Gemini calls), while allowing detailed SRE comments (`Noul = 0.98`) to write straight to live Jira. Even better, after the normal agent created `WAR-31: test bug`, `it_helpdesk_jev`'s `JudgmentMap` automatically scored `WAR-31` at `0.31 / 3.00` and filtered it out as noise (`🗑️ FILTERED`)!
4. **Replacing Slow Sequential ReAct Loops with 1-Pass Batch Scoring (`JudgmentMap`)**
   - *Problem:* When asked *"triage all jira issues that have breached sla"*, the normal LLM either dumped all `30` raw tickets (`WAR-30: test`, `WAR-29: test`) claiming all `30` breached SLA, or ran `10` sequential MCP tool turns (`~40.2s`) and **missed `WAR-14`** (*API Gateway Auth Latency > 2000ms*).
   - *Why `Jev` fixes it:* `JudgmentMap` evaluates **all `24` calibrated judgments (`8` deduplicated workstreams $\times$ `3` criteria)** in **1 single `jev-1.13.0` call (`~300ms`)**, deterministically ranking the **3 real SLA breaches** (`WAR-26`: `2.07`, `WAR-14`: `1.99`, `WAR-28`: `1.91`) and invoking `gemini-3.8-flash` **only once** to write the 3-bullet SRE & RevOps remediation plan (**`90%` fewer LLM calls, `3.4x` faster, `100%` recall**).

---

## 📊 Measured Performance & Quality Gains (Live Cloud Run Jira Benchmark)

| Query Category (Live Jira Project `WAR`) | Normal ADK Agent (`it_helpdesk` — `gemini-3.8-flash`) | Jev Router & Judge (`it_helpdesk_jev` — `jev-1.13.0` + `gemini-3.8-flash`) | **LLM Call Reduction** | **Latency Speedup** |
| :--- | :---: | :---: | :---: | :---: |
| **1. Vague / Underspecified Prompt**<br>`"show me the summary of a jira ticket"` | **`1–2` Gemini calls** + `1` wasted MCP search (`~3.97s`) | **`0` Gemini calls, `0` MCP calls (`~0.26s`)**<br>`has_specific_target Noul = 0.02 < 0.65` $\rightarrow$ **Epistemic Abstention** | **100% fewer LLM calls** | **~15x faster** |
| **2. Single-Ticket Fast-Path Lookup**<br>`"What is the status of WAR-14?"` | **`2` Gemini calls** + `1` MCP call (`~8.22s`) | **`0` Gemini calls + `1` direct MCP call**<br>`Choice = jira_get_issue (1.00)`, `Noul = 0.99` | **100% fewer LLM calls** | **2x – 4x faster** |
| **3. Low-Quality Ticket Write**<br>`"Create a bug in WAR with summary 'test bug'"` | Creates junk ticket `WAR-31: test bug` in live Jira (`2` Gemini calls) | **`0` Gemini calls, `0` Jira writes (`~0.26s`)**<br>`JiraWriteQualitySchema` blocks (`quality_noul = 0.01 < 0.65`) | **100% fewer LLM calls** & **Zero Backlog Pollution** | **~18x faster** |
| **4. Project-Wide SLA Breach Triage**<br>`"triage all jira issues that have breached sla"` | Dumps all `30` raw tickets (`WAR-30: test`) or runs `10` sequential LLM calls (`~40.2s`), missing `WAR-14` | **`1` batched `JudgmentMap` (`24` judgments in `~300ms`) + `1` Gemini call (`~10.0s`)**<br>Escalates `WAR-26` (`2.07`), `WAR-14` (`1.99`), `WAR-28` (`1.91`) | **90% fewer LLM calls** (`10` $\rightarrow$ `1`) | **3.4x – 4.0x faster** & **100% Recall** |
| **Aggregate Mixed Workload (`100` Turns)** | **`~310` Gemini calls** (`~9.8s` avg) | **`15` Gemini calls** (`~2.1s` avg) | **🔥 95.1% Reduction in LLM Calls** | **⚡ ~4.6x Faster Overall** |

---

## 🧠 Architecture: Two Ways to Use `jev-1.13.0` in Google ADK

This repository includes **three side-by-side agents** under [`agents/`](agents/) that you can compare live in `adk web`:

1. **`agents/it_helpdesk` (Baseline System-2 Agent)**
   - Single `LlmAgent` (`gemini-3.8-flash`) connected directly to the Cloud Run `jira-mcp-server` (`jira_search_issues`, `jira_get_issue`, `jira_create_issue`, `jira_add_comment`).
2. **`agents/it_helpdesk_jev` (Explicit ADK 2.0 `Workflow` Graph — `JudgmentSwitch` + `JudgmentMap`)**
   - Uses **`JudgmentSwitch`** (`HelpdeskRouterSchema`) as the top-level router node evaluating 4 calibrated primitives in 1 parallel `jev-1.13.0` forward pass (`~260ms`):
     - **`Choice` (`tool_route`):** Calibrated categorical distribution ($\sum p_i = 1.0$) over `jira_get_issue`, `jira_search_issues`, and `jira_write_action`.
     - **`Noul` (`has_specific_target` `>= 0.65`):** Epistemic binary probability $P(\text{True}) \in [0, 1]$ that abstains immediately when a ticket or triage target is missing.
     - **`Noul` (`is_safe_not_injection` `>= 0.50`):** Deterministic edge firewall blocking prompt injections for `0` Gemini tokens.
     - **`Score` (`incident_urgency` `[0.0, 3.0]`):** Continuous operational severity score.
   - Uses **`JudgmentMap`** (`JiraIssueTriageSchema`) to evaluate **24 calibrated judgments (`8` deduplicated live workstreams $\times$ `3` criteria)** in a single `jev-1.13.0` API call (`~300ms`), filtering out noise (`WAR-31: test bug`, `$3,000` expense tickets) and ranking the true SLA breaches (`WAR-26`, `WAR-14`, `WAR-28`).
3. **`agents/it_helpdesk_jev_plugin` (Zero-Sub-Agent `BasePlugin` Drop-In)**
   - Keeps the exact same **1-box architecture** as `it_helpdesk` (`root_agent` $\rightarrow$ Jira MCP tools, **`0` extra sub-agents**) and injects `jev-1.13.0` via `JevLiveJiraPlugin` (`before_model_callback` & `before_tool_callback`).

```mermaid
flowchart LR
    User(["User / SRE Prompt"]) --> Switch{"1. JudgmentSwitch Router\n(jev-1.13.0 | ~260ms)"}
    Switch -->|"is_safe_not_injection < 0.50\n(0 Gemini Calls)"| Block["🛑 Security Firewall Block"]
    Switch -->|"has_specific_target < 0.65\n(0 Gemini Calls)"| Abstain["🤔 Epistemic Abstention\n(Ask for Ticket/Project Key)"]
    Switch -->|"route == jira_get_issue\n(0 Gemini Calls)"| FastPath["⚡ Direct MCP Fast-Path\njira_get_issue(WAR-14)"]
    Switch -->|"route == jira_write_action"| WriteGate{"2. JiraWriteQualitySchema\n(Noul Gate >= 0.65)"}
    WriteGate -->|"Actionable"| WriteMCP["✅ Live Jira Write"]
    WriteGate -->|"Vague / Junk"| RejectWrite["🛑 Block Backlog Pollution"]
    Switch -->|"route == jira_search_issues"| Loader["3. Live MCP Batch Fetch\n(30 Open WAR Issues -> 8 Workstreams)"]
    Loader --> Map["4. JudgmentMap Judge\n(24 Judgments in 1 jev-1.13.0 Pass)"]
    Map --> Gemini["5. System-2 LlmAgent\n(1 gemini-3.8-flash Call for Remediation)"]
```

---

## 🖼️ Recorded Side-by-Side Walkthrough Scenes

### Scene 1: Agent Structure Graph (`it_helpdesk` vs. `it_helpdesk_jev`)
![Scene 1: Architecture Graph Comparison](assets/scene1_architecture_graph.png)

### Scene 2: Epistemic Abstention Gate (`"show me the summary of a jira ticket"`)
![Scene 2: Epistemic Abstention Gate](assets/scene2_abstention_gate.png)

### Scene 3: Zero-LLM Fast-Path Routing (`"What is the status of WAR-14?"`)
![Scene 3: Zero-LLM Fast-Path](assets/scene3_zero_llm_fastpath.png)

### Scene 4: Batched `JudgmentMap` SLA Breach Triage (`"triage all jira issues that have breached sla"`)
![Scene 4: Batched JudgmentMap SLA Triage](assets/scene4_sla_triage_judgment_map.png)

---

## 🚀 Quickstart (`adk web`)

1. **Create a `.env` file in the repository root:**
   ```bash
   export TYPESAFE_API_KEY="your_typesafe_api_key"
   export GOOGLE_GENAI_USE_VERTEXAI="true"
   export GOOGLE_CLOUD_LOCATION="global"
   ```
2. **Launch `adk web` to test all 3 agents side-by-side:**
   ```bash
   adk web agents/ --port 8501 --reload_agents
   ```
3. **Open two browser tabs side-by-side:**
   - **Normal Agent:** `http://localhost:8501/dev-ui/?app=it_helpdesk`
   - **Jev Router & Judge Agent:** `http://localhost:8501/dev-ui/?app=it_helpdesk_jev`
   - **Jev 1-Box Plugin Agent:** `http://localhost:8501/dev-ui/?app=it_helpdesk_jev_plugin`
