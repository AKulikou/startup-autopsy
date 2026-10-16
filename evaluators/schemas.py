"""Structured output schemas for evaluator responses."""

import re
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


# Human-readable form of each verdict for reports: (short label, meaning).
# The meanings also define the verdicts for the model in EvaluatorResult.
VERDICT_TEXT: dict[Verdict, tuple[str, str]] = {
    Verdict.VIABLE: ("Viable", "evidence supports building now"),
    Verdict.VIABLE_IF: (
        "Viable if conditions hold",
        "can work, but only if specific testable conditions hold",
    ),
    Verdict.NEEDS_VALIDATION: (
        "Needs validation",
        "too little evidence to judge; research must come first",
    ),
    Verdict.RISKY: (
        "Risky",
        "no fundamental flaw, but serious risks need mitigation before investing",
    ),
    Verdict.NOT_VIABLE: (
        "Not viable",
        "a fundamental flaw that no amount of research or iteration fixes",
    ),
}


VERDICT_RULES = (
    "Scope: the verdict answers your lens's question only. The overall verdict on the "
    "business is made later by combining all lenses, so problems outside your lens go into "
    "out_of_lens_red_flags and do not change your verdict. "
    "How to choose: "
    "Judge the idea as described, not an improved version of it; put pivots in next_steps. "
    "If something within your lens makes the idea unworkable as described (for example it is "
    "illegal, blocked by platform policy, or economically impossible), choose NOT_VIABLE. "
    "Choose RISKY only if every serious risk within your lens can be mitigated without changing "
    "the core model. "
    "Choose NEEDS_VALIDATION only if the deciding question within your lens is still open and "
    "can be answered by research (demand, willingness to pay); if you have already found a "
    "blocker you consider established, choose RISKY or NOT_VIABLE instead. "
    "The verdict must agree with the summary and the killer risk."
)

CONFIDENCE_RULES = (
    "How sure you are that the verdict is the right call, not how good or bad the idea is. "
    "HIGH: the verdict follows from established facts, regulations or arithmetic. "
    "MEDIUM: it depends on plausible but unverified assumptions. "
    "LOW: key information is missing and the verdict is largely a judgement call."
)


def verdict_label(verdict: str) -> str:
    """Short report label for a verdict code, e.g. 'VIABLE_IF' -> 'Viable if conditions hold'."""
    return VERDICT_TEXT[Verdict(verdict)][0]


def verdict_meaning(verdict: str) -> str:
    """One-line explanation of a verdict code."""
    return VERDICT_TEXT[Verdict(verdict)][1]


def confidence_label(confidence: str) -> str:
    """Report label for a confidence code, e.g. 'HIGH' -> 'High'."""
    return Confidence(confidence).value.capitalize()


# The prompts ask for plain words, yet the models still write codes into their text
# ("the appropriate verdict is NEEDS_VALIDATION rather than VIABLE_IF", "confidence
# at MEDIUM"): in all six real reports checked on 2026-10-16, mostly in the synthesis
# reasoning. Reports and the web page show them as words; report.json keeps the text
# as the model wrote it.
_VERDICT_IN_TEXT = re.compile(r"(['\"`]?)\b(NOT_VIABLE|VIABLE_IF|NEEDS_VALIDATION|RISKY|VIABLE)\b\1")
_CONFIDENCE_IN_TEXT = re.compile(r"\b(HIGH|MEDIUM|LOW)\b")
# A capitalised HIGH, MEDIUM or LOW counts as a confidence code only near the word.
_CONFIDENCE_CONTEXT = 40


def codes_as_words(text: str) -> str:
    """Verdict and confidence codes inside a model's text, written as words."""
    text = _VERDICT_IN_TEXT.sub(_verdict_words, text)
    return _CONFIDENCE_IN_TEXT.sub(_confidence_words, text)


def _verdict_words(match: re.Match) -> str:
    label = verdict_label(match.group(2))
    if not _starts_sentence(match.string, match.start()):
        label = label[0].lower() + label[1:]
    return f"'{label}'"


def _confidence_words(match: re.Match) -> str:
    around = match.string[max(0, match.start() - _CONFIDENCE_CONTEXT): match.end() + _CONFIDENCE_CONTEXT]
    if "confidence" not in around.lower():
        return match.group(0)
    return confidence_label(match.group(1)).lower()


def _starts_sentence(text: str, position: int) -> bool:
    before = text[:position].rstrip(" \t*_(")
    return not before or before[-1] in ".!?\n-#|"


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
        description="One or two sentences: your lens verdict and the main reason for it."
    )
    verdict: Verdict = Field(
        description=" ".join(
            f"{verdict.value}: {meaning}." for verdict, (_, meaning) in VERDICT_TEXT.items()
        ) + " " + VERDICT_RULES
    )
    confidence: Confidence = Field(
        description=CONFIDENCE_RULES
    )
    confidence_reason: str = Field(
        description="One sentence naming what the confidence depends on "
        "without repeating the level (e.g. 'Hinges on an unverified 5% trial-to-paid conversion rate')."
    )
    key_assumptions: list[Assumption] = Field(
        description="The 2-4 assumptions the verdict depends on most, most critical first."
    )
    killer_risk: str = Field(
        description="Within your lens, the single risk most likely to kill the project, stated "
        "specifically (not 'competition' but 'Calendly offers the same feature for free')."
    )
    next_steps: list[str] = Field(
        description="2-4 concrete actions in priority order, each doable within two weeks. "
        "If the verdict is NOT_VIABLE, the first step must be 'Do not pursue' with the reason."
    )
    out_of_lens_red_flags: list[str] = Field(
        description="Serious problems you noticed that belong to other perspectives (legal, "
        "market, technical, financial) and could kill the project, one specific sentence each. "
        "Do not analyse them and do not repeat your killer risk. Empty if you noticed none."
    )

