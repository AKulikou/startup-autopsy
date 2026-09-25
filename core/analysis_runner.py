"""
Runs the full analysis of one business idea: input check, lenses, synthesis, reports.

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
from typing import Callable, Optional

from config import ENABLED_LENSES, MODEL, REPORT_TRANSLATION, TRANSLATE_LENS_REPORTS
from evaluators.evaluator import Evaluator
from evaluators.lenses import select_lenses
from evaluators.schemas import confidence_label, verdict_label
from gate.idea_gate import GATE_LABEL, NEXT_STEP_HINT, IdeaGate
from gate.schemas import GateDecision, gate_decision_label
from core.idea_input import InvalidIdeaError, prepare_idea
from core.idea_processor import IdeaProcessor
from core.report_builder import build_report
from core.translator import translate_markdown
from core.token_summary import estimate_cost, format_cost, log_token_summary
from synthesis.synthesizer import SYNTHESIS_LABEL, Synthesizer

logger = logging.getLogger(__name__)


class AnalysisRunner:
    """Orchestrates evaluation of an idea by all enabled lenses."""

    def __init__(
        self,
        processor: IdeaProcessor,
        confirm_vague_idea: Optional[Callable[[dict], bool]] = None,
    ):
        """
        Args:
            processor: Idea input and result output
            confirm_vague_idea: Asked whether to analyze an idea the input check found
                too vague; without it such ideas are not analyzed. The CLI asks the user.
        """
        self.processor = processor
        self.lenses = select_lenses(ENABLED_LENSES)
        self.confirm_vague_idea = confirm_vague_idea

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

        analysis = self.analyze(idea_content)
        if not analysis["analyzed"]:
            log_token_summary([analysis["gate"]])
            return False
        results, synthesis = analysis["lenses"], analysis["synthesis"]

        run_dir = self.processor.create_run_dir(idea_name, started_at)
        lens_paths = self._save_reports(results, run_dir, idea_name, started_at)
        report_path = self.processor.save_report(
            run_dir,
            build_report(idea_name, started_at, synthesis, results, analysis["input_note"]),
        )
        logger.info(f"Report: {report_path}")
        translations = []
        if REPORT_TRANSLATION:
            to_translate = [report_path] + (lens_paths if TRANSLATE_LENS_REPORTS else [])
            translations = self._translate_reports(to_translate, REPORT_TRANSLATION)
        log_token_summary([analysis["gate"]] + results + [synthesis] + translations)

        return synthesis["status"] == "success"

    def analyze(self, idea_content: str) -> dict:
        """
        Analyze a prepared idea text without writing any files: input check,
        lenses, synthesis. Used by run(), by the eval runner, and later by an
        MCP server.

        Returns:
            {"analyzed": bool, "gate": dict, "input_note": str | None,
             "lenses": list[dict], "synthesis": dict | None}
        """
        gate = self._run_gate(idea_content)
        if not self._gate_allows(gate):
            return {"analyzed": False, "gate": gate, "input_note": None,
                    "lenses": [], "synthesis": None}
        input_note = self._input_note(gate)
        lenses = self._run_evaluators(idea_content, input_note)
        synthesis = self._run_synthesis(idea_content, lenses, input_note)
        return {"analyzed": True, "gate": gate, "input_note": input_note,
                "lenses": lenses, "synthesis": synthesis}

    def _load_idea(self, idea_name: str) -> Optional[str]:
        raw_content = self.processor.load_idea(idea_name)
        if raw_content is None:
            return None  # load_idea has logged the reason

        try:
            idea_content, quotes_replaced = prepare_idea(raw_content)
        except InvalidIdeaError as e:
            logger.error(f"Idea '{idea_name}' not analyzed. {e}")
            logger.debug(f"Local input check: rejection code {e.code}")
            logger.error(NEXT_STEP_HINT)
            return None
        if quotes_replaced:
            logger.debug(f"Replaced {quotes_replaced} straight double quotes in the idea text")

        logger.info(
            f"Idea: {idea_name} ({len(idea_content)} chars), "
            f"{len(self.lenses)} lenses, model {MODEL}"
        )
        return idea_content

    def _run_gate(self, idea_content: str) -> dict:
        gate = IdeaGate(idea_content).check()
        duration = f"{gate['duration_s']:.0f}s"
        if gate["status"] == "success":
            logger.info(f"[{GATE_LABEL}] ... done in {duration}: {gate_decision_label(gate['decision'])}")
            logger.debug(f"{GATE_LABEL}: decision code {gate['decision']}")
        return gate

    def _gate_allows(self, gate: dict) -> bool:
        """Decide whether the analysis runs, and tell the user why if it does not."""
        if gate["status"] != "success":
            logger.warning(
                f"[{GATE_LABEL}] ... FAILED: {gate['error']}; continuing without the input check"
            )
            return True

        if gate["injection_suspected"]:
            logger.warning(
                f"[{GATE_LABEL}] the idea text seems to contain instructions for an AI; "
                "the analysis treats them as part of the idea, not as instructions"
            )

        decision = GateDecision(gate["decision"])
        if decision == GateDecision.NOT_AN_IDEA:
            logger.error(f"Reason: {gate['reason']}")
            logger.error(NEXT_STEP_HINT)
            return False
        if decision == GateDecision.TOO_VAGUE:
            logger.warning(f"Reason: {gate['reason']}")
            logger.warning(f"Missing: {'; '.join(gate['missing_information'])}")
            if self.confirm_vague_idea and self.confirm_vague_idea(gate):
                logger.info("Analyzing anyway at the user's request")
                return True
            logger.info("Not analyzed. " + NEXT_STEP_HINT)
            return False
        return True

    @staticmethod
    def _input_note(gate: dict) -> Optional[str]:
        """A note for the synthesis and the report when the input was flagged."""
        if gate["status"] != "success":
            return None
        notes = []
        if gate["decision"] == GateDecision.TOO_VAGUE.value:
            notes.append(
                f"The input check rated this idea too vague ({gate['reason'].rstrip('.')}; missing: "
                f"{', '.join(gate['missing_information'])}). It was analyzed anyway at the "
                "founder's request, so the conclusions rest on assumptions the lenses made."
            )
        if gate["injection_suspected"]:
            notes.append(
                "The idea text appears to contain instructions addressed to an AI; "
                "they were treated as part of the idea, not followed."
            )
        return " ".join(notes) or None

    def _run_evaluators(self, idea_content: str, input_note: Optional[str]) -> list[dict]:
        total = len(self.lenses)
        prefixes = [f"[{index}/{total}] {lens.name}" for index, lens in enumerate(self.lenses, start=1)]
        results: list[Optional[dict]] = [None] * total

        started = time.monotonic()
        # One thread per lens: all enabled lenses start at once.
        with ThreadPoolExecutor(max_workers=total) as pool:
            futures = {}
            for index, lens in enumerate(self.lenses):
                logger.info(f"{prefixes[index]} ... started")
                futures[pool.submit(Evaluator(lens, idea_content, input_note).evaluate)] = index
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
    ) -> list[Path]:
        paths = []
        for result in results:
            if result["status"] == "success":
                path = self.processor.save_analysis(run_dir, idea_name, started_at, result)
                logger.debug(f"Saved {result['evaluator_display']} report: {path}")
                paths.append(path)
        return paths

    @staticmethod
    def _translate_reports(paths: list[Path], language: str) -> list[dict]:
        """
        Write <name>.<language>.md next to each English report. A failed
        translation is logged and skipped; the English report is unaffected.
        """
        suffix = language.strip().lower().replace(" ", "_")
        logger.info(f"[Translation] ... started: {len(paths)} report(s) into {language}")

        def translate(path: Path) -> dict:
            outcome = translate_markdown(path.read_text(encoding="utf-8"), language)
            outcome["evaluator_display"] = f"Translation of {path.name}"
            if outcome["status"] == "success":
                path.with_name(f"{path.stem}.{suffix}.md").write_text(outcome["text"], encoding="utf-8")
            return outcome

        with ThreadPoolExecutor(max_workers=len(paths)) as pool:
            outcomes = list(pool.map(translate, paths))

        for outcome in outcomes:
            if outcome["status"] != "success":
                logger.warning(f"[Translation] {outcome['evaluator_display']} FAILED: {outcome['error']}")
        done = [o for o in outcomes if o["status"] == "success"]
        if done:
            input_tokens = sum(o["input_tokens"] for o in done)
            output_tokens = sum(o["output_tokens"] for o in done)
            logger.info(
                f"[Translation] ... done: {len(done)} of {len(paths)} report(s), "
                f"{input_tokens}/{output_tokens} tokens, "
                f"{format_cost(estimate_cost(input_tokens, output_tokens))}; "
                f"main report: report.{suffix}.md"
            )
        return outcomes

    def _run_synthesis(
        self, idea_content: str, results: list[dict], input_note: Optional[str]
    ) -> dict:
        succeeded = sum(r["status"] == "success" for r in results)
        if not succeeded:
            error = "no lens succeeded, nothing to synthesize"
            logger.error(f"[{SYNTHESIS_LABEL}] skipped: {error}")
            return {"evaluator_display": SYNTHESIS_LABEL, "status": "error", "error": error}

        logger.info(f"[{SYNTHESIS_LABEL}] ... started ({succeeded} of {len(results)} lenses)")
        synthesis = Synthesizer(idea_content, results, input_note).synthesize()
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
