"""
Token usage and estimated API cost.
"""

import logging
from typing import Optional

from config import MODEL, MODEL_PRICING_PER_MTOK

logger = logging.getLogger(__name__)


def estimate_cost(input_tokens: int, output_tokens: int) -> Optional[float]:
    """Estimated cost in USD for MODEL, or None if its pricing is not configured."""
    pricing = MODEL_PRICING_PER_MTOK.get(MODEL)
    if pricing is None:
        return None
    input_price, output_price = pricing
    return (input_tokens * input_price + output_tokens * output_price) / 1_000_000


def format_cost(cost: Optional[float]) -> str:
    return "cost n/a" if cost is None else f"est. cost ${cost:.4f}"


def log_token_summary(results: list[dict]) -> None:
    """
    Log one total line; the per-call breakdown goes to the log file only.
    Failed calls count when their tokens are known (rejected attempts are billed).
    """
    billed = [r for r in results if "input_tokens" in r]
    if not billed:
        logger.info("Tokens: no billed calls")
        return

    for result in billed:
        cost = estimate_cost(result["input_tokens"], result["output_tokens"])
        logger.debug(
            f"Tokens {result['evaluator_display']}: "
            f"{result['input_tokens']} in / {result['output_tokens']} out, {format_cost(cost)}"
        )

    total_input = sum(r["input_tokens"] for r in billed)
    total_output = sum(r["output_tokens"] for r in billed)
    cost = estimate_cost(total_input, total_output)
    logger.info(f"Tokens: {total_input} in / {total_output} out, {format_cost(cost)} ({MODEL})")
    if cost is None:
        logger.warning(f"No pricing for {MODEL} in config.MODEL_PRICING_PER_MTOK")
