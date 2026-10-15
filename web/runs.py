"""
Analysis runs started from the web page: one at a time, each in its own thread.

A run is paid for, so a double click or a second browser tab must not start a
second one in parallel: RunManager.start() refuses while a run is active. Runs
live only in memory (the page has no history); their reports are written to
results/ like any other run.
"""

import logging
import threading
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from core.analysis_runner import AnalysisRunner
from core.idea_processor import IdeaProcessor
from core.progress import ProgressEvent

logger = logging.getLogger(__name__)

# Finished runs kept for their result and downloads; older ones are forgotten
# (their files stay in results/).
KEEP_RUNS = 10


class BusyError(RuntimeError):
    """Another run is still active."""

    def __init__(self, active_run_id: str | None):
        super().__init__("Another analysis is already running.")
        self.active_run_id = active_run_id


@dataclass
class Run:
    id: str
    idea: str
    name: str
    language: str | None
    analyze_if_vague: bool
    started_at: datetime
    analysis: dict | None = None
    report_path: Path | None = None
    error: str | None = None
    _events: list[dict] = field(default_factory=list)
    _finished: bool = False
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def add_event(self, event: ProgressEvent) -> None:
        with self._lock:
            self._events.append(event.to_dict())

    def finish(self, event: ProgressEvent) -> None:
        """Add the last event; readers see it and the finished flag together."""
        with self._lock:
            self._events.append(event.to_dict())
            self._finished = True

    def events_since(self, count: int) -> tuple[list[dict], bool]:
        """The events after the first `count`, and whether the run has finished."""
        with self._lock:
            return self._events[count:], self._finished

    @property
    def finished(self) -> bool:
        with self._lock:
            return self._finished

    def cost_usd(self) -> float:
        """Estimated cost of the calls made so far (calls with unknown tokens count as 0)."""
        with self._lock:
            return sum(e["cost_usd"] or 0.0 for e in self._events if e["stage"] != "run")


class RunManager:
    def __init__(self, results_dir: Path):
        self.results_dir = results_dir
        self._busy = threading.Lock()
        self._runs: OrderedDict[str, Run] = OrderedDict()
        self._active: str | None = None

    def start(self, idea: str, name: str, language: str | None, analyze_if_vague: bool) -> Run:
        """
        Start an analysis of a prepared idea text in a background thread.

        Raises:
            BusyError: if a run is still active
        """
        if not self._busy.acquire(blocking=False):
            raise BusyError(self._active)
        try:
            run = Run(id=uuid.uuid4().hex[:12], idea=idea, name=name, language=language,
                      analyze_if_vague=analyze_if_vague, started_at=datetime.now())
            self._runs[run.id] = run
            while len(self._runs) > KEEP_RUNS:
                self._runs.popitem(last=False)
            self._active = run.id
            threading.Thread(target=self._execute, args=(run,), name=f"run-{run.id}", daemon=True).start()
        except BaseException:
            self._active = None
            self._busy.release()
            raise
        return run

    def get(self, run_id: str) -> Run | None:
        return self._runs.get(run_id)

    @property
    def active_run_id(self) -> str | None:
        return self._active

    def _execute(self, run: Run) -> None:
        final = None
        try:
            logger.info(f"Web run {run.id} started: {run.name}")
            runner = AnalysisRunner(
                IdeaProcessor(results_dir=str(self.results_dir)),
                confirm_vague_idea=lambda gate: run.analyze_if_vague,
                on_progress=run.add_event,
            )
            run.analysis = runner.analyze(run.idea)
            if run.analysis["analyzed"]:
                # "English" means no translated copy: the page's checkbox decides,
                # not REPORT_TRANSLATION from .env.
                run.report_path = runner.save(run.name, run.analysis, run.started_at,
                                              language=run.language or "English")
            final = ProgressEvent("run", "done", text="analyzed" if run.analysis["analyzed"]
                                  else "not analyzed", cost_usd=run.cost_usd())
        except Exception as e:
            logger.exception(f"Web run {run.id} failed")
            run.error = f"{type(e).__name__}: {e}"
            final = ProgressEvent("run", "failed", text=run.error, cost_usd=run.cost_usd())
        finally:
            # Free the lock before the last event, so the page can start the next
            # run (for example "analyze anyway") as soon as it sees this one end.
            self._active = None
            self._busy.release()
            run.finish(final or ProgressEvent("run", "failed", text="interrupted"))
            logger.info(f"Web run {run.id} finished, est. cost ${run.cost_usd():.4f}")
