"""
Runs the full analysis of one business idea: lenses, synthesis, reports.

Progress goes to the log one line per event (INFO); the reports themselves
are written only to Markdown files.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import ENABLED_LENSES, MODEL
from evaluators.evaluator import Evaluator
from evaluators.lenses import select_lenses
from evaluators.schemas import confidence_label, verdict_label
from core.idea_input import InvalidIdeaError, prepare_idea
from core.idea_processor import IdeaProcessor
from core.report_builder import build_report
from core.token_summary import estimate_cost, format_cost, log_token_summary
from synthesis.synthesizer import SYNTHESIS_LABEL, Synthesizer

logger = logging.getLogger(__name__)


class AnalysisRunner:
    """Orchestrates evaluation of an idea by all enabled lenses."""

    def __init__(self, processor: IdeaProcessor):
        self.processor = processor
        self.lenses = select_lenses(ENABLED_LENSES)

    def run(self, idea_name: str) -> bool:
        """
        Run the full analysis cycle for one idea.

        Returns:
            bool: True if the synthesis produced an overall verdict
        """
        started_at = datetime.now()
        idea_content = self._load_idea(idea_name)
        if not idea_content:
            return False

        results = self._run_evaluators(idea_content)
        synthesis = self._run_synthesis(idea_content, results)

        run_dir = self.processor.create_run_dir(idea_name, started_at)
        self._save_reports(results, run_dir, idea_name, started_at)
        report_path = self.processor.save_report(
            run_dir, build_report(idea_name, started_at, synthesis, results)
        )
        logger.info(f"Report: {report_path}")
        log_token_summary(results + [synthesis])

        return synthesis["status"] == "success"

    def _load_idea(self, idea_name: str) -> Optional[str]:
        raw_content = self.processor.load_idea(idea_name)
        if raw_content is None:
            return None  # load_idea has logged the reason

        try:
            idea_content, quotes_replaced = prepare_idea(raw_content)
        except InvalidIdeaError as e:
            logger.error(f"Idea '{idea_name}' rejected before analysis: {e}")
            return None
        if quotes_replaced:
            logger.debug(f"Replaced {quotes_replaced} straight double quotes in the idea text")

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
                    f"{len(result['out_of_lens_red_flags'])} red flags, "
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

    def _run_synthesis(self, idea_content: str, results: list[dict]) -> dict:
        succeeded = sum(r["status"] == "success" for r in results)
        if not succeeded:
            error = "no lens succeeded, nothing to synthesize"
            logger.error(f"[{SYNTHESIS_LABEL}] skipped: {error}")
            return {"evaluator_display": SYNTHESIS_LABEL, "status": "error", "error": error}

        logger.info(f"[{SYNTHESIS_LABEL}] ... started ({succeeded} of {len(results)} lenses)")
        synthesis = Synthesizer(idea_content, results).synthesize()
        duration = f"{synthesis['duration_s']:.0f}s"
        if synthesis["status"] == "success":
            cost = estimate_cost(synthesis["input_tokens"], synthesis["output_tokens"])
            logger.info(
                f"[{SYNTHESIS_LABEL}] ... done in {duration}: OVERALL {verdict_label(synthesis['verdict'])} "
                f"({confidence_label(synthesis['confidence'])}), "
                f"{len(synthesis['conflicts'])} conflicts, "
                f"{synthesis['input_tokens']}/{synthesis['output_tokens']} tokens, {format_cost(cost)}"
            )
        else:
            logger.error(f"[{SYNTHESIS_LABEL}] ... FAILED in {duration}: {synthesis['error']}")
        return synthesis
