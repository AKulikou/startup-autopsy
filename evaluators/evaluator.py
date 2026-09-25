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
        system_prompt = self.get_system_prompt()
        user_prompt = f"{self.get_evaluation_prompt()}\n\nBusiness Idea:\n{self.business_idea}"
        logger.debug(
            f"{self.lens.name}: request model={self.model} max_tokens={self.max_tokens} "
            f"system_chars={len(system_prompt)} user_chars={len(user_prompt)}"
        )
        try:
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

            # Check why generation stopped before trusting the output
            if response.stop_reason == "max_tokens":
                raise RuntimeError(
                    f"Response truncated at max_tokens={self.max_tokens}; "
                    "increase MAX_TOKENS in config.py"
                )
            if response.stop_reason == "refusal":
                raise RuntimeError("Model refused to evaluate this idea")

            result = response.parsed_output
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens

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

    @property
    def full_prompt(self) -> str:
        """Full prompt, for debugging."""
        return (
            f"=== SYSTEM PROMPT ===\n{self.get_system_prompt()}\n\n"
            f"=== EVALUATION PROMPT ===\n{self.get_evaluation_prompt()}\n\n"
            f"=== BUSINESS IDEA ===\n{self.business_idea}\n"
        )
