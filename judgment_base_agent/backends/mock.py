"""Deterministic MockJudgmentBackend for offline unit and integration tests."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from judgment_base_agent.backends.typesafe import _question_kind
from judgment_base_agent.primitives import (
    ChoiceJudgment,
    JudgmentResult,
    JudgmentUsage,
    NoulJudgment,
    ScoreJudgment,
)


class MockJudgmentBackend:
    """Offline mock backend supporting static answer dicts or dynamic responder callables."""

    def __init__(
        self,
        responses: (
            Mapping[str, Any]
            | Callable[[Any, Mapping[str, Any], str], Mapping[str, Any]]
        ),
        default_model: str = "mock-judgment",
        confidence_floor: float = 0.50,
    ) -> None:
        self.responses = responses
        self.default_model = default_model
        self.confidence_floor = confidence_floor
        self.calls: list[dict[str, Any]] = []

    async def evaluate(
        self,
        state: Any,
        questions: Mapping[str, Any],
        model: str | None = None,
    ) -> JudgmentResult:
        target_model = model or self.default_model
        self.calls.append(
            {"state": state, "questions": dict(questions), "model": target_model}
        )

        raw_map = (
            self.responses(state, questions, target_model)
            if callable(self.responses)
            else self.responses
        )

        parsed_choices: dict[str, ChoiceJudgment] = {}
        parsed_scores: dict[str, ScoreJudgment] = {}
        parsed_nouls: dict[str, NoulJudgment] = {}

        for key, q in questions.items():
            kind = _question_kind(q)
            val = raw_map.get(key)
            if kind == "choice":
                if isinstance(val, ChoiceJudgment):
                    parsed_choices[key] = val
                elif isinstance(val, Mapping):
                    parsed_choices[key] = ChoiceJudgment.from_raw(
                        choice=str(val.get("choice", "")),
                        probabilities=val.get("probabilities") or {},
                        confidence=float(val.get("confidence", 0.90)),
                        confidence_floor=self.confidence_floor,
                    )
                else:
                    choice_str = str(val) if val is not None else ""
                    parsed_choices[key] = ChoiceJudgment.from_raw(
                        choice=choice_str,
                        probabilities={choice_str: 0.90} if choice_str else {},
                        confidence=0.90,
                        confidence_floor=self.confidence_floor,
                    )
            elif kind == "score":
                if isinstance(val, ScoreJudgment):
                    parsed_scores[key] = val
                elif isinstance(val, Mapping):
                    parsed_scores[key] = ScoreJudgment.from_raw(
                        score=float(val.get("score", 0.0)),
                        legend=val.get("legend") or {},
                        probabilities=val.get("probabilities") or {},
                        confidence=float(val.get("confidence", 0.90)),
                        confidence_floor=self.confidence_floor,
                    )
                else:
                    parsed_scores[key] = ScoreJudgment.from_raw(
                        score=float(val if val is not None else 0.0),
                        confidence=0.90,
                        confidence_floor=self.confidence_floor,
                    )
            elif kind == "noul":
                if isinstance(val, NoulJudgment):
                    parsed_nouls[key] = val
                elif isinstance(val, Mapping):
                    parsed_nouls[key] = NoulJudgment(noul=float(val.get("noul", 0.0)))
                else:
                    parsed_nouls[key] = NoulJudgment(
                        noul=float(val if val is not None else 0.0)
                    )

        return JudgmentResult(
            choices=parsed_choices,
            scores=parsed_scores,
            nouls=parsed_nouls,
            model=target_model,
            usage=JudgmentUsage(input_tokens=10, output_tokens=len(questions)),
        )
