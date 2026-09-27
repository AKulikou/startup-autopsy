"""
Writes analysis results to Markdown files, one directory per run:

    results/2026-09-24_18-48-18_fitness_tracker/
        report.md                     the final report for the reader
        report.json                   the same analysis as structured data
        lenses/
            no_code_stack_master.md   one detailed report per lens
            reality_auditor.md

The timestamp comes first so that runs sort chronologically by name.
"""

import re
from datetime import datetime
from pathlib import Path

from evaluators.schemas import confidence_label, verdict_label, verdict_meaning

REPORT_FILENAME = "report.md"
JSON_FILENAME = "report.json"
LENSES_DIR = "lenses"


def lens_report_path(evaluator_name: str) -> str:
    """
    Path of a lens report relative to the run directory, also used for links.

    Example: "No-Code Stack Master" -> "lenses/no_code_stack_master.md"
    """
    cleaned = re.sub(r'[^\w\s]', ' ', evaluator_name)
    cleaned = re.sub(r'_+', '_', cleaned.lower().strip().replace(" ", "_"))
    return f"{LENSES_DIR}/{cleaned}.md"


def table_cell(text: str) -> str:
    """Make text safe for a Markdown table cell."""
    return text.replace("|", "\\|").replace("\n", " ")


class ResultWriter:
    """Writes the final report and the lens reports to Markdown files."""

    def __init__(self, results_directory: str = "results"):
        """
        Args:
            results_directory (str): Directory for result files
        """
        self.results_dir = Path(results_directory)
        self.results_dir.mkdir(parents=True, exist_ok=True)

    def create_run_dir(self, idea_name: str, started_at: datetime) -> Path:
        """
        Create and return the directory for one analysis run. Two runs of the same
        idea started in the same second (parallel MCP calls) get _2, _3, ... so a
        finished, paid-for analysis is never lost to a name clash.
        """
        base = f"{started_at.strftime('%Y-%m-%d_%H-%M-%S')}_{idea_name}"
        for attempt in range(1, 100):
            run_dir = self.results_dir / (base if attempt == 1 else f"{base}_{attempt}")
            try:
                run_dir.mkdir(parents=True, exist_ok=False)
                return run_dir
            except FileExistsError:
                continue
        raise FileExistsError(f"No free run directory name for {base}")

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
        filepath = run_dir / lens_report_path(result["evaluator_display"])
        filepath.parent.mkdir(exist_ok=True)
        filepath.write_text(self._format_markdown(idea_name, started_at, result), encoding="utf-8")
        return filepath

    def _format_markdown(self, idea_name: str, started_at: datetime, result: dict) -> str:
        """Render the structured fields first, then the full analysis."""
        timestamp = started_at.strftime("%Y-%m-%d %H:%M:%S")

        assumption_rows = "\n".join(
            f"| {table_cell(a['statement'])} | {table_cell(a['how_to_test'])} "
            f"| {table_cell(a['failure_signal'])} |"
            for a in result["key_assumptions"]
        )
        next_steps = "\n".join(
            f"{i}. {step}" for i, step in enumerate(result["next_steps"], start=1)
        )
        red_flags = "\n".join(f"- {flag}" for flag in result["out_of_lens_red_flags"]) or "None reported."

        return f"""# Startup Autopsy — {result['evaluator_display']}

- **Idea:** {idea_name}
- **Analyzed:** {timestamp}
- **Tokens used:** {result['tokens_used']} (input {result['input_tokens']}, output {result['output_tokens']})

---

## Lens Verdict: {verdict_label(result['verdict'])}

*{verdict_meaning(result['verdict']).capitalize()}.*

{result['summary']}

**Confidence:** {confidence_label(result['confidence'])} — {result['confidence_reason']}

## Killer Risk Within This Lens

{result['killer_risk']}

## Red Flags Outside This Lens

{red_flags}

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

    def save_report(self, run_dir: Path, report: str) -> Path:
        """Save the final report and return its path."""
        filepath = run_dir / REPORT_FILENAME
        filepath.write_text(report, encoding="utf-8")
        return filepath

    def save_json(self, run_dir: Path, document: str) -> Path:
        """Save the structured report and return its path."""
        filepath = run_dir / JSON_FILENAME
        filepath.write_text(document, encoding="utf-8")
        return filepath
