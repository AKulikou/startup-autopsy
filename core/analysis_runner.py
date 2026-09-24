"""
Runs the full analysis of one business idea: evaluate, save, synthesize.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import ENABLED_LENSES
from evaluators.evaluator import Evaluator
from evaluators.lenses import select_lenses
from core.idea_processor import IdeaProcessor
from core.report_aggregator import ReportAggregator
from core.token_summary import TokenSummary

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
        logger.info(f"\nSaving reports to: {run_dir}")
        self._save_reports(results, run_dir, idea_name, started_at)
        self._save_synthesis(results, run_dir)
        TokenSummary.print_summary(results)

        return any(r["status"] == "success" for r in results)

    def _load_idea(self, idea_name: str) -> Optional[str]:
        idea_content = self.processor.load_idea(idea_name)
        if not idea_content:
            logger.error(f"Idea '{idea_name}' is missing or empty")
            return None

        logger.info(f"\nIdea loaded ({len(idea_content)} characters)")
        logger.info(f"Analyzing with {len(self.lenses)} lenses...\n")
        return idea_content

    def _run_evaluators(self, idea_content: str) -> list[dict]:
        results = []
        for lens in self.lenses:
            result = Evaluator(lens, idea_content).evaluate()
            results.append(result)
            if result["status"] == "error":
                logger.error(f"{result['evaluator_display']} failed: {result['error']}")
        return results

    def _save_reports(
        self, results: list[dict], run_dir: Path, idea_name: str, started_at: datetime
    ) -> None:
        for result in results:
            if result["status"] == "success":
                path = self.processor.save_analysis(run_dir, idea_name, started_at, result)
                logger.info(f"  - {result['evaluator_display']}: {path.name}")

    def _save_synthesis(self, results: list[dict], run_dir: Path) -> None:
        synthesis = self.aggregator.aggregate(results)
        logger.info("\n" + synthesis)
        path = self.processor.save_synthesis(run_dir, synthesis)
        logger.info(f"Synthesis saved: {path.name}\n")
