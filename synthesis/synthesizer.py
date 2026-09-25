"""
Synthesizer: turns the lens results into one overall verdict on the idea.

The lenses answer separate questions, so their verdicts are evidence, not votes.
The synthesis reads everything they returned (structured fields and full
analysis) and decides on the whole business, following SYNTHESIS_PRINCIPLES.
"""

import logging
import time
from typing import Optional

from config import MAX_TOKENS, MODEL
from core.claude_client import get_client
from core.structured_call import billed_tokens, length_problems, request_structured
from evaluators.schemas import Verdict, confidence_label, verdict_label
from synthesis.schemas import SynthesisResult

logger = logging.getLogger(__name__)

SYNTHESIS_LABEL = "Synthesis"

SYNTHESIS_PRINCIPLES = """\
You are the lead analyst who turns several independent evaluations of a business idea
into one final decision for the founder.

Each lens answered only its own question (revenue, buildability, whether the idea is
worth pursuing at all, ...), so the lens verdicts are evidence, not votes. Your verdict
is about the whole business as described.

How to decide:
- Weakest link, not majority. A business needs every critical part to work, so one
  established blocker in the core (illegal, blocked by a platform, economically
  impossible) outweighs positive verdicts from other lenses.
- Substance over labels. Read each lens's killer risk, confidence reason and analysis.
  If a lens's verdict contradicts its own reasoning (for example "risky" while calling
  the core impossible to build as described), follow the reasoning and record the
  contradiction as a conflict.
- Corroboration. A problem raised independently by several lenses, including in their
  out-of-lens red flags, is strong evidence. A claim made by one lens without support
  is an assumption to test, not an established fact.
- Flawed versus unvalidated. Not viable only for an established blocker in the core
  model; needs validation when the deciding questions are open and cheap to test;
  viable if when specific testable conditions decide the outcome.
- A blocker makes the idea not viable only if it lies in the business itself: what
  is sold, to whom, how it makes money, whether it is legal. If a different
  implementation choice (technology, channel, supplier) would remove it, it is a
  condition or a risk, not a fundamental flaw.
- Judge the idea as described. A promising pivot belongs in the next steps, not in
  the verdict.
- Lower the confidence when lenses disagree on facts or numbers, when the verdict rests
  on unconfirmed claims, when some lenses failed and their perspective is missing, or
  when an input check note says the idea description is thin.

Standards:
- Be brutally honest. No marketing language, no encouragement for its own sake.
- Every number carries its source: which lens, or the founder's own claim. Surface
  numbers that conflict between lenses or with the founder's claims.
- Attribute findings to lenses by name.
- Write in English. Describe verdicts in plain words; do not quote verdict codes
  such as NOT_VIABLE in the text.
- When quoting anything, including the idea description, use single quotes ('like
  this'), not double quotes: your answer is JSON, and an unescaped double quote
  ends the field it is in.
"""

# Length bounds also catch field bleed: when a field breaks off at a stray double
# quote, the rest of the text lands in the next field.
MIN_SUMMARY_CHARS = 60
MAX_SUMMARY_CHARS = 1500
MIN_REASON_CHARS = 30
MAX_REASON_CHARS = 600
MIN_REASONING_CHARS = 300


def validate_synthesis(result: SynthesisResult) -> list[str]:
    """Return the problems that make a parsed synthesis unusable; empty if it is fine."""
    problems = []
    if len(result.reasoning.strip()) < MIN_REASONING_CHARS:
        problems.append("reasoning too short")
    problems += length_problems("summary", result.summary, MIN_SUMMARY_CHARS, MAX_SUMMARY_CHARS)
    problems += length_problems(
        "confidence_reason", result.confidence_reason, MIN_REASON_CHARS, MAX_REASON_CHARS
    )
    if not result.deciding_factors:
        problems.append("no deciding_factors")
    if not result.killer_risks:
        problems.append("no killer_risks")
    if not result.next_steps:
        problems.append("no next_steps")
    return problems


def consistency_warnings(synthesis: dict, lens_results: list[dict]) -> list[str]:
    """
    Cheap checks of the overall verdict against the lens results. They only warn:
    the synthesis may be right to disagree with a lens label, so nothing is overridden.
    """
    warnings = []
    overall = synthesis["verdict"]
    positive = {Verdict.VIABLE.value, Verdict.VIABLE_IF.value}
    not_viable = [
        r["evaluator_display"]
        for r in lens_results
        if r["status"] == "success" and r["verdict"] == Verdict.NOT_VIABLE.value
    ]
    if overall in positive and not_viable:
        warnings.append(
            f"overall verdict is {verdict_label(overall)} although {', '.join(not_viable)} "
            "found the idea not viable"
        )
    if overall == Verdict.NOT_VIABLE.value and not synthesis["next_steps"][0].lower().startswith(
        "do not pursue"
    ):
        warnings.append("overall verdict is Not viable but the first next step is not 'Do not pursue'")
    return warnings


class Synthesizer:
    """Combines the results of any number of lenses into one overall verdict."""

    def __init__(
        self, business_idea: str, lens_results: list[dict], input_note: Optional[str] = None
    ):
        self.business_idea = business_idea
        self.lens_results = lens_results
        self.input_note = input_note
        self.client = get_client()
        self.model = MODEL
        self.max_tokens = MAX_TOKENS

    def get_user_prompt(self) -> str:
        succeeded = sum(r["status"] == "success" for r in self.lens_results)
        lenses = "\n\n".join(self._format_lens(r) for r in self.lens_results)
        note = f"<input_check>\n{self.input_note}\n</input_check>\n\n" if self.input_note else ""
        return (
            f"<business_idea>\n{self.business_idea}\n</business_idea>\n\n"
            f"{note}"
            f"Lens results ({succeeded} of {len(self.lens_results)} lenses succeeded):\n\n"
            f"{lenses}\n\n"
            "Decide the overall verdict on this business idea."
        )

    @staticmethod
    def _format_lens(result: dict) -> str:
        name = result["evaluator_display"]
        if result["status"] != "success":
            return f'<lens name="{name}">\nFAILED: {result["error"]}\n</lens>'

        red_flags = "\n".join(f"- {flag}" for flag in result["out_of_lens_red_flags"]) or "- none"
        assumptions = "\n".join(
            f"- {a['statement']} | test: {a['how_to_test']} | fails if: {a['failure_signal']}"
            for a in result["key_assumptions"]
        )
        steps = "\n".join(f"{i}. {step}" for i, step in enumerate(result["next_steps"], start=1))
        return (
            f'<lens name="{name}">\n'
            f"Lens verdict: {verdict_label(result['verdict'])} "
            f"(confidence {confidence_label(result['confidence'])}: {result['confidence_reason']})\n"
            f"Summary: {result['summary']}\n"
            f"Killer risk within this lens: {result['killer_risk']}\n"
            f"Red flags outside this lens:\n{red_flags}\n"
            f"Key assumptions:\n{assumptions}\n"
            f"Next steps:\n{steps}\n"
            f"Full analysis:\n{result['analysis']}\n"
            "</lens>"
        )

    def synthesize(self) -> dict:
        """
        Run the synthesis and return a result dict with "status": "success" and the
        SynthesisResult fields, or "status": "error" with an error message. Never raises.
        """
        started = time.monotonic()
        try:
            response = request_structured(
                self.client,
                label=SYNTHESIS_LABEL,
                model=self.model,
                max_tokens=self.max_tokens,
                system=SYNTHESIS_PRINCIPLES,
                user=self.get_user_prompt(),
                output_format=SynthesisResult,
                validate=validate_synthesis,
            )
            result = {
                "evaluator_display": SYNTHESIS_LABEL,
                "status": "success",
                **response.result.model_dump(mode="json"),
                "tokens_used": response.input_tokens + response.output_tokens,
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "duration_s": time.monotonic() - started,
            }
            for warning in consistency_warnings(result, self.lens_results):
                logger.warning(f"{SYNTHESIS_LABEL}: {warning}")
            return result
        except Exception as e:
            logger.debug(f"{SYNTHESIS_LABEL}: failed", exc_info=True)
            return {
                "evaluator_display": SYNTHESIS_LABEL,
                "status": "error",
                "error": f"{type(e).__name__}: {e}",
                "duration_s": time.monotonic() - started,
                **billed_tokens(e),
            }
