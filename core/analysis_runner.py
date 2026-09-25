"""
Runs the full analysis of one business idea: evaluate, save, synthesize.

Progress goes to the log one line per event (INFO); the reports themselves
are written only to Markdown files.
"""

import logging
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import ENABLED_LENSES, MODEL
from evaluators.evaluator import Evaluator
from evaluators.lenses import select_lenses
from evaluators.schemas import confidence_label, verdict_label
from core.idea_processor import IdeaProcessor
from core.report_aggregator import ReportAggregator
from core.token_summary import estimate_cost, format_cost, log_token_summary

logger = logging.getLogger(__name__)


class AnalysisRunner:
    """Orchestrates evaluation of an idea by all enabled lenses."""

    def __init__(self, processor: IdeaProcessor):
        self.processor = processor
        self.lenses = select_lenses(ENABLED_LENSES)
        self.aggregator = ReportAggregator()

    def run(self, idea_name: str) -> bool:
        """
        Run the full analysis cycle for one idea.

        Returns:
            bool: True if at least one evaluator succeeded
        """
        started_at = datetime.now()
        idea_content = self._load_idea(idea_name)
        if not idea_content:
            return False

        results = self._run_evaluators(idea_content)

        run_dir = self.processor.create_run_dir(idea_name, started_at)
        self._save_reports(results, run_dir, idea_name, started_at)
        self._save_synthesis(results, run_dir)
        logger.info(f"Reports: {run_dir}")
        log_token_summary(results)

        return any(r["status"] == "success" for r in results)

    def _load_idea(self, idea_name: str) -> Optional[str]:
        idea_content = self.processor.load_idea(idea_name)
        if not idea_content:
            logger.error(f"Idea '{idea_name}' is missing or empty")
            return None

        logger.info(
            f"Idea: {idea_name} ({len(idea_content)} chars), "
            f"{len(self.lenses)} lenses, model {MODEL}"
        )
        return idea_content

    def _run_evaluators(self, idea_content: str) -> list[dict]:
        results = []
        total = len(self.lenses)
        for index, lens in enumerate(self.lenses, start=1):
            prefix = f"[{index}/{total}] {lens.name}"
            logger.info(f"{prefix} ... started")
            result = Evaluator(lens, idea_content).evaluate()
            results.append(result)

            duration = f"{result['duration_s']:.0f}s"
            if result["status"] == "success":
                cost = estimate_cost(result["input_tokens"], result["output_tokens"])
                logger.info(
                    f"{prefix} ... done in {duration}: {verdict_label(result['verdict'])} "
                    f"({confidence_label(result['confidence'])}), "
                    f"{result['input_tokens']}/{result['output_tokens']} tokens, {format_cost(cost)}"
                )
            else:
                logger.error(f"{prefix} ... FAILED in {duration}: {result['error']}")
        return results

    def _save_reports(
        self, results: list[dict], run_dir: Path, idea_name: str, started_at: datetime
    ) -> None:
        for result in results:
            if result["status"] == "success":
                path = self.processor.save_analysis(run_dir, idea_name, started_at, result)
                logger.debug(f"Saved {result['evaluator_display']} report: {path}")

    def _save_synthesis(self, results: list[dict], run_dir: Path) -> None:
        path = self.processor.save_synthesis(run_dir, self.aggregator.aggregate(results))
        logger.debug(f"Saved synthesis: {path}")

        successful = [r for r in results if r["status"] == "success"]
        verdicts = Counter(verdict_label(r["verdict"]) for r in successful)
        split = ", ".join(f"{label} x{count}" for label, count in verdicts.most_common())
        logger.info(
            f"Synthesis: {len(successful)} of {len(results)} lenses succeeded"
            + (f"; {split}" if split else "")
        )
