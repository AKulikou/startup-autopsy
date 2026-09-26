"""
Builds report.json: the same analysis as report.md, as structured data for
programs (a web UI, the MCP server, comparisons between runs).

Fields keep their codes (NEEDS_VALIDATION, HIGH), not display words, and
failed calls stay in with their error, so a reader never mistakes a missing
result for a negative one.
"""

import json
from datetime import datetime

from config import EXTRA_LENSES, LENS_SELECTION, MODEL, THINKING, WEB_SEARCH

FORMAT_VERSION = 1


def build_json(idea_name: str, started_at: datetime, analysis: dict) -> str:
    """Render an analysis from AnalysisRunner.analyze() as a JSON document."""
    document = {
        "format_version": FORMAT_VERSION,
        "idea_name": idea_name,
        "analyzed_at": started_at.isoformat(timespec="seconds"),
        "settings": {"model": MODEL, "thinking": THINKING, "lens_selection": LENS_SELECTION,
                     "extra_lenses": list(EXTRA_LENSES), "web_search": WEB_SEARCH},
        "input_check": analysis["gate"],
        "input_note": analysis["input_note"],
        "skipped_lenses": analysis["skipped_lenses"],
        "synthesis": analysis["synthesis"],
        "lenses": analysis["lenses"],
    }
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"
