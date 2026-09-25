"""
Runs the full analysis of one business idea: lenses, synthesis, reports.

The lenses run in parallel threads (they are independent API calls), so their
"done" lines arrive in completion order. Results are still passed to the
synthesis in the configured lens order. Progress goes to the log one line per
event (INFO); the reports themselves are written only to Markdown files.
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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
        total = len(self.lenses)
        prefixes = [f"[{index}/{total}] {lens.name}" for index, lens in enumerate(self.lenses, start=1)]
        results: list[Optional[dict]] = [None] * total

        started = time.monotonic()
        # One thread per lens: all enabled lenses start at once.
        with ThreadPoolExecutor(max_workers=total) as pool:
            futures = {}
            for index, lens in enumerate(self.lenses):
                logger.info(f"{prefixes[index]} ... started")
                futures[pool.submit(Evaluator(lens, idea_content).evaluate)] = index
            for finished, future in enumerate(as_completed(futures), start=1):
                index = futures[future]
                results[index] = future.result()  # evaluate() never raises
                self._log_lens_result(prefixes[index], results[index], finished, total)

        elapsed = time.monotonic() - started
        busy = sum(r["duration_s"] for r in results)
        logger.info(f"Lenses finished in {elapsed:.0f}s (sum of lens times {busy:.0f}s)")
        return results

    @staticmethod
    def _log_lens_result(prefix: str, result: dict, finished: int, total: int) -> None:
        duration = f"{result['duration_s']:.0f}s"
        progress = f"({finished}/{total} finished)"
        if result["status"] == "success":
            cost = estimate_cost(result["input_tokens"], result["output_tokens"])
            logger.info(
                f"{prefix} ... done in {duration}: {verdict_label(result['verdict'])} "
                f"({confidence_label(result['confidence'])}), "
                f"{len(result['out_of_lens_red_flags'])} red flags, "
                f"{result['input_tokens']}/{result['output_tokens']} tokens, "
                f"{format_cost(cost)} {progress}"
            )
        else:
            logger.error(f"{prefix} ... FAILED in {duration}: {result['error']} {progress}")

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
