"""Declarative Pydantic schema binding fields to Choice, Score, and Noul primitives."""

from __future__ import annotations

from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from judgment_base_agent.errors import JudgmentConfigError
from judgment_base_agent.primitives import JudgmentResult

_JUDGMENT_QUESTION_META = "judgment_question"
_JUDGMENT_KEY_META = "judgment_key"


def JudgmentField(
    question: Any,
    *,
    key: str | None = None,
    description: str | None = None,
) -> Any:
    """Bind a Pydantic schema field to a Choice, Score, or Noul question definition."""
    if question is None:
        raise JudgmentConfigError("JudgmentField requires a non-None question object.")
    return Field(
        default=...,
        description=description,
        json_schema_extra={
            _JUDGMENT_QUESTION_META: question,
            _JUDGMENT_KEY_META: key,
        },
    )


class JudgmentSchema(BaseModel):
    """Base class for declarative, strongly-typed Judgment schemas."""

    model_config = ConfigDict(frozen=True)
    _raw_result: JudgmentResult | None = PrivateAttr(default=None)

    @property
    def raw_result(self) -> JudgmentResult | None:
        """Return the underlying JudgmentResult (with usage and model metadata) if available."""
        return self._raw_result

    @classmethod
    def build_questions(cls) -> dict[str, Any]:
        """Extract the mapping of question keys to question primitives declared on this schema."""
        questions: dict[str, Any] = {}
        for field_name, field_info in cls.model_fields.items():
            extra = field_info.json_schema_extra
            if isinstance(extra, dict) and _JUDGMENT_QUESTION_META in extra:
                q_key = extra.get(_JUDGMENT_KEY_META) or field_name
                questions[str(q_key)] = extra[_JUDGMENT_QUESTION_META]
        if not questions:
            raise JudgmentConfigError(
                f"JudgmentSchema '{cls.__name__}' defines no fields using JudgmentField(...)."
            )
        return questions

    @classmethod
    def from_result(cls, result: JudgmentResult) -> Self:
        """Instantiate and validate this schema from a JudgmentResult."""
        payload: dict[str, Any] = {}
        for field_name, field_info in cls.model_fields.items():
            extra = field_info.json_schema_extra
            if isinstance(extra, dict) and _JUDGMENT_QUESTION_META in extra:
                q_key = str(extra.get(_JUDGMENT_KEY_META) or field_name)
                payload[field_name] = result.get(q_key)
        instance = cls.model_validate(payload)
        object.__setattr__(instance, "_raw_result", result)
        return instance
