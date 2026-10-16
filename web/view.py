"""
The result of a web run as the page shows it: meanings in words, never codes.

Verdict and decision codes are kept only where the page needs them for logic
or colour (`verdict`, `decision`); every text a person reads comes from the
*_text fields. report.json keeps the full analysis with its codes.
"""

from core.result_writer import JSON_FILENAME, REPORT_FILENAME
from core.translator import translated_path
from evaluators.lenses import LENSES
from evaluators.schemas import confidence_label, verdict_label, verdict_meaning
from gate.idea_gate import NEXT_STEP_HINT
from gate.schemas import GateDecision, gate_decision_label
from web.languages import NATIVE_NAMES
from web.runs import Run

FOCUS = {lens.key: lens.focus for lens in LENSES}


def download_paths(run: Run) -> dict:
    """Files a finished run offers, by the kind the page asks for; only files that exist."""
    if run.report_path is None:
        return {}
    paths = {"report": run.report_path, "json": run.report_path.with_name(JSON_FILENAME)}
    if run.language:
        paths["translation"] = translated_path(run.report_path, run.language)
    return {kind: path for kind, path in paths.items() if path.exists()}


def run_view(run: Run) -> dict:
    analysis = run.analysis or {}
    view = {
        "analyzed": bool(analysis.get("analyzed")),
        "error": run.error,
        "input_check": _input_check(analysis["gate"]) if analysis else None,
        "input_note": analysis.get("input_note"),
        "synthesis": None,
        "lenses": [],
        "skipped_lenses": analysis.get("skipped_lenses", []),
        "cost_usd": round(run.cost_usd(), 4),
        "downloads": [],
        "translation": None,
    }
    if not view["analyzed"]:
        return view
    view["synthesis"] = _synthesis(analysis["synthesis"])
    view["lenses"] = [_lens(result) for result in analysis["lenses"]]
    view["downloads"] = _downloads(run)
    if run.language:
        made = "translation" in download_paths(run)
        view["translation"] = {
            # English name for sentences in the English page; the language's own name
            # only where it stands alone, as in the language list.
            "language": run.language,
            "native_name": NATIVE_NAMES.get(run.language, run.language),
            "made": made,
            "text": None if made else "The translation failed; the English report is complete.",
        }
    return view


def _input_check(gate: dict) -> dict:
    if gate["status"] != "success":
        return {"decision": None, "text": "input check unavailable",
                "reason": "The input check failed, so the idea was analyzed without it.",
                "missing": [], "hint": None}
    analyzable = gate["decision"] == GateDecision.ANALYZABLE.value
    return {
        "decision": gate["decision"],
        "text": gate_decision_label(gate["decision"]),
        "reason": gate["reason"],
        "missing": gate["missing_information"],
        "hint": None if analyzable else NEXT_STEP_HINT,
    }


def _findings(items: list[dict]) -> list[dict]:
    return [{"text": item["finding"], "lenses": item["lenses"]} for item in items]


def _assumptions(items: list[dict]) -> list[dict]:
    return [{"statement": a["statement"], "how_to_test": a["how_to_test"],
             "failure_signal": a["failure_signal"]} for a in items]


def _synthesis(synthesis: dict) -> dict:
    if synthesis["status"] != "success":
        return {"ok": False,
                "text": f"No overall verdict: the synthesis did not run ({synthesis['error']}). "
                        "The separate analyses below are complete."}
    return {
        "ok": True,
        "verdict": synthesis["verdict"],
        "verdict_text": verdict_label(synthesis["verdict"]),
        "verdict_meaning": verdict_meaning(synthesis["verdict"]),
        "confidence_text": confidence_label(synthesis["confidence"]),
        "confidence_reason": synthesis["confidence_reason"],
        "summary": synthesis["summary"],
        "deciding_factors": _findings(synthesis["deciding_factors"]),
        "killer_risks": _findings(synthesis["killer_risks"]),
        "what_holds_up": _findings(synthesis["what_holds_up"]),
        "conflicts": [{"description": c["description"], "resolution": c["resolution"]}
                      for c in synthesis["conflicts"]],
        "key_assumptions": _assumptions(synthesis["key_assumptions"]),
        "next_steps": synthesis["next_steps"],
    }


def _lens(result: dict) -> dict:
    lens = {"key": result["evaluator"], "name": result["evaluator_display"],
            "focus": FOCUS.get(result["evaluator"]), "ok": result["status"] == "success"}
    if not lens["ok"]:
        return {**lens, "text": f"This analysis failed ({result['error']}); "
                                "the overall verdict rests on the others."}
    return {
        **lens,
        "verdict": result["verdict"],
        "verdict_text": verdict_label(result["verdict"]),
        "confidence_text": confidence_label(result["confidence"]),
        "confidence_reason": result["confidence_reason"],
        "summary": result["summary"],
        "analysis": result["analysis"],
        "killer_risk": result["killer_risk"],
        "key_assumptions": _assumptions(result["key_assumptions"]),
        "next_steps": result["next_steps"],
        "red_flags": result["out_of_lens_red_flags"],
        "warnings": result.get("warnings", []),
    }


DOWNLOAD_LABELS = {
    "report": f"Save report ({REPORT_FILENAME})",
    "json": f"Save structured data ({JSON_FILENAME})",
}


def _downloads(run: Run) -> list[dict]:
    """
    Each file with its own handling on the page: the report and its translation are
    shown on the page and can be saved; report.json is data for programs, saved only.
    """
    downloads = []
    for kind, path in download_paths(run).items():
        label = DOWNLOAD_LABELS.get(kind) or f"Save translation ({path.name})"
        downloads.append({"kind": kind, "label": label})
    return downloads
