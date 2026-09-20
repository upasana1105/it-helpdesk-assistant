"""Model-agnostic System One / Judgment primitives for Google ADK workflows."""

from judgment_base_agent.agent import JudgmentAgent, JudgmentDecision, judgment_node
from judgment_base_agent.backends import (
    BaseJudgmentBackend,
    MockJudgmentBackend,
    TypeSafeBackend,
)
from judgment_base_agent.errors import (
    JudgmentConfigError,
    JudgmentError,
    JudgmentEvaluationError,
)
from judgment_base_agent.evals import (
    JudgmentRubric,
    JudgmentRubricEvaluator,
    RubricItem,
    evaluate_rubric_metric,
    format_rubric_scorecard,
    register_judgment_eval_metrics,
)
from judgment_base_agent.presets import (
    JudgmentBatch,
    JudgmentBatchEntry,
    JudgmentGuard,
    JudgmentMap,
    JudgmentSwitch,
)
from judgment_base_agent.primitives import (
    Choice,
    ChoiceJudgment,
    ConfidenceTier,
    JudgmentResult,
    JudgmentUsage,
    Noul,
    NoulJudgment,
    Score,
    ScoreJudgment,
    classify_confidence_tier,
)
from judgment_base_agent.schema import JudgmentField, JudgmentSchema

# Model-agnostic aliases
SystemOneAgent = JudgmentAgent

JudgmentRouter = JudgmentSwitch
SystemOneRouter = JudgmentSwitch

JudgmentGate = JudgmentGuard
SystemOneGate = JudgmentGuard

__all__ = [
    "BaseJudgmentBackend",
    "Choice",
    "ChoiceJudgment",
    "ConfidenceTier",
    "JudgmentAgent",
    "JudgmentBatch",
    "JudgmentBatchEntry",
    "JudgmentConfigError",
    "JudgmentDecision",
    "JudgmentError",
    "JudgmentEvaluationError",
    "JudgmentField",
    "JudgmentGate",
    "JudgmentGuard",
    "JudgmentMap",
    "JudgmentResult",
    "JudgmentRouter",
    "JudgmentRubric",
    "JudgmentRubricEvaluator",
    "JudgmentSchema",
    "JudgmentSwitch",
    "JudgmentUsage",
    "MockJudgmentBackend",
    "Noul",
    "NoulJudgment",
    "RubricItem",
    "Score",
    "ScoreJudgment",
    "SystemOneAgent",
    "SystemOneGate",
    "SystemOneRouter",
    "TypeSafeBackend",
    "classify_confidence_tier",
    "evaluate_rubric_metric",
    "format_rubric_scorecard",
    "judgment_node",
    "register_judgment_eval_metrics",
]
