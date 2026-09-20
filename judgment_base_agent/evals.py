"""ADK Evaluation (`google.adk.evaluation`) Rubric-based Judge using Calibrated Judgment."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Optional

from google.adk.evaluation.eval_case import (
    ConversationScenario,
    IntermediateData,
    Invocation,
    InvocationEvents,
)
from google.adk.evaluation.eval_metrics import (
    EvalMetric,
    EvalStatus,
    Interval,
    MetricInfo,
    MetricValueInfo,
    RubricsBasedCriterion,
)
from google.adk.evaluation.eval_rubrics import Rubric, RubricContent, RubricScore
from google.adk.evaluation.evaluator import EvaluationResult, Evaluator, PerInvocationResult
from google.adk.evaluation.metric_evaluator_registry import (
    DEFAULT_METRIC_EVALUATOR_REGISTRY,
    MetricEvaluatorRegistry,
)
from google.genai import types as genai_types
from pydantic import BaseModel, ConfigDict, Field

from judgment_base_agent.backends.base import BaseJudgmentBackend
from judgment_base_agent.backends.typesafe import TypeSafeBackend
from judgment_base_agent.primitives import Noul

DEFAULT_METRIC_NAME = "judgment_rubric_quality_v1"
CLARITY_KEY = "_epistemic_clarity"


class RubricItem(BaseModel):
    """A single weighted and optionally hard-veto criterion in a JudgmentRubric."""

    model_config = ConfigDict(frozen=True)

    rubric_id: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    weight: float = Field(default=1.0, gt=0.0)
    min_score: float = Field(default=0.70, ge=0.0, le=1.0)
    veto: bool = Field(default=False)

    @classmethod
    def from_adk_rubric(cls, rubric: Rubric) -> RubricItem:
        """Creates a RubricItem from a standard google.adk.evaluation.eval_rubrics.Rubric."""
        text_prop = (
            rubric.rubric_content.text_property
            if rubric.rubric_content and rubric.rubric_content.text_property
            else rubric.description or rubric.rubric_id
        )
        is_veto = bool(rubric.type and "VETO" in rubric.type.upper())
        return cls(
            rubric_id=rubric.rubric_id,
            description=text_prop,
            weight=1.0,
            min_score=0.75 if is_veto else 0.70,
            veto=is_veto,
        )

    def to_adk_rubric(self) -> Rubric:
        """Converts this RubricItem into a standard google.adk.evaluation.eval_rubrics.Rubric."""
        return Rubric(
            rubric_id=self.rubric_id,
            rubric_content=RubricContent(text_property=self.description),
            description=f"weight={self.weight}, min_score={self.min_score}, veto={self.veto}",
            type="CRITICAL_VETO" if self.veto else "QUALITY_CRITERION",
        )


class JudgmentRubric(BaseModel):
    """Declarative multi-criteria rubric compiled into calibrated Noul primitives."""

    model_config = ConfigDict(frozen=True)

    question: str = Field(
        default=(
            "Does the agent's response accurately, safely, and completely satisfy "
            "each evaluation rubric criterion for the user's request?"
        ),
        min_length=1,
    )
    items: tuple[RubricItem, ...] = Field(..., min_length=1)
    threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    min_clarity: float = Field(default=0.40, ge=0.0, le=1.0)

    def build_questions(self) -> dict[str, Any]:
        """Builds the batched Noul question dictionary for a single-pass evaluation."""
        questions: dict[str, Any] = {}
        for item in self.items:
            questions[item.rubric_id] = Noul(
                instructions=(
                    "Evaluate the [ACTUAL AGENT RESPONSE] against the [USER REQUEST] "
                    "(and any [TOOL TRAJECTORY & OUTPUTS] or [EXPECTED REFERENCE RESPONSE]). "
                    f"Does the response satisfy this rubric criterion: {item.description}?"
                ),
                criteria={
                    "true": {item.rubric_id: item.description},
                    "false": {
                        f"violates_{item.rubric_id}": f"Fails to satisfy: {item.description}"
                    },
                },
            )
        questions[CLARITY_KEY] = Noul(
            instructions=(
                "Does the evaluation dossier contain a non-empty [USER REQUEST] and "
                "a concrete [ACTUAL AGENT RESPONSE] that can be evaluated against the rubric?"
            ),
            criteria={
                "true": {
                    "evaluable_turn": (
                        "Contains both a user request and a substantive agent response"
                    )
                },
                "false": {
                    "missing_evidence": (
                        "The agent response is empty, missing, or lacks required tool trace"
                    )
                },
            },
        )
        return questions

    @classmethod
    def from_adk_rubrics(
        cls,
        rubrics: Sequence[Rubric],
        *,
        threshold: float = 0.75,
        min_clarity: float = 0.40,
        question: str | None = None,
    ) -> JudgmentRubric:
        """Constructs a JudgmentRubric from a sequence of ADK Rubric definitions."""
        items = tuple(RubricItem.from_adk_rubric(r) for r in rubrics)
        kwargs: dict[str, object] = {
            "items": items,
            "threshold": threshold,
            "min_clarity": min_clarity,
        }
        if question is not None:
            kwargs["question"] = question
        return cls(**kwargs)  # type: ignore[arg-type]


def _extract_content_text(content: Optional[genai_types.Content]) -> str:
    if content is None or not content.parts:
        return ""
    texts: list[str] = []
    for part in content.parts:
        if part.text:
            texts.append(part.text)
    return "\n".join(texts).strip()


def _format_intermediate_data(
    intermediate: Optional[IntermediateData | InvocationEvents],
) -> str:
    if intermediate is None:
        return ""
    lines: list[str] = []
    if isinstance(intermediate, IntermediateData):
        for call in intermediate.tool_uses:
            lines.append(f"- Tool Call: {call.name}({call.args})")
        for resp in intermediate.tool_responses:
            lines.append(f"- Tool Output ({resp.name}): {resp.response}")
    elif isinstance(intermediate, InvocationEvents):
        for event in intermediate.invocation_events:
            txt = _extract_content_text(event.content)
            if txt:
                lines.append(f"- [{event.author}]: {txt}")
    return "\n".join(lines)


class JudgmentRubricEvaluator(Evaluator):
    """Native ADK Evaluator that grades invocations using a calibrated JudgmentRubric."""

    criterion_type = RubricsBasedCriterion

    def __init__(
        self,
        eval_metric: Optional[EvalMetric] = None,
        *,
        rubric: Optional[JudgmentRubric] = None,
        backend: Optional[BaseJudgmentBackend] = None,
        include_tool_trajectory: bool = True,
        include_expected_response: bool = True,
    ) -> None:
        self._eval_metric = eval_metric
        self._rubric = rubric
        self._backend = backend
        self._include_tool_trajectory = include_tool_trajectory
        self._include_expected_response = include_expected_response

    def _resolve_backend(self) -> BaseJudgmentBackend:
        if self._backend is not None:
            return self._backend
        return TypeSafeBackend()

    def _resolve_rubric(self, invocation: Invocation) -> JudgmentRubric:
        if self._rubric is not None:
            return self._rubric

        threshold = 0.75
        adk_rubrics: list[Rubric] = []
        if self._eval_metric is not None:
            if self._eval_metric.threshold is not None:
                threshold = float(self._eval_metric.threshold)
            if isinstance(self._eval_metric.criterion, RubricsBasedCriterion):
                threshold = float(self._eval_metric.criterion.threshold)
                adk_rubrics.extend(self._eval_metric.criterion.rubrics)

        if invocation.rubrics:
            adk_rubrics.extend(invocation.rubrics)

        if not adk_rubrics:
            return JudgmentRubric(
                threshold=threshold,
                items=(
                    RubricItem(
                        rubric_id="helpful_and_accurate",
                        description="Accurately and directly addresses the user's request",
                        weight=1.0,
                    ),
                ),
            )
        return JudgmentRubric.from_adk_rubrics(adk_rubrics, threshold=threshold)

    def _build_evaluation_dossier(
        self,
        actual: Invocation,
        expected: Optional[Invocation],
    ) -> str:
        sections: list[str] = [
            f"[USER REQUEST]\n{_extract_content_text(actual.user_content)}"
        ]
        if self._include_tool_trajectory:
            trace_str = _format_intermediate_data(actual.intermediate_data)
            if trace_str:
                sections.append(f"[TOOL TRAJECTORY & OUTPUTS]\n{trace_str}")

        if self._include_expected_response and expected is not None:
            expected_text = _extract_content_text(expected.final_response)
            if expected_text:
                sections.append(f"[EXPECTED REFERENCE RESPONSE]\n{expected_text}")

        sections.append(
            f"[ACTUAL AGENT RESPONSE]\n{_extract_content_text(actual.final_response)}"
        )
        return "\n\n".join(sections)

    async def evaluate_invocations(
        self,
        actual_invocations: list[Invocation],
        expected_invocations: Optional[list[Invocation]] = None,
        conversation_scenario: Optional[ConversationScenario] = None,
    ) -> EvaluationResult:
        """Evaluates each ADK invocation against the calibrated JudgmentRubric."""
        del conversation_scenario
        if not actual_invocations:
            return EvaluationResult()

        backend = self._resolve_backend()
        per_invocation_results: list[PerInvocationResult] = []
        rubric_score_buckets: dict[str, list[float]] = {}

        for idx, actual in enumerate(actual_invocations):
            expected = (
                expected_invocations[idx]
                if expected_invocations is not None and idx < len(expected_invocations)
                else None
            )
            rubric = self._resolve_rubric(actual)
            dossier = self._build_evaluation_dossier(actual, expected)
            questions = rubric.build_questions()
            judgment_result = await backend.evaluate(dossier, questions)

            clarity_score = (
                judgment_result.noul(CLARITY_KEY)
                if CLARITY_KEY in judgment_result.nouls and judgment_result.noul(CLARITY_KEY) > 0.0
                else 0.90
            )
            abstained = clarity_score < rubric.min_clarity
            veto_failures: list[str] = []
            rubric_scores: list[RubricScore] = []
            weighted_sum = 0.0
            total_weight = 0.0

            for item in rubric.items:
                item_score = float(judgment_result.noul(item.rubric_id))
                weighted_sum += item.weight * item_score
                total_weight += item.weight
                rubric_score_buckets.setdefault(item.rubric_id, []).append(item_score)

                item_vetoed = item.veto and item_score < item.min_score
                if item_vetoed:
                    veto_failures.append(
                        f"{item.rubric_id}={item_score:.2f}<{item.min_score:.2f}"
                    )

                status_tag = "PASS"
                if abstained:
                    status_tag = (
                        f"ABSTAINED (clarity={clarity_score:.2f}<{rubric.min_clarity:.2f})"
                    )
                elif item_vetoed:
                    status_tag = (
                        f"VETO FAILED (score={item_score:.2f}<{item.min_score:.2f})"
                    )
                elif item_score < item.min_score:
                    status_tag = (
                        f"BELOW_MIN (score={item_score:.2f}<{item.min_score:.2f})"
                    )

                rubric_scores.append(
                    RubricScore(
                        rubric_id=item.rubric_id,
                        score=round(item_score, 4),
                        rationale=(
                            f"[{status_tag} | weight={item.weight:.1f} | clarity={clarity_score:.2f}] "
                            f"{item.description}"
                        ),
                    )
                )

            weighted_avg = (
                round(weighted_sum / total_weight, 4) if total_weight > 0 else 0.0
            )
            if abstained:
                inv_status = EvalStatus.NOT_EVALUATED
            elif veto_failures or weighted_avg < rubric.threshold:
                inv_status = EvalStatus.FAILED
            else:
                inv_status = EvalStatus.PASSED

            per_invocation_results.append(
                PerInvocationResult(
                    actual_invocation=actual,
                    expected_invocation=expected,
                    score=weighted_avg,
                    eval_status=inv_status,
                    rubric_scores=rubric_scores,
                )
            )

        evaluated_scores = [
            r.score
            for r in per_invocation_results
            if r.score is not None and r.eval_status != EvalStatus.NOT_EVALUATED
        ]
        all_abstained = all(
            r.eval_status == EvalStatus.NOT_EVALUATED for r in per_invocation_results
        )
        any_failed = any(
            r.eval_status == EvalStatus.FAILED for r in per_invocation_results
        )

        if all_abstained:
            overall_status = EvalStatus.NOT_EVALUATED
            overall_score = None
        else:
            overall_score = (
                round(sum(evaluated_scores) / len(evaluated_scores), 4)
                if evaluated_scores
                else 0.0
            )
            active_threshold = self._resolve_rubric(actual_invocations[0]).threshold
            overall_status = (
                EvalStatus.FAILED
                if (any_failed or overall_score < active_threshold)
                else EvalStatus.PASSED
            )

        overall_rubric_scores = [
            RubricScore(
                rubric_id=r_id,
                score=round(sum(vals) / len(vals), 4),
                rationale=f"Mean calibrated probability across {len(vals)} invocation(s)",
            )
            for r_id, vals in rubric_score_buckets.items()
        ]

        return EvaluationResult(
            overall_score=overall_score,
            overall_eval_status=overall_status,
            per_invocation_results=per_invocation_results,
            overall_rubric_scores=overall_rubric_scores,
        )


async def evaluate_rubric_metric(
    eval_metric: EvalMetric,
    actual_invocations: list[Invocation],
    expected_invocations: Optional[list[Invocation]] = None,
    conversation_scenario: Optional[ConversationScenario] = None,
    *,
    backend: Optional[BaseJudgmentBackend] = None,
) -> EvaluationResult:
    """ADK custom_function_path entry point (`judgment_base_agent.evals.evaluate_rubric_metric`)."""
    evaluator = JudgmentRubricEvaluator(eval_metric=eval_metric, backend=backend)
    return await evaluator.evaluate_invocations(
        actual_invocations=actual_invocations,
        expected_invocations=expected_invocations,
        conversation_scenario=conversation_scenario,
    )


def register_judgment_eval_metrics(
    registry: Optional[MetricEvaluatorRegistry] = None,
    metric_name: str = DEFAULT_METRIC_NAME,
) -> MetricEvaluatorRegistry:
    """Registers JudgmentRubricEvaluator in ADK's MetricEvaluatorRegistry."""
    target_registry = (
        registry if registry is not None else DEFAULT_METRIC_EVALUATOR_REGISTRY
    )
    metric_info = MetricInfo(
        metric_name=metric_name,
        description=(
            "Single-pass calibrated epistemic rubric judge with weighted criteria, "
            "hard-fail safety vetoes, and clarity-based abstention."
        ),
        metric_value_info=MetricValueInfo(
            interval=Interval(min_value=0.0, max_value=1.0)
        ),
    )
    target_registry.register_evaluator(
        metric_info=metric_info,
        evaluator=JudgmentRubricEvaluator,
    )
    return target_registry


def format_rubric_scorecard(
    result: EvaluationResult,
    rubric: JudgmentRubric,
) -> str:
    """Formats an ADK EvaluationResult as a Markdown scorecard table."""
    if not result.per_invocation_results:
        return "No invocations evaluated."
    per_inv = result.per_invocation_results[0]
    items_by_id = {item.rubric_id: item for item in rubric.items}
    rows: list[str] = [
        f"### ADK Rubric Evaluation Verdict: **{per_inv.eval_status.name}** "
        f"(Weighted Score: **{(per_inv.score or 0.0):.2f}** / Threshold: **{rubric.threshold:.2f}**)",
        "",
        "| Rubric Criterion | Calibrated Score | Weight | Min Required | Hard Veto? | Status |",
        "| :--- | :---: | :---: | :---: | :---: | :--- |",
    ]
    for r_score in per_inv.rubric_scores or []:
        item = items_by_id.get(r_score.rubric_id)
        weight = item.weight if item else 1.0
        min_req = item.min_score if item else rubric.threshold
        is_veto = item.veto if item else False
        val = r_score.score if r_score.score is not None else 0.0
        if per_inv.eval_status == EvalStatus.NOT_EVALUATED:
            badge = "⚠️ ABSTAINED (Low Clarity)"
        elif is_veto and val < min_req:
            badge = "🛑 VETO FAILED"
        elif val < min_req:
            badge = "❌ BELOW MIN"
        else:
            badge = "✅ PASS"
        rows.append(
            f"| `{r_score.rubric_id}` — {item.description if item else ''} "
            f"| **{val:.2f}** | `{weight:.1f}x` | `{min_req:.2f}` | `{'YES' if is_veto else 'No'}` | {badge} |"
        )
    return "\n".join(rows)
