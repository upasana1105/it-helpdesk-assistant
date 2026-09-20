"""Model-agnostic question and answer primitives for System One / Judgment workflows."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from judgment_base_agent.errors import JudgmentConfigError

ConfidenceTier = Literal["high", "medium", "low"]


def classify_confidence_tier(
    confidence: float, floor: float = 0.50
) -> ConfidenceTier:
    """Classify a calibrated confidence value into high, medium, or low tiers."""
    if confidence >= 0.80:
        return "high"
    if confidence >= floor:
        return "medium"
    return "low"


@dataclass(frozen=True)
class Choice:
    """Unordered categorical judgment over a closed set of options."""

    instructions: str
    criteria: Mapping[str, str | None] | Sequence[str]

    def __post_init__(self) -> None:
        if not (self.instructions or "").strip():
            raise JudgmentConfigError("Choice.instructions must be a non-empty string.")
        if not self.criteria:
            raise JudgmentConfigError("Choice.criteria must contain at least one option.")

    def normalized_criteria(self) -> dict[str, str | None]:
        """Return criteria normalized as a dict mapping option key to description or None."""
        if isinstance(self.criteria, Mapping):
            return {str(k): (str(v) if v is not None else None) for k, v in self.criteria.items()}
        return {str(item): None for item in self.criteria}


@dataclass(frozen=True)
class Score:
    """Ordered spectrum judgment over 2 or more defined levels."""

    instructions: str
    criteria: Sequence[str]

    def __post_init__(self) -> None:
        if not (self.instructions or "").strip():
            raise JudgmentConfigError("Score.instructions must be a non-empty string.")
        if not self.criteria or len(self.criteria) < 2:
            raise JudgmentConfigError("Score.criteria must contain at least 2 ordered levels.")

    def normalized_criteria(self) -> list[str]:
        """Return criteria normalized as a list of level strings."""
        return [str(level) for level in self.criteria]


@dataclass(frozen=True)
class Noul:
    """Calibrated binary probability judgment in [0.0, 1.0]."""

    instructions: str
    criteria: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if not (self.instructions or "").strip():
            raise JudgmentConfigError("Noul.instructions must be a non-empty string.")
        if self.criteria is not None:
            raw = dict(self.criteria)
            if not set(raw.keys()).issubset({"true", "false"}):
                object.__setattr__(self, "criteria", {"true": raw})


class ChoiceJudgment(BaseModel):
    """Typed answer for a Choice question."""

    model_config = ConfigDict(frozen=True)

    choice: str
    probabilities: dict[str, float] = Field(default_factory=dict)
    confidence: float = 1.0
    confidence_tier: ConfidenceTier = "high"

    @classmethod
    def from_raw(
        cls,
        choice: str,
        probabilities: Mapping[str, float] | None = None,
        confidence: float = 1.0,
        confidence_floor: float = 0.50,
    ) -> ChoiceJudgment:
        probs = {str(k): float(v) for k, v in (probabilities or {}).items()}
        conf = float(confidence)
        return cls(
            choice=str(choice),
            probabilities=probs,
            confidence=conf,
            confidence_tier=classify_confidence_tier(conf, floor=confidence_floor),
        )


class ScoreJudgment(BaseModel):
    """Typed answer for a Score question."""

    model_config = ConfigDict(frozen=True)

    score: float
    level: str = ""
    legend: dict[str, str] = Field(default_factory=dict)
    probabilities: dict[str, float] = Field(default_factory=dict)
    confidence: float = 1.0
    confidence_tier: ConfidenceTier = "high"

    @property
    def normalized_score(self) -> float:
        """Return score normalized to [0.0, 1.0] based on legend length."""
        max_idx = max(1, len(self.legend) - 1) if self.legend else 1
        return min(1.0, max(0.0, self.score / max_idx))

    @classmethod
    def from_raw(
        cls,
        score: float,
        legend: Mapping[str, str] | None = None,
        probabilities: Mapping[str, float] | None = None,
        confidence: float = 1.0,
        confidence_floor: float = 0.50,
        level: str = "",
    ) -> ScoreJudgment:
        conf = float(confidence)
        legend_dict = {str(k): str(v) for k, v in (legend or {}).items()}
        resolved_level = (
            str(level)
            if level
            else legend_dict.get(str(round(float(score))), "")
        )
        return cls(
            score=float(score),
            level=resolved_level,
            legend=legend_dict,
            probabilities={str(k): float(v) for k, v in (probabilities or {}).items()},
            confidence=conf,
            confidence_tier=classify_confidence_tier(conf, floor=confidence_floor),
        )


class NoulJudgment(BaseModel):
    """Typed answer for a Noul question."""

    model_config = ConfigDict(frozen=True)

    noul: float

    @property
    def probability(self) -> float:
        """Alias for noul probability in [0.0, 1.0]."""
        return self.noul

    @property
    def confidence_tier(self) -> ConfidenceTier:
        """Return high/borderline/low confidence tier based on distance from 0.50."""
        margin = abs(self.noul - 0.5) * 2.0
        return classify_confidence_tier(0.5 + margin / 2.0, floor=0.60)

    def passed(self, threshold: float = 0.50) -> bool:
        """Return True if noul probability meets or exceeds threshold."""
        return self.noul >= threshold


class JudgmentUsage(BaseModel):
    """Token usage telemetry for a judgment evaluation call."""

    model_config = ConfigDict(frozen=True)

    input_tokens: int = 0
    output_tokens: int = 0


class JudgmentResult(BaseModel):
    """Immutable container of all Choice, Score, and Noul judgments from an evaluation."""

    model_config = ConfigDict(frozen=True)

    choices: dict[str, ChoiceJudgment] = Field(default_factory=dict)
    scores: dict[str, ScoreJudgment] = Field(default_factory=dict)
    nouls: dict[str, NoulJudgment] = Field(default_factory=dict)
    model: str = "judgment-latest"
    usage: JudgmentUsage | None = None

    def get(self, key: str) -> ChoiceJudgment | ScoreJudgment | NoulJudgment:
        """Retrieve any judgment answer by question key."""
        if key in self.choices:
            return self.choices[key]
        if key in self.scores:
            return self.scores[key]
        if key in self.nouls:
            return self.nouls[key]
        raise KeyError(f"Question key '{key}' not found in JudgmentResult.")

    def __getitem__(self, key: str) -> ChoiceJudgment | ScoreJudgment | NoulJudgment:
        return self.get(key)

    def choice(self, key: str) -> str:
        """Return the selected choice string for a Choice question."""
        if key not in self.choices:
            raise KeyError(f"Choice key '{key}' not found in JudgmentResult.")
        return self.choices[key].choice

    def score(self, key: str) -> float:
        """Return the numeric score for a Score question."""
        if key not in self.scores:
            raise KeyError(f"Score key '{key}' not found in JudgmentResult.")
        return self.scores[key].score

    def noul(self, key: str) -> float:
        """Return the probability in [0, 1] for a Noul question."""
        if key not in self.nouls:
            raise KeyError(f"Noul key '{key}' not found in JudgmentResult.")
        return self.nouls[key].noul

    def confidence(self, key: str) -> float:
        """Return the calibrated confidence for a Choice or Score question."""
        if key in self.choices:
            return self.choices[key].confidence
        if key in self.scores:
            return self.scores[key].confidence
        if key in self.nouls:
            # Distance from 0.5 normalized to [0.0, 1.0] for binary Noul
            return abs(self.nouls[key].noul - 0.5) * 2.0
        raise KeyError(f"Question key '{key}' not found in JudgmentResult.")
