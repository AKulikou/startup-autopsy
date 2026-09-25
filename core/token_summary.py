"""
Token usage and estimated API cost.

A run can use more than one model (the analysis model and a cheaper translation
model), so every call is priced with the model that served it.
"""

import logging
from typing import Optional

from config import MODEL, MODEL_PRICING_PER_MTOK

logger = logging.getLogger(__name__)


def estimate_cost(
    input_tokens: int, output_tokens: int, model: Optional[str] = None
) -> Optional[float]:
    """
    Estimated cost in USD for the given model (default: the analysis MODEL),
    or None if the model's pricing is not configured.
    """
    pricing = MODEL_PRICING_PER_MTOK.get(model or MODEL)
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
    Each result may name its "model"; otherwise the analysis MODEL is assumed.
    """
    billed = [r for r in results if "input_tokens" in r]
    if not billed:
        logger.info("Tokens: no billed calls")
        return

    costs = []
    for result in billed:
        model = result.get("model", MODEL)
        cost = estimate_cost(result["input_tokens"], result["output_tokens"], model)
        costs.append(cost)
        logger.debug(
            f"Tokens {result['evaluator_display']} ({model}): "
            f"{result['input_tokens']} in / {result['output_tokens']} out, {format_cost(cost)}"
        )

    total_input = sum(r["input_tokens"] for r in billed)
    total_output = sum(r["output_tokens"] for r in billed)
    total_cost = None if None in costs else sum(costs)
    models = sorted({r.get("model", MODEL) for r in billed})
    logger.info(
        f"Tokens: {total_input} in / {total_output} out, {format_cost(total_cost)} "
        f"({', '.join(models)})"
    )
    for model in models:
        if model not in MODEL_PRICING_PER_MTOK:
            logger.warning(f"No pricing for {model} in config.MODEL_PRICING_PER_MTOK")
