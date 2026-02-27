"""Pydantic schemas for the Hypothesis Advisor feature."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# -- Step 1: Questions -----------------------------------------------


class AdvisorQuestionsRequest(BaseModel):
    """No body needed -- hypothesis is read from the experiment."""
    pass


class AdvisorQuestion(BaseModel):
    id: str
    question: str
    why: str | None = None
    options: list[str] | None = None


class AdvisorQuestionsResponse(BaseModel):
    experiment_id: int
    hypothesis: str
    questions: list[AdvisorQuestion]


# -- Step 2: Suggest conditions --------------------------------------


class QuestionAnswer(BaseModel):
    question: str
    answer: str


class AdvisorSuggestRequest(BaseModel):
    answers: list[QuestionAnswer] = Field(
        ..., min_length=1, description="Answered clarifying questions"
    )


class SuggestedCondition(BaseModel):
    name: str
    prompt: str
    rationale: str | None = None
    upload_plan: list[int] | None = None
    ref_strategy: str | None = Field(
        default=None,
        description="Why these reference images and this order were chosen",
    )

    @classmethod
    def from_raw(cls, data: dict) -> "SuggestedCondition":
        """Create from raw Gemini output, handling various formats."""
        raw_plan = data.get("upload_plan")
        clean_plan = None

        if isinstance(raw_plan, list) and raw_plan:
            # Slot-aware legacy format: [{"slot": 1, "asset_id": 7}, ...]
            if isinstance(raw_plan[0], dict) and "asset_id" in raw_plan[0]:
                ids = []
                # Sort by slot/position if present, then extract IDs
                sorted_items = sorted(
                    raw_plan,
                    key=lambda x: x.get("slot", x.get("position", 0)),
                )
                for item in sorted_items:
                    try:
                        ids.append(int(item["asset_id"]))
                    except (ValueError, TypeError, KeyError):
                        pass
                clean_plan = ids if ids else None
            else:
                # Flat list of ints
                ids = []
                for v in raw_plan:
                    try:
                        ids.append(int(v))
                    except (ValueError, TypeError):
                        pass
                clean_plan = ids if ids else None

        return cls(
            name=data.get("name", "Unnamed"),
            prompt=data.get("prompt", ""),
            rationale=data.get("rationale"),
            upload_plan=clean_plan,
            ref_strategy=data.get("ref_strategy", data.get("slot_strategy")),
        )


class AdvisorSuggestResponse(BaseModel):
    experiment_id: int
    conditions: list[SuggestedCondition]
