"""
Prints token usage and estimated API cost per evaluator.
"""

import logging

logger = logging.getLogger(__name__)

TABLE_WIDTH = 70


class TokenSummary:
    """Formats the token usage table for the console and log."""

    # Flat rate for all tokens; separate input/output pricing is planned.
    COST_PER_1K_TOKENS = 0.003

    @staticmethod
    def print_summary(results: list[dict]) -> None:
        """Log input/output tokens and estimated cost for each successful evaluator."""
        successful = [r for r in results if r["status"] == "success"]
        if not successful:
            logger.info("No successful results; token summary skipped.")
            return

        logger.info("\n" + "=" * TABLE_WIDTH)
        logger.info("TOKEN USAGE SUMMARY")
        logger.info("=" * TABLE_WIDTH)
        logger.info(f"{'Evaluator':<30} | {'Input / Output':<20} | {'Cost (USD)':<10}")
        logger.info("-" * TABLE_WIDTH)

        total_input = 0
        total_output = 0
        for result in successful:
            total_input += result["input_tokens"]
            total_output += result["output_tokens"]
            tokens = f"{result['input_tokens']} / {result['output_tokens']}"
            cost = TokenSummary._calculate_cost(result["tokens_used"])
            logger.info(f"{result['evaluator_display']:<30} | {tokens:<20} | ${cost:<9.4f}")

        logger.info("-" * TABLE_WIDTH)
        tokens = f"{total_input} / {total_output}"
        cost = TokenSummary._calculate_cost(total_input + total_output)
        logger.info(f"{'TOTAL':<30} | {tokens:<20} | ${cost:<9.4f}")
        logger.info("=" * TABLE_WIDTH + "\n")

    @staticmethod
    def _calculate_cost(tokens: int) -> float:
        """Estimated cost in USD for the given number of tokens."""
        return tokens / 1000 * TokenSummary.COST_PER_1K_TOKENS
