"""
Evaluator: runs one analytical lens against a business idea.

The lens supplies the perspective (role, focus, questions); the shared
ANALYSIS_STANDARDS supply the tone; the EvaluatorResult schema defines the output.
"""

import logging
import time

from anthropic import Anthropic

from config import ANTHROPIC_API_KEY, MODEL, MAX_TOKENS
from evaluators.lenses import ANALYSIS_STANDARDS, Lens
from evaluators.schemas import EvaluatorResult

logger = logging.getLogger(__name__)

# A schema-valid response can still be garbage: in one real run the model broke
# off the analysis mid-sentence and filled the remaining fields with fragments
# ("killer_risk": "none", empty lists). Such output is retried once, then
# reported as an error instead of being written into the reports.
MAX_ATTEMPTS = 2
MIN_SUMMARY_CHARS = 40
MIN_REASON_CHARS = 30
PLACEHOLDER_VALUES = {"", "none", "n/a", "na", "null", "unknown", "-"}


class InvalidResultError(RuntimeError):
    """Raised when the model keeps returning structurally valid but unusable output."""


def validate_result(result: EvaluatorResult) -> list[str]:
    """Return the problems that make a parsed result unusable; empty if it is fine."""
    problems = []
    if len(result.summary.strip()) < MIN_SUMMARY_CHARS:
        problems.append(f"summary too short ({result.summary.strip()!r})")
    if len(result.confidence_reason.strip()) < MIN_REASON_CHARS:
        problems.append(f"confidence_reason too short ({result.confidence_reason.strip()!r})")
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
        self.client = Anthropic(api_key=ANTHROPIC_API_KEY)
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
        input_tokens = 0
        output_tokens = 0
        try:
            for attempt in range(1, MAX_ATTEMPTS + 1):
                response = self._request()
                # Tokens of a discarded attempt are billed too, so count them.
                input_tokens += response.usage.input_tokens
                output_tokens += response.usage.output_tokens

                result = response.parsed_output
                problems = validate_result(result)
                if not problems:
                    break
                logger.warning(
                    f"{self.lens.name}: invalid result on attempt {attempt}/{MAX_ATTEMPTS} "
                    f"(request_id={response._request_id}): {'; '.join(problems)}"
                )
            else:
                raise InvalidResultError(
                    f"{MAX_ATTEMPTS} attempts returned malformed output: {'; '.join(problems)}"
                )

            return {
                "evaluator": self.lens.key,
                "evaluator_display": self.lens.name,
                "status": "success",
                **result.model_dump(mode="json"),
                "tokens_used": input_tokens + output_tokens,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
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
            }

    def _request(self):
        """Send one request and check why generation stopped. Raises on unusable responses."""
        system_prompt = self.get_system_prompt()
        user_prompt = f"{self.get_evaluation_prompt()}\n\nBusiness Idea:\n{self.business_idea}"
        logger.debug(
            f"{self.lens.name}: request model={self.model} max_tokens={self.max_tokens} "
            f"system_chars={len(system_prompt)} user_chars={len(user_prompt)}"
        )
        response = self.client.messages.parse(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            output_format=EvaluatorResult,
        )
        logger.debug(
            f"{self.lens.name}: response request_id={response._request_id} "
            f"stop_reason={response.stop_reason} input_tokens={response.usage.input_tokens} "
            f"output_tokens={response.usage.output_tokens}"
        )

        if response.stop_reason == "max_tokens":
            raise RuntimeError(
                f"Response truncated at max_tokens={self.max_tokens}; "
                "increase MAX_TOKENS in config.py"
            )
        if response.stop_reason == "refusal":
            raise RuntimeError("Model refused to evaluate this idea")
        return response

    @property
    def full_prompt(self) -> str:
        """Full prompt, for debugging."""
        return (
            f"=== SYSTEM PROMPT ===\n{self.get_system_prompt()}\n\n"
            f"=== EVALUATION PROMPT ===\n{self.get_evaluation_prompt()}\n\n"
            f"=== BUSINESS IDEA ===\n{self.business_idea}\n"
        )
