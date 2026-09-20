"""Custom exception hierarchy for judgment_base_agent."""

from __future__ import annotations


class JudgmentError(Exception):
    """Base exception for all JudgmentAgent errors."""


class JudgmentConfigError(JudgmentError):
    """Raised when a question, schema, or agent configuration is invalid."""


class JudgmentEvaluationError(JudgmentError):
    """Raised when a judgment backend fails to evaluate a request."""
