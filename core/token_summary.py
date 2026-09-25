"""
Prints token usage and estimated API cost per evaluator.
"""

import logging
from typing import Optional

from config import MODEL, MODEL_PRICING_PER_MTOK

logger = logging.getLogger(__name__)

TABLE_WIDTH = 70


class TokenSummary:
    """Formats the token usage table for the console and log."""

    @staticmethod
    def print_summary(results: list[dict]) -> None:
        """Log input/output tokens and estimated cost for each successful evaluator."""
        successful = [r for r in results if r["status"] == "success"]
        if not successful:
            logger.info("No successful results; token summary skipped.")
            return

        pricing = MODEL_PRICING_PER_MTOK.get(MODEL)

        logger.info("\n" + "=" * TABLE_WIDTH)
        logger.info(f"TOKEN USAGE SUMMARY ({MODEL})")
        logger.info("=" * TABLE_WIDTH)
        logger.info(f"{'Evaluator':<30} | {'Input / Output':<20} | {'Cost (USD)':<10}")
        logger.info("-" * TABLE_WIDTH)

        total_input = 0
        total_output = 0
        for result in successful:
            total_input += result["input_tokens"]
            total_output += result["output_tokens"]
            tokens = f"{result['input_tokens']} / {result['output_tokens']}"
            cost = TokenSummary._format_cost(
                TokenSummary._calculate_cost(result["input_tokens"], result["output_tokens"], pricing)
            )
            logger.info(f"{result['evaluator_display']:<30} | {tokens:<20} | {cost:<10}")

        logger.info("-" * TABLE_WIDTH)
        tokens = f"{total_input} / {total_output}"
        cost = TokenSummary._format_cost(
            TokenSummary._calculate_cost(total_input, total_output, pricing)
        )
        logger.info(f"{'TOTAL':<30} | {tokens:<20} | {cost:<10}")
        if pricing is None:
            logger.info(f"No pricing for {MODEL} in config.MODEL_PRICING_PER_MTOK; cost not estimated.")
        logger.info("=" * TABLE_WIDTH + "\n")

    @staticmethod
    def _calculate_cost(
        input_tokens: int, output_tokens: int, pricing: Optional[tuple[float, float]]
    ) -> Optional[float]:
        """Estimated cost in USD, or None if the model's pricing is unknown."""
        if pricing is None:
            return None
        input_price, output_price = pricing
        return (input_tokens * input_price + output_tokens * output_price) / 1_000_000

    @staticmethod
    def _format_cost(cost: Optional[float]) -> str:
        return "n/a" if cost is None else f"${cost:.4f}"
