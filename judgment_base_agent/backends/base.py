"""Protocol for model-agnostic Judgment evaluation backends."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable

from judgment_base_agent.primitives import JudgmentResult


@runtime_checkable
class BaseJudgmentBackend(Protocol):
    """Protocol implemented by System One / calibrated judgment backends."""

    async def evaluate(
        self,
        state: Any,
        questions: Mapping[str, Any],
        model: str | None = None,
    ) -> JudgmentResult:
        """Evaluate all questions in parallel against the given state and return a JudgmentResult."""
        ...
