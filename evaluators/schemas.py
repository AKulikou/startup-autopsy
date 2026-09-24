"""Structured output schemas for evaluator responses."""

from enum import Enum
from pydantic import BaseModel, Field


class Verdict(str, Enum):
    VIABLE = "VIABLE"
    VIABLE_IF = "VIABLE_IF"
    NEEDS_VALIDATION = "NEEDS_VALIDATION"
    RISKY = "RISKY"
    NOT_VIABLE = "NOT_VIABLE"


class Confidence(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class Assumption(BaseModel):
    statement: str = Field(
        description="What must be true for the idea to work, stated specifically "
        "(e.g. 'At least 5% of trial users convert to the $15/month plan')"
    )
    how_to_test: str = Field(
        description="The cheapest concrete way to check it within 1-2 weeks "
        "(survey, landing page, manual pilot), before building the product"
    )
    failure_signal: str = Field(
        description="The observable result that would prove the assumption wrong "
        "(e.g. 'fewer than 10 of 200 visitors join the waitlist')"
    )


class EvaluatorResult(BaseModel):
    analysis: str = Field(
        description="Full analysis from this evaluator's perspective, in Markdown. "
        "Show the reasoning and the math behind every estimate."
    )
    summary: str = Field(
        description="One or two sentences: the verdict and the main reason for it."
    )
    verdict: Verdict = Field(
        description=(
            "VIABLE: evidence supports building now. "
            "VIABLE_IF: can work, but only if specific testable conditions hold. "
            "NEEDS_VALIDATION: too little evidence to judge; research must come first. "
            "RISKY: no fundamental flaw, but serious risks need mitigation before investing. "
            "NOT_VIABLE: fundamental flaw that no amount of research or iteration fixes."
        )
    )
    confidence: Confidence = Field(
        description="How strongly the evidence supports the verdict."
    )
    confidence_reason: str = Field(
        description="One sentence naming what the confidence depends on "
        "without repeating the level (e.g. 'Hinges on an unverified 5% trial-to-paid conversion rate')."
    )
    key_assumptions: list[Assumption] = Field(
        description="The 2-4 assumptions the verdict depends on most, most critical first."
    )
    killer_risk: str = Field(
        description="The single risk most likely to kill the project, stated specifically "
        "(not 'competition' but 'Calendly offers the same feature for free')."
    )
    next_steps: list[str] = Field(
        description="2-4 concrete actions in priority order, each doable within two weeks. "
        "If the verdict is NOT_VIABLE, the first step must be 'Do not pursue' with the reason."
    )

