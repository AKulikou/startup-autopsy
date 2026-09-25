"""Structured output schema for the synthesis: the overall verdict on an idea."""

from pydantic import BaseModel, Field

from evaluators.schemas import CONFIDENCE_RULES, VERDICT_TEXT, Assumption, Confidence, Verdict


class Finding(BaseModel):
    finding: str = Field(description="The finding, stated specifically.")
    lenses: list[str] = Field(
        description="Names of the lenses that support it, exactly as given in the input. "
        "Empty if it comes only from your own reading of the idea."
    )


class Conflict(BaseModel):
    description: str = Field(
        description="What conflicts: numbers that differ between lenses or from the founder's "
        "own claims, contradictory advice, or a lens verdict that contradicts its own reasoning. "
        "Name the lenses and quote the numbers."
    )
    resolution: str = Field(
        description="Which side you believe and why, or what cheap test would settle it."
    )


class SynthesisResult(BaseModel):
    reasoning: str = Field(
        description="Work through the lens results before deciding: what each lens established, "
        "where lenses agree, conflict or contradict themselves, and which findings decide the "
        "outcome. Plain prose."
    )
    verdict: Verdict = Field(
        description="Overall verdict on the whole business as described. "
        + " ".join(f"{verdict.value}: {meaning}." for verdict, (_, meaning) in VERDICT_TEXT.items())
    )
    confidence: Confidence = Field(description=CONFIDENCE_RULES)
    confidence_reason: str = Field(
        description="One sentence naming what the confidence depends on, without repeating the level."
    )
    summary: str = Field(
        description="Two or three sentences for the founder: the overall verdict and the main reasons."
    )
    deciding_factors: list[Finding] = Field(
        description="The 2-5 findings the verdict rests on, most decisive first."
    )
    killer_risks: list[Finding] = Field(
        description="The distinct risks most likely to kill the project, merged across lens "
        "killer risks and red flags, most severe first. Each risk appears once."
    )
    conflicts: list[Conflict] = Field(
        description="Conflicts between lenses, with the founder's claims, or within one lens. "
        "Empty if there are none."
    )
    key_assumptions: list[Assumption] = Field(
        description="The 2-5 assumptions the whole idea depends on most, merged across lenses, "
        "most critical first."
    )
    next_steps: list[str] = Field(
        description="3-5 concrete actions in priority order, merged and deduplicated across lenses, "
        "each doable within two weeks. If the verdict is NOT_VIABLE, the first step must be "
        "'Do not pursue' with the reason."
    )
