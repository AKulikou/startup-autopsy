"""
Startup Autopsy as an MCP server, so Claude (Claude Code, Claude Desktop) or any
other MCP client can analyze a business idea as a tool.

Run over stdio:
    python mcp_server.py

In stdio mode stdout carries the protocol, so this module never prints: logs go
to logs/mcp_server_<timestamp>.log only.
"""

import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Literal

import anyio
from mcp.server.mcpserver import MCPServer
from mcp_types import ToolAnnotations
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from core.analysis_runner import AnalysisRunner  # noqa: E402
from core.idea_input import InvalidIdeaError, prepare_idea  # noqa: E402
from core.idea_processor import IdeaProcessor  # noqa: E402
from core.result_writer import JSON_FILENAME  # noqa: E402
from evaluators.schemas import confidence_label, verdict_label  # noqa: E402
from gate.idea_gate import NEXT_STEP_HINT, IdeaGate  # noqa: E402
from gate.schemas import gate_decision_label  # noqa: E402

logger = logging.getLogger(__name__)

server = MCPServer(
    name="startup-autopsy",
    title="Startup Autopsy",
    instructions=(
        "Brutally honest evaluation of business ideas. Call check_idea first when an "
        "idea is short or unclear: it is cheap and says what is missing, so you can ask "
        "the user before running analyze_idea, which takes about 3 minutes and costs "
        "about 0.40 USD. Present the verdict without softening it."
    ),
)


class IdeaCheck(BaseModel):
    decision: Literal["EMPTY", "TOO_SHORT", "NOT_AN_IDEA", "TOO_VAGUE", "ANALYZABLE"]
    decision_text: str = Field(description="The decision in plain words.")
    reason: str
    missing_information: list[str] = []
    injection_suspected: bool = False
    hint: str | None = Field(None, description="What to add, when the idea cannot be analyzed.")


class IdeaAnalysis(BaseModel):
    analyzed: bool
    check: IdeaCheck
    verdict: str | None = Field(None, description="Overall verdict in plain words.")
    verdict_code: str | None = None
    confidence: str | None = None
    summary: str | None = None
    report_markdown: str | None = Field(None, description="The full report.md.")
    report_path: str | None = None
    report_json_path: str | None = Field(
        None, description="report.json: the same analysis as structured data."
    )
    error: str | None = None


def _local_rejection(error: InvalidIdeaError) -> IdeaCheck:
    return IdeaCheck(decision=error.code, decision_text=str(error), reason=str(error), hint=NEXT_STEP_HINT)


def _gate_check(gate: dict) -> IdeaCheck:
    if gate["status"] != "success":
        return IdeaCheck(decision="ANALYZABLE", decision_text="input check unavailable",
                         reason=f"The input check failed ({gate['error']}); the idea was not screened.")
    return IdeaCheck(
        decision=gate["decision"],
        decision_text=gate_decision_label(gate["decision"]),
        reason=gate["reason"],
        missing_information=gate["missing_information"],
        injection_suspected=gate["injection_suspected"],
        hint=None if gate["decision"] == "ANALYZABLE" else NEXT_STEP_HINT,
    )


def _run_name(name: str) -> str:
    """A safe directory-name fragment for the results folder."""
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return slug[:50] or "mcp_idea"


def check_idea_sync(idea: str) -> IdeaCheck:
    try:
        text, _ = prepare_idea(idea)
    except InvalidIdeaError as e:
        return _local_rejection(e)
    return _gate_check(IdeaGate(text).check())


def analyze_idea_sync(idea: str, name: str, analyze_if_vague: bool) -> IdeaAnalysis:
    started_at = datetime.now()
    try:
        text, _ = prepare_idea(idea)
    except InvalidIdeaError as e:
        return IdeaAnalysis(analyzed=False, check=_local_rejection(e))

    runner = AnalysisRunner(IdeaProcessor(), confirm_vague_idea=lambda gate: analyze_if_vague)
    analysis = runner.analyze(text)
    check = _gate_check(analysis["gate"])
    if not analysis["analyzed"]:
        return IdeaAnalysis(analyzed=False, check=check)

    report_path = runner.save(_run_name(name), analysis, started_at)
    synthesis = analysis["synthesis"]
    result = IdeaAnalysis(
        analyzed=True, check=check,
        report_markdown=report_path.read_text(encoding="utf-8"), report_path=str(report_path),
        report_json_path=str(report_path.with_name(JSON_FILENAME)),
    )
    if synthesis["status"] != "success":
        result.error = f"The synthesis failed ({synthesis['error']}); the report has no overall verdict."
        return result
    result.verdict = verdict_label(synthesis["verdict"])
    result.verdict_code = synthesis["verdict"]
    result.confidence = confidence_label(synthesis["confidence"])
    result.summary = synthesis["summary"]
    return result


@server.tool(
    annotations=ToolAnnotations(title="Check a business idea", read_only_hint=True, open_world_hint=True),
)
async def check_idea(idea: str) -> IdeaCheck:
    """
    Screen a business idea before the full analysis: is it a business idea at all,
    and is it detailed enough to analyze? Cheap (about 0.003 USD, a few seconds).
    Decisions: EMPTY or TOO_SHORT (rejected locally), NOT_AN_IDEA, TOO_VAGUE (with the
    missing information), ANALYZABLE. It never judges whether the idea is good.
    """
    return await anyio.to_thread.run_sync(check_idea_sync, idea)


@server.tool(
    annotations=ToolAnnotations(title="Analyze a business idea", read_only_hint=False,
                                idempotent_hint=False, open_world_hint=True),
)
async def analyze_idea(idea: str, name: str = "mcp_idea", analyze_if_vague: bool = False) -> IdeaAnalysis:
    """
    Run the full Startup Autopsy analysis of a business idea: an input check, several
    independent lenses in parallel, and a synthesis that decides the overall verdict
    (Viable, Viable if conditions hold, Needs validation, Risky, Not viable) with
    confidence, deciding factors, killer risks, conflicts and next steps.

    Takes about 3 minutes and costs about 0.40 USD. The report is saved under
    results/ and returned in full as report_markdown.

    Args:
        idea: The idea as the founder describes it: product, customer, pricing, plans.
        name: Short name for the results folder.
        analyze_if_vague: Analyze even if the input check finds the idea too vague;
            the report then says its conclusions rest on the lenses' assumptions.
    """
    return await anyio.to_thread.run_sync(analyze_idea_sync, idea, name, analyze_if_vague)


def setup_logging() -> Path:
    logs = ROOT / "logs"
    logs.mkdir(exist_ok=True)
    log_file = logs / f"mcp_server_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"
    handler = logging.FileHandler(log_file, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(handler)
    for noisy in ("anthropic", "httpx2", "httpcore2", "mcp"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    return log_file


if __name__ == "__main__":
    setup_logging()
    server.run()
