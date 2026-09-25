"""
Facade over idea input and result output.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from .file_manager import FileManager
from .result_writer import ResultWriter

logger = logging.getLogger(__name__)


class IdeaProcessor:
    """Loads ideas and saves analysis results."""

    def __init__(self, ideas_dir: str = "ideas", results_dir: str = "results"):
        self.file_manager = FileManager(ideas_dir)
        self.result_writer = ResultWriter(results_dir)

    def get_available_ideas(self) -> tuple[list[str], Path]:
        """Return the available idea names and the directory they were found in."""
        return self.file_manager.list_ideas(), self.file_manager.get_full_path()

    def load_idea(self, idea_name: str) -> Optional[str]:
        """Return the idea text, or None if it cannot be read (the error is logged)."""
        try:
            return self.file_manager.read_idea(idea_name)
        except OSError as e:
            logger.error(f"Cannot load idea '{idea_name}': {e}")
            return None

    def create_run_dir(self, idea_name: str, started_at: datetime) -> Path:
        """Create the output directory for one analysis run."""
        return self.result_writer.create_run_dir(idea_name, started_at)

    def save_analysis(self, run_dir: Path, idea_name: str, started_at: datetime, result: dict) -> Path:
        """Save one evaluator's successful result and return the file path."""
        return self.result_writer.save_result(run_dir, idea_name, started_at, result)

    def save_report(self, run_dir: Path, report: str) -> Path:
        """Save the final report and return the file path."""
        return self.result_writer.save_report(run_dir, report)
