"""
Evaluator: runs one analytical lens against a business idea.

The lens supplies the perspective (role, focus, questions); the shared
ANALYSIS_STANDARDS supply the tone; the EvaluatorResult schema defines the output.
"""

import logging
import time

from config import MODEL, MAX_TOKENS
from core.claude_client import get_client
from core.structured_call import billed_tokens, length_problems, request_structured
from evaluators.lenses import ANALYSIS_STANDARDS, Lens
from evaluators.schemas import EvaluatorResult

logger = logging.getLogger(__name__)

# Length bounds also catch field bleed: when a field breaks off at a stray double
# quote, the rest of the text lands in the next field (seen: a full analysis in
# 'summary' and a 2 KB stub in 'analysis').
MIN_ANALYSIS_CHARS = 1500
MIN_SUMMARY_CHARS = 40
MAX_SUMMARY_CHARS = 800
MIN_REASON_CHARS = 30
MAX_REASON_CHARS = 600
PLACEHOLDER_VALUES = {"", "none", "n/a", "na", "null", "unknown", "-"}


def validate_result(result: EvaluatorResult) -> list[str]:
    """Return the problems that make a parsed result unusable; empty if it is fine."""
    problems = []
    if len(result.analysis.strip()) < MIN_ANALYSIS_CHARS:
        problems.append(f"analysis too short ({len(result.analysis.strip())} chars)")
    problems += length_problems("summary", result.summary, MIN_SUMMARY_CHARS, MAX_SUMMARY_CHARS)
    problems += length_problems(
        "confidence_reason", result.confidence_reason, MIN_REASON_CHARS, MAX_REASON_CHARS
    )
    if result.killer_risk.strip().lower() in PLACEHOLDER_VALUES:
        problems.append(f"killer_risk is a placeholder ({result.killer_risk.strip()!r})")
    if not result.key_assumptions:
        problems.append("no key_assumptions")
    if not result.next_steps:
        problems.append("no next_steps")
    return problems


class Evaluator:
    """Evaluates a business idea through a single lens."""

    def __init__(self, lens: Lens, business_idea: str):
        self.lens = lens
        self.business_idea = business_idea
        self.client = get_client()
        self.model = MODEL
        self.max_tokens = MAX_TOKENS

    def get_system_prompt(self) -> str:
        return (
            f"You are {self.lens.role}.\n\n"
            f"{ANALYSIS_STANDARDS}\n"
            f"Your lens: {self.lens.focus}"
        )

    def get_evaluation_prompt(self) -> str:
        questions = "\n".join(
            f"{number}. {question}"
            for number, question in enumerate(self.lens.questions, start=1)
        )
        return (
            "Evaluate the business idea below through your lens. "
            f"Address these questions in your analysis:\n\n{questions}"
        )

    def evaluate(self) -> dict:
        """
        Run the evaluation and return a result dict.

        Returns a dict with "status": "success" and the structured fields,
        or "status": "error" with an error message. Never raises.
        """
        started = time.monotonic()
        try:
            response = request_structured(
                self.client,
                label=self.lens.name,
                model=self.model,
                max_tokens=self.max_tokens,
                system=self.get_system_prompt(),
                user=f"{self.get_evaluation_prompt()}\n\nBusiness Idea:\n{self.business_idea}",
                output_format=EvaluatorResult,
                validate=validate_result,
            )
            return {
                "evaluator": self.lens.key,
                "evaluator_display": self.lens.name,
                "status": "success",
                **response.result.model_dump(mode="json"),
                "tokens_used": response.input_tokens + response.output_tokens,
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "duration_s": time.monotonic() - started,
            }
        except Exception as e:
            logger.debug(f"{self.lens.name}: evaluation failed", exc_info=True)
            return {
                "evaluator": self.lens.key,
                "evaluator_display": self.lens.name,
                "status": "error",
                "error": f"{type(e).__name__}: {e}",
                "duration_s": time.monotonic() - started,
                **billed_tokens(e),
            }

    @property
    def full_prompt(self) -> str:
        """Full prompt, for debugging."""
        return (
            f"=== SYSTEM PROMPT ===\n{self.get_system_prompt()}\n\n"
            f"=== EVALUATION PROMPT ===\n{self.get_evaluation_prompt()}\n\n"
            f"=== BUSINESS IDEA ===\n{self.business_idea}\n"
        )
