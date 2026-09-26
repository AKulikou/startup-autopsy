"""
Evaluator: runs one analytical lens against a business idea.

The lens supplies the perspective (role, focus, questions); the shared
ANALYSIS_STANDARDS supply the tone; the EvaluatorResult schema defines the output.
"""

import logging
import time

from config import MAX_TOKENS, MODEL, THINKING, WEB_SEARCH, WEB_SEARCH_LENSES, WEB_SEARCH_TOOL
from core.claude_client import get_client
from core.structured_call import billed_tokens, length_problems, request_structured
from evaluators.knowledge import load_knowledge
from evaluators.lenses import ANALYSIS_STANDARDS, Lens
from evaluators.schemas import EvaluatorResult

logger = logging.getLogger(__name__)

WEB_SEARCH_GUIDANCE = (
    "You can search the web. Check the facts your conclusions rest on - which "
    "competitors operate in the named market, what the law requires there, current "
    "prices - instead of relying on memory, and name the source in the analysis. "
    "A fact you could not confirm is marked as unverified."
)

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

    def __init__(self, lens: Lens, business_idea: str, input_note: str | None = None):
        self.lens = lens
        self.business_idea = business_idea
        self.input_note = input_note
        self.client = get_client()
        self.model = MODEL
        self.max_tokens = MAX_TOKENS
        self.web_search = WEB_SEARCH and lens.key in WEB_SEARCH_LENSES

    def get_system_prompt(self) -> str:
        prompt = (
            f"You are {self.lens.role}.\n\n"
            f"{ANALYSIS_STANDARDS}\n"
            f"Your lens: {self.lens.focus}"
        )
        if self.lens.knowledge:
            prompt += (
                "\n\nDomain knowledge for your lens:\n\n"
                f"<domain_knowledge>\n{load_knowledge(self.lens.knowledge)}\n</domain_knowledge>"
            )
        if self.web_search:
            prompt += f"\n\n{WEB_SEARCH_GUIDANCE}"
        return prompt

    def get_evaluation_prompt(self) -> str:
        questions = "\n".join(
            f"{number}. {question}"
            for number, question in enumerate(self.lens.questions, start=1)
        )
        return (
            "Evaluate the business idea below through your lens. "
            f"Address these questions in your analysis:\n\n{questions}"
        )

    def get_user_prompt(self) -> str:
        note = f"\n\n<input_check>\n{self.input_note}\n</input_check>" if self.input_note else ""
        return (
            f"{self.get_evaluation_prompt()}\n\n"
            f"<business_idea>\n{self.business_idea}\n</business_idea>{note}"
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
                user=self.get_user_prompt(),
                output_format=EvaluatorResult,
                validate=validate_result,
                thinking=THINKING == "adaptive",
                tools=[WEB_SEARCH_TOOL] if self.web_search else None,
            )
            return {
                "evaluator": self.lens.key,
                "evaluator_display": self.lens.name,
                "status": "success",
                **response.result.model_dump(mode="json"),
                "tokens_used": response.input_tokens + response.output_tokens,
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "web_searches": response.web_searches,
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
            f"=== USER PROMPT ===\n{self.get_user_prompt()}\n"
        )
