"""Core JudgmentAgent(BaseAgent), JudgmentDecision, and @judgment_node decorator."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable, Mapping, Sequence
from dataclasses import dataclass, field
import inspect
import json
import sys
from typing import Any

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.adk.events.request_input import RequestInput
from google.adk.workflow.utils._workflow_hitl_utils import (
    create_request_input_event,
)
from google.genai import types
from pydantic import BaseModel, ConfigDict

from judgment_base_agent.backends.base import BaseJudgmentBackend
from judgment_base_agent.backends.typesafe import TypeSafeBackend
from judgment_base_agent.errors import JudgmentConfigError
from judgment_base_agent.primitives import JudgmentResult
from judgment_base_agent.schema import JudgmentSchema


@dataclass(frozen=True)
class JudgmentDecision:
    """User-returned decision envelope controlling ADK Event output, routing, and escalation."""

    output: Any = None
    route: str | int | bool | list[str] | None = None
    escalate: bool | None = None
    transfer_to_agent: str | None = None
    state_delta: dict[str, Any] = field(default_factory=dict)
    request_input_id: str | None = None
    request_input_prompt: str | None = None

    @property
    def branch(self) -> str | int | bool | list[str] | None:
        """Alias for route."""
        return self.route

    @property
    def state_updates(self) -> dict[str, Any]:
        """Alias for state_delta."""
        return self.state_delta


def normalize_decision(
    raw_decision: Any,
    default_output: Any,
    transfer_to_sub_agent: bool = False,
) -> JudgmentDecision:
    """Normalize user decide() return value (str, bool, dict, JudgmentDecision) into JudgmentDecision."""
    if raw_decision is None:
        return JudgmentDecision(output=default_output)
    if isinstance(raw_decision, JudgmentDecision):
        return JudgmentDecision(
            output=raw_decision.output if raw_decision.output is not None else default_output,
            route=raw_decision.route,
            escalate=raw_decision.escalate,
            transfer_to_agent=raw_decision.transfer_to_agent,
            state_delta=dict(raw_decision.state_delta),
            request_input_id=raw_decision.request_input_id,
            request_input_prompt=raw_decision.request_input_prompt,
        )
    if isinstance(raw_decision, bool):
        return JudgmentDecision(
            output=default_output,
            route="pass" if raw_decision else "fail",
            escalate=raw_decision,
        )
    if isinstance(raw_decision, str):
        return JudgmentDecision(
            output=default_output,
            route=raw_decision,
            transfer_to_agent=raw_decision if transfer_to_sub_agent else None,
        )
    if isinstance(raw_decision, list):
        return JudgmentDecision(output=default_output, route=raw_decision)
    return JudgmentDecision(output=raw_decision)


def _extract_node_input(ctx: InvocationContext) -> Any:
    """Extract predecessor output or latest user message text from ADK InvocationContext."""
    if ctx.session and ctx.session.events:
        for ev in reversed(ctx.session.events):
            if getattr(ev, "output", None) is not None:
                return ev.output
            if ev.content and ev.content.parts:
                texts = [p.text for p in ev.content.parts if getattr(p, "text", None)]
                if texts:
                    return "\n".join(texts)
    if ctx.user_content and ctx.user_content.parts:
        texts = [p.text for p in ctx.user_content.parts if getattr(p, "text", None)]
        if texts:
            return "\n".join(texts)
    return None


def _serialize_output(val: Any) -> Any:
    """Ensure output is JSON-serializable for ADK Event.output and state_delta."""
    if isinstance(val, BaseModel):
        return val.model_dump()
    return val


class JudgmentAgent(BaseAgent):
    """Model-agnostic System One / Judgment step for Google ADK 2.0 Workflows & Composite Agents."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    model: str = "judgment-latest"
    schema_cls: type[JudgmentSchema] | None = None
    questions: Mapping[str, Any] | Callable[..., Mapping[str, Any]] | None = None
    state_keys: Sequence[str] | None = None
    state_builder: Callable[..., Any] | None = None
    output_key: str | None = None
    decide: Callable[..., Any] | None = None
    on_error: Callable[[Exception, dict[str, Any]], JudgmentDecision] | None = None
    transfer_to_sub_agent: bool = False
    backend: BaseJudgmentBackend | None = None

    def __init__(
        self,
        *,
        name: str,
        description: str = "",
        model: str = "judgment-latest",
        schema: type[JudgmentSchema] | None = None,
        questions: Mapping[str, Any] | Callable[..., Mapping[str, Any]] | None = None,
        state_keys: Sequence[str] | None = None,
        state_builder: Callable[..., Any] | None = None,
        output_key: str | None = None,
        decide: Callable[..., Any] | None = None,
        on_error: Callable[[Exception, dict[str, Any]], JudgmentDecision] | None = None,
        transfer_to_sub_agent: bool = False,
        backend: BaseJudgmentBackend | None = None,
        sub_agents: Sequence[BaseAgent] | None = None,
    ) -> None:
        if schema is None and questions is None and not hasattr(self, "_custom_evaluate"):
            raise JudgmentConfigError(
                f"JudgmentAgent '{name}' requires either `schema` (a JudgmentSchema subclass) "
                "or `questions` (a dict or callable)."
            )
        super().__init__(
            name=name,
            description=description or f"Evaluates calibrated judgments using {model}.",
            sub_agents=list(sub_agents or []),
            model=model,
            schema_cls=schema,
            questions=questions,
            state_keys=list(state_keys) if state_keys is not None else None,
            state_builder=state_builder,
            output_key=output_key,
            decide=decide,
            on_error=on_error,
            transfer_to_sub_agent=transfer_to_sub_agent,
            backend=backend or TypeSafeBackend(default_model=model),
        )

    def _resolve_state(
        self, session_state: dict[str, Any], node_input: Any
    ) -> Any:
        if self.state_builder is not None:
            sig = inspect.signature(self.state_builder)
            if len(sig.parameters) >= 2:
                return self.state_builder(session_state, node_input)
            return self.state_builder(session_state)
        if self.state_keys is not None:
            return {k: session_state.get(k) for k in self.state_keys}
        if node_input is not None and node_input != "":
            return node_input
        return session_state

    def _resolve_questions(
        self, state_payload: Any, session_state: dict[str, Any], node_input: Any
    ) -> Mapping[str, Any]:
        if self.schema_cls is not None:
            return self.schema_cls.build_questions()
        if callable(self.questions):
            sig = inspect.signature(self.questions)
            if len(sig.parameters) >= 2:
                return self.questions(state_payload, node_input)
            return self.questions(state_payload)
        return dict(self.questions or {})

    async def _evaluate_core(
        self, session_state: dict[str, Any], node_input: Any
    ) -> Any:
        state_payload = self._resolve_state(session_state, node_input)
        resolved_questions = self._resolve_questions(
            state_payload, session_state, node_input
        )
        active_backend = self.backend or TypeSafeBackend(default_model=self.model)
        raw_result: JudgmentResult = await active_backend.evaluate(
            state=state_payload,
            questions=resolved_questions,
            model=self.model,
        )
        if self.schema_cls is not None:
            return self.schema_cls.from_result(raw_result)
        return raw_result

    def _invoke_decide(
        self, typed_output: Any, session_state: dict[str, Any], node_input: Any
    ) -> JudgmentDecision:
        default_serialized = _serialize_output(typed_output)
        if self.decide is None:
            return JudgmentDecision(output=default_serialized)
        sig = inspect.signature(self.decide)
        if len(sig.parameters) >= 3:
            raw_decision = self.decide(typed_output, session_state, node_input)
        elif len(sig.parameters) == 2:
            raw_decision = self.decide(typed_output, session_state)
        else:
            raw_decision = self.decide(typed_output)
        return normalize_decision(
            raw_decision,
            default_output=default_serialized,
            transfer_to_sub_agent=self.transfer_to_sub_agent,
        )

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        session_state = dict(ctx.session.state)
        node_input = _extract_node_input(ctx)

        try:
            typed_output = await self._evaluate_core(session_state, node_input)
            decision = self._invoke_decide(typed_output, session_state, node_input)
        except Exception as exc:
            if self.on_error is not None:
                decision = self.on_error(exc, session_state)
            else:
                raise

        if decision.request_input_id:
            req_event = create_request_input_event(
                RequestInput(
                    interrupt_id=decision.request_input_id,
                    message=decision.request_input_prompt or "Additional input required.",
                )
            )
            req_event.invocation_id = ctx.invocation_id
            req_event.author = self.name
            yield req_event
            return

        final_output = _serialize_output(decision.output)
        state_delta = dict(decision.state_delta)
        if self.output_key:
            state_delta[self.output_key] = final_output

        for k, v in state_delta.items():
            ctx.session.state[k] = v

        yield Event(
            invocation_id=ctx.invocation_id,
            author=self.name,
            output=final_output,
            actions=EventActions(
                state_delta=state_delta,
                route=decision.route,
                escalate=decision.escalate,
                transfer_to_agent=decision.transfer_to_agent,
            ),
            content=types.Content(
                role="model",
                parts=[
                    types.Part.from_text(
                        text=(
                            final_output
                            if isinstance(final_output, str)
                            else json.dumps(final_output, indent=2, default=str)
                        )
                    )
                ],
            ),
        )


def judgment_node(
    *,
    name: str | None = None,
    schema: type[JudgmentSchema] | None = None,
    questions: Mapping[str, Any] | Callable[..., Mapping[str, Any]] | None = None,
    model: str = "judgment-latest",
    state_keys: Sequence[str] | None = None,
    state_builder: Callable[..., Any] | None = None,
    output_key: str | None = None,
    backend: BaseJudgmentBackend | None = None,
) -> Callable[[Callable[..., Any]], JudgmentAgent]:
    """Decorator turning a Python decision function `(result, state) -> decision` into a JudgmentAgent."""

    def decorator(func: Callable[..., Any]) -> JudgmentAgent:
        return JudgmentAgent(
            name=name or func.__name__,
            description=func.__doc__ or "",
            model=model,
            schema=schema,
            questions=questions,
            state_keys=state_keys,
            state_builder=state_builder,
            output_key=output_key,
            decide=func,
            backend=backend,
        )

    return decorator


sys.modules.setdefault("judgment_base_agent/agent", sys.modules[__name__])
