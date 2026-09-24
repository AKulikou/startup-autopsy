"""
Builds the synthesis report from all evaluator results.

Interim version: it only restates and compares what the evaluators returned,
without drawing its own conclusions. A Claude-based synthesis replaces it in Phase 3.
"""

from collections import Counter

from evaluators.schemas import confidence_label, verdict_label


class ReportAggregator:
    """Combines the results of any number of evaluators into one Markdown report."""

    def aggregate(self, results: list[dict]) -> str:
        """
        Build the synthesis report.

        Args:
            results: Result dicts from Evaluator.evaluate(), successful or not

        Returns:
            str: Markdown report
        """
        successful = [r for r in results if r["status"] == "success"]
        failed = [r for r in results if r["status"] == "error"]

        if not successful:
            return self._error_report(failed)

        sections = [
            "# Startup Autopsy — Synthesis Report",
            f"## Verdicts\n\n{self._verdict_table(successful)}",
            f"## Verdict Agreement\n\n{self._verdict_agreement(successful)}",
            f"## Evaluator Summaries\n\n{self._summaries(successful)}",
            f"## Killer Risks\n\n{self._killer_risks(successful)}",
            f"## Next Steps by Evaluator\n\n{self._next_steps(successful)}",
        ]
        if failed:
            sections.append(f"## Failed Evaluators\n\n{self._failures(failed)}")

        sections.append(
            f"---\n\n*Aggregated from {len(successful)} of {len(results)} evaluators. "
            "Full reasoning is in the per-evaluator reports.*"
        )
        return "\n\n".join(sections) + "\n"

    @staticmethod
    def _verdict_table(results: list[dict]) -> str:
        rows = "\n".join(
            f"| {r['evaluator_display']} | {verdict_label(r['verdict'])} "
            f"| {confidence_label(r['confidence'])} |"
            for r in results
        )
        return "| Evaluator | Verdict | Confidence |\n|---|---|---|\n" + rows

    @staticmethod
    def _verdict_agreement(results: list[dict]) -> str:
        if len(results) < 2:
            return "Only one evaluator ran, so there is nothing to compare."

        counts = Counter(r["verdict"] for r in results)
        if len(counts) == 1:
            return f"All {len(results)} evaluators agree: **{verdict_label(next(iter(counts)))}**."

        split = ", ".join(
            f"{verdict_label(verdict)} × {count}" for verdict, count in counts.most_common()
        )
        return (
            f"Evaluators disagree ({split}). "
            "Compare their summaries and killer risks below to see why."
        )

    @staticmethod
    def _summaries(results: list[dict]) -> str:
        return "\n\n".join(
            f"**{r['evaluator_display']}** — {r['summary']}\n\n"
            f"*Confidence {confidence_label(r['confidence'])}: {r['confidence_reason']}*"
            for r in results
        )

    @staticmethod
    def _killer_risks(results: list[dict]) -> str:
        return "\n".join(f"- **{r['evaluator_display']}:** {r['killer_risk']}" for r in results)

    @staticmethod
    def _next_steps(results: list[dict]) -> str:
        blocks = []
        for r in results:
            steps = "\n".join(f"{i}. {step}" for i, step in enumerate(r["next_steps"], start=1))
            blocks.append(f"**{r['evaluator_display']}**\n\n{steps}")
        return "\n\n".join(blocks)

    @staticmethod
    def _failures(failed: list[dict]) -> str:
        return "\n".join(f"- **{r['evaluator_display']}:** {r['error']}" for r in failed)

    def _error_report(self, failed: list[dict]) -> str:
        return (
            "# Startup Autopsy — Synthesis Report\n\n"
            f"All evaluators failed.\n\n{self._failures(failed)}\n"
        )
