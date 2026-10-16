"""
Builds report.md, the one report a reader needs: the synthesis verdict and its
reasons first, the lens results as an appendix with links to their full reports.
"""

from datetime import datetime

from config import MODEL
from core.result_writer import lens_report_path, table_cell
from evaluators.schemas import codes_as_words, confidence_label, verdict_label, verdict_meaning


def build_report(
    idea_name: str,
    started_at: datetime,
    synthesis: dict,
    lens_results: list[dict],
    input_note: str | None = None,
    skipped_lenses: list[dict] = (),
) -> str:
    """
    Render the final report. If the synthesis failed, say so and show only the
    lens results instead of inventing an overall verdict. Codes the models wrote
    into their text are shown as words.
    """
    succeeded = sum(r["status"] == "success" for r in lens_results)
    header = (
        f"# Startup Autopsy — {idea_name}\n\n"
        f"- **Analyzed:** {started_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"- **Model:** {MODEL}\n"
        f"- **Lenses:** {succeeded} of {len(lens_results)} succeeded"
    )
    if input_note:
        header += f"\n\n> **Input check:** {input_note}"
    for r in lens_results:
        for warning in r.get("warnings", ()):
            header += f"\n\n> **Warning:** {r['evaluator_display']} {warning}."

    if synthesis["status"] != "success":
        body = (
            "## No Overall Verdict\n\n"
            f"The synthesis failed ({synthesis['error']}), so there is no overall verdict. "
            "The lens results below answer only their own questions; read their reports "
            "for details."
        )
        parts = [header, body, _lens_appendix(lens_results, skipped_lenses)]
        return codes_as_words("\n\n".join(parts) + "\n")

    sections = [
        header,
        f"## Verdict: {verdict_label(synthesis['verdict'])}\n\n"
        f"*{verdict_meaning(synthesis['verdict']).capitalize()}.*\n\n"
        f"{synthesis['summary']}\n\n"
        f"**Confidence:** {confidence_label(synthesis['confidence'])} — "
        f"{synthesis['confidence_reason']}",
        f"## Why: Deciding Factors\n\n{_findings(synthesis['deciding_factors'])}",
        f"## What Could Kill This Project\n\n{_findings(synthesis['killer_risks'])}",
        f"## What Holds Up\n\n{_holds_up(synthesis['what_holds_up'])}",
        f"## Conflicts\n\n{_conflicts(synthesis['conflicts'])}",
        f"## What Must Be True\n\n{_assumptions(synthesis['key_assumptions'])}",
        f"## Next Steps\n\n{_numbered(synthesis['next_steps'])}",
        "---",
        _lens_appendix(lens_results, skipped_lenses),
        f"## Appendix: How the Verdict Was Reached\n\n{synthesis['reasoning']}",
    ]
    return codes_as_words("\n\n".join(sections) + "\n")


def _findings(findings: list[dict]) -> str:
    lines = []
    for f in findings:
        source = f" *({', '.join(f['lenses'])})*" if f["lenses"] else ""
        lines.append(f"- {f['finding']}{source}")
    return "\n".join(lines)


def _holds_up(findings: list[dict]) -> str:
    if not findings:
        return "The lenses found nothing in the idea that clearly holds up."
    return _findings(findings)


def _conflicts(conflicts: list[dict]) -> str:
    if not conflicts:
        return "No conflicts found between the lenses or with the idea's own claims."
    return "\n".join(
        f"- {c['description']}\n  - **Resolution:** {c['resolution']}" for c in conflicts
    )


def _assumptions(assumptions: list[dict]) -> str:
    rows = "\n".join(
        f"| {table_cell(a['statement'])} | {table_cell(a['how_to_test'])} "
        f"| {table_cell(a['failure_signal'])} |"
        for a in assumptions
    )
    return "| Assumption | How to test | Failure signal |\n|---|---|---|\n" + rows


def _numbered(items: list[str]) -> str:
    return "\n".join(f"{i}. {item}" for i, item in enumerate(items, start=1))


def _lens_appendix(lens_results: list[dict], skipped_lenses: list[dict] = ()) -> str:
    rows = []
    for r in lens_results:
        name = r["evaluator_display"]
        if r["status"] == "success":
            rows.append(
                f"| [{name}]({lens_report_path(name)}) | {verdict_label(r['verdict'])} "
                f"| {confidence_label(r['confidence'])} | {table_cell(r['summary'])} |"
            )
        else:
            rows.append(f"| {name} | failed | — | {table_cell(r['error'])} |")
    return (
        "## Appendix: Lens Results\n\n"
        "Each lens verdict answers only that lens's question.\n\n"
        "| Lens | Lens verdict | Confidence | Summary |\n|---|---|---|---|\n" + "\n".join(rows)
        + _skipped(skipped_lenses)
    )


def _skipped(skipped_lenses: list[dict]) -> str:
    if not skipped_lenses:
        return ""
    lines = "\n".join(f"- **{s['lens']}:** {s['reason']}" for s in skipped_lenses)
    return (
        "\n\nNot run, because the lens fit check found their question does not fit "
        f"this idea:\n\n{lines}"
    )
