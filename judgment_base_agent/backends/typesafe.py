"""TypeSafe AI System One Judgment backend implementation."""

from __future__ import annotations

from collections.abc import Mapping
import os
from typing import Any

import typesafe_sdk

from judgment_base_agent.errors import JudgmentConfigError, JudgmentEvaluationError
from judgment_base_agent.primitives import (
    Choice,
    ChoiceJudgment,
    JudgmentResult,
    JudgmentUsage,
    Noul,
    NoulJudgment,
    Score,
    ScoreJudgment,
)


def _normalize_noul_criteria(
    criteria: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Normalize Noul criteria into typesafe_sdk NoulCriteria ({'true': ..., 'false': ...})."""
    if not criteria:
        return None
    raw = dict(criteria)
    if set(raw.keys()).issubset({"true", "false"}):
        return raw
    return {"true": raw}


def _to_typesafe_question(q: Any) -> Any:
    """Convert model-agnostic Choice/Score/Noul or dict into typesafe_sdk question objects."""
    if isinstance(q, (typesafe_sdk.Choice, typesafe_sdk.Score, typesafe_sdk.Noul)):
        return q
    if isinstance(q, Choice):
        return typesafe_sdk.Choice(
            instructions=q.instructions,
            criteria=q.normalized_criteria(),
        )
    if isinstance(q, Score):
        return typesafe_sdk.Score(
            instructions=q.instructions,
            criteria=q.normalized_criteria(),
        )
    if isinstance(q, Noul):
        return typesafe_sdk.Noul(
            instructions=q.instructions,
            criteria=_normalize_noul_criteria(q.criteria),
        )
    if isinstance(q, Mapping):
        q_type = str(q.get("type", "")).lower()
        if q_type == "choice":
            return typesafe_sdk.Choice(
                instructions=str(q["instructions"]),
                criteria=q["criteria"],
            )
        if q_type == "score":
            return typesafe_sdk.Score(
                instructions=str(q["instructions"]),
                criteria=list(q["criteria"]),
            )
        if q_type == "noul":
            return typesafe_sdk.Noul(
                instructions=str(q["instructions"]),
                criteria=_normalize_noul_criteria(q.get("criteria")),
            )
    raise JudgmentConfigError(f"Unsupported question primitive type: {type(q)!r}")


def _question_kind(q: Any) -> str:
    if isinstance(q, (Choice, typesafe_sdk.Choice)):
        return "choice"
    if isinstance(q, (Score, typesafe_sdk.Score)):
        return "score"
    if isinstance(q, (Noul, typesafe_sdk.Noul)):
        return "noul"
    if isinstance(q, Mapping):
        return str(q.get("type", "")).lower()
    return "unknown"


class TypeSafeBackend:
    """Judgment backend powered by TypeSafe's AsyncTypeSafeClient (default model: 'judgment-latest')."""

    def __init__(
        self,
        api_key: str | None = None,
        default_model: str = "judgment-latest",
        confidence_floor: float = 0.50,
        client: Any | None = None,
    ) -> None:
        self.api_key = api_key
        self.default_model = default_model
        self.confidence_floor = confidence_floor
        self.client = client
        self._shared_client: Any | None = None

    async def aclose(self) -> None:
        """Close the cached AsyncTypeSafeClient if one was created."""
        if self._shared_client is not None:
            close_fn = getattr(self._shared_client, "close", None) or getattr(
                self._shared_client, "__aexit__", None
            )
            if close_fn is not None:
                try:
                    await close_fn()
                except TypeError:
                    await self._shared_client.__aexit__(None, None, None)
            self._shared_client = None

    async def close(self) -> None:
        """Alias for aclose()."""
        await self.aclose()

    async def evaluate(
        self,
        state: Any,
        questions: Mapping[str, Any],
        model: str | None = None,
    ) -> JudgmentResult:
        """Send state and batched questions to TypeSafe system_one and normalize the result."""
        if not questions:
            return JudgmentResult(model=model or self.default_model)

        sdk_questions = {
            str(k): _to_typesafe_question(v) for k, v in questions.items()
        }
        target_model = model or self.default_model

        try:
            if self.client is not None:
                try:
                    response = await self.client.system_one(
                        state=state, questions=sdk_questions, model=target_model
                    )
                except TypeError:
                    response = await self.client.system_one(
                        state=state, questions=sdk_questions
                    )
            else:
                resolved_key = self.api_key or os.environ.get("TYPESAFE_API_KEY")
                if not resolved_key:
                    raise JudgmentConfigError(
                        "TYPESAFE_API_KEY environment variable or explicit api_key is required "
                        "to evaluate questions with TypeSafeBackend."
                    )
                sdk_model = (
                    typesafe_sdk.constants.DEFAULT_MODEL
                    if target_model in ("judgment-latest", "system-one")
                    else target_model
                )
                if self._shared_client is None:
                    client_instance = typesafe_sdk.AsyncTypeSafeClient(
                        api_key=resolved_key
                    )
                    self._shared_client = await client_instance.__aenter__()
                response = await self._shared_client.system_one(
                    state=state,
                    questions=sdk_questions,
                    model=sdk_model,
                )
        except JudgmentConfigError:
            raise
        except Exception as exc:
            raise JudgmentEvaluationError(
                f"TypeSafe evaluation failed for model '{target_model}': {exc}"
            ) from exc

        answers_map = getattr(response, "answers", None) or {}
        choices_map = getattr(response, "choices", None) or {}
        scores_map = getattr(response, "scores", None) or {}
        nouls_map = getattr(response, "nouls", None) or {}

        parsed_choices: dict[str, ChoiceJudgment] = {}
        parsed_scores: dict[str, ScoreJudgment] = {}
        parsed_nouls: dict[str, NoulJudgment] = {}

        for key, orig_q in questions.items():
            kind = _question_kind(orig_q)
            if kind == "choice":
                raw_c = answers_map.get(key) or choices_map[key]
                parsed_choices[key] = ChoiceJudgment.from_raw(
                    choice=str(raw_c.choice),
                    probabilities=getattr(raw_c, "probabilities", {}) or {},
                    confidence=float(getattr(raw_c, "confidence", 1.0)),
                    confidence_floor=self.confidence_floor,
                )
            elif kind == "score":
                raw_s = answers_map.get(key) or scores_map[key]
                parsed_scores[key] = ScoreJudgment.from_raw(
                    score=float(raw_s.score),
                    legend=getattr(raw_s, "legend", {}) or {},
                    probabilities=getattr(raw_s, "probabilities", {}) or {},
                    confidence=float(getattr(raw_s, "confidence", 1.0)),
                    confidence_floor=self.confidence_floor,
                )
            elif kind == "noul":
                raw_n = answers_map.get(key) or nouls_map[key]
                parsed_nouls[key] = NoulJudgment(noul=float(raw_n.noul))

        raw_usage = getattr(response, "usage", None)
        usage = (
            JudgmentUsage(
                input_tokens=int(getattr(raw_usage, "input_tokens", 0)),
                output_tokens=int(getattr(raw_usage, "output_tokens", 0)),
            )
            if raw_usage is not None
            else None
        )

        return JudgmentResult(
            choices=parsed_choices,
            scores=parsed_scores,
            nouls=parsed_nouls,
            model=str(getattr(response, "model", target_model)),
            usage=usage,
        )
