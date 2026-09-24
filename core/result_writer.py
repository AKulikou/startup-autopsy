"""
Writes analysis results to Markdown files, one directory per run:

    results/2026-09-24_18-48-18_fitness_tracker/
        00_synthesis.md
        no_code_stack_master.md
        reality_auditor.md

The timestamp comes first so that runs sort chronologically by name.
"""

import re
from pathlib import Path
from datetime import datetime


class ResultWriter:
    """Writes evaluator results to Markdown files."""

    def __init__(self, results_directory: str = "results"):
        """
        Args:
            results_directory (str): Directory for result files
        """
        self.results_dir = Path(results_directory)
        self.results_dir.mkdir(parents=True, exist_ok=True)

    def _clean_evaluator_name(self, evaluator_name: str) -> str:
        """
        Strip special characters and format the name for a filename.

        Example: "No-Code Stack Master" -> "no_code_stack_master"
        """
        cleaned = re.sub(r'[^\w\s]', ' ', evaluator_name)
        cleaned = cleaned.lower().strip().replace(" ", "_")
        return re.sub(r'_+', '_', cleaned)

    def create_run_dir(self, idea_name: str, started_at: datetime) -> Path:
        """Create and return the directory for one analysis run."""
        run_dir = self.results_dir / f"{started_at.strftime('%Y-%m-%d_%H-%M-%S')}_{idea_name}"
        run_dir.mkdir(parents=True, exist_ok=False)
        return run_dir

    def save_result(self, run_dir: Path, idea_name: str, started_at: datetime, result: dict) -> Path:
        """
        Save a successful evaluator result to a Markdown file in the run directory.

        Args:
            run_dir (Path): Directory from create_run_dir()
            idea_name (str): Idea name
            started_at (datetime): When the run started
            result (dict): Successful result dict from Evaluator.evaluate()

        Returns:
            Path: Path to the saved file
        """
        filepath = run_dir / f"{self._clean_evaluator_name(result['evaluator_display'])}.md"
        filepath.write_text(self._format_markdown(idea_name, started_at, result), encoding="utf-8")
        return filepath

    def _format_markdown(self, idea_name: str, started_at: datetime, result: dict) -> str:
        """Render the structured fields first, then the full analysis."""
        timestamp = started_at.strftime("%Y-%m-%d %H:%M:%S")

        assumption_rows = "\n".join(
            f"| {self._cell(a['statement'])} | {self._cell(a['how_to_test'])} "
            f"| {self._cell(a['failure_signal'])} |"
            for a in result["key_assumptions"]
        )
        next_steps = "\n".join(
            f"{i}. {step}" for i, step in enumerate(result["next_steps"], start=1)
        )

        return f"""# Startup Autopsy — {result['evaluator_display']}

- **Idea:** {idea_name}
- **Analyzed:** {timestamp}
- **Tokens used:** {result['tokens_used']} (input {result['input_tokens']}, output {result['output_tokens']})

---

## Verdict: {result['verdict']}

{result['summary']}

**Confidence:** {result['confidence']} — {result['confidence_reason']}

## Killer Risk

{result['killer_risk']}

## Key Assumptions

| Assumption | How to test | Failure signal |
|---|---|---|
{assumption_rows}

## Next Steps

{next_steps}

---

## Full Analysis

{result['analysis']}
"""

    @staticmethod
    def _cell(text: str) -> str:
        """Make text safe for a Markdown table cell."""
        return text.replace("|", "\\|").replace("\n", " ")

    def save_synthesis(self, run_dir: Path, synthesis: str) -> Path:
        """Save the synthesis report; the 00_ prefix keeps it first in the directory."""
        filepath = run_dir / "00_synthesis.md"
        filepath.write_text(synthesis, encoding="utf-8")
        return filepath
