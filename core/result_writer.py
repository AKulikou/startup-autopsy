"""
Writes per-evaluator analysis results to Markdown files.
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

    def get_filename(self, idea_name: str, evaluator_name: str = None) -> str:
        """
        Build the result filename: IDEA_NAME[_EVALUATOR]_YYYY-MM-DD_HH-MM-SS.md

        Example: "api_monitor_profitable_app_designer_2026-09-22_15-22-50.md"
        """
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        if evaluator_name:
            return f"{idea_name}_{self._clean_evaluator_name(evaluator_name)}_{timestamp}.md"
        return f"{idea_name}_{timestamp}.md"

    def save_result(self, idea_name: str, result: dict) -> Path:
        """
        Save a successful evaluator result to a Markdown file.

        Args:
            idea_name (str): Idea name
            result (dict): Successful result dict from Evaluator.evaluate()

        Returns:
            Path: Path to the saved file
        """
        filepath = self.results_dir / self.get_filename(idea_name, result["evaluator_display"])
        filepath.write_text(self._format_markdown(idea_name, result), encoding="utf-8")
        return filepath

    def _format_markdown(self, idea_name: str, result: dict) -> str:
        """Render the structured fields first, then the full analysis."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        assumption_rows = "\n".join(
            f"| {self._cell(a['statement'])} | {self._cell(a['how_to_test'])} "
            f"| {self._cell(a['failure_signal'])} |"
            for a in result["key_assumptions"]
        )
        next_steps = "\n".join(
            f"{i}. {step}" for i, step in enumerate(result["next_steps"], start=1)
        )

        return f"""# Startup Autopsy — {result['evaluator_display']}

**Idea:** {idea_name}
**Analyzed:** {timestamp}
**Tokens used:** {result['tokens_used']} (input {result['input_tokens']}, output {result['output_tokens']})

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

    def save_synthesis(self, idea_name: str, synthesis: str) -> Path:
        """Save the synthesis report and return its path."""
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filepath = self.results_dir / f"{idea_name}_SYNTHESIS_{timestamp}.md"
        filepath.write_text(synthesis, encoding="utf-8")
        return filepath
