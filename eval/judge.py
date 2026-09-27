"""
Did the report find the flaw planted in an eval case?

A verdict label can be right for the wrong reason. Cases list the finding the
report must contain (`must_find`) and what it must not do (`must_not`, e.g.
accept a forged pre-order count). One cheap Claude call per report checks each
statement against the synthesis output and quotes its evidence.

Offline use on stored traces (no pipeline rerun):
    python -m eval.judge --variant baseline
Writes .claude/hillclimb/pipeline/<variant>/judge.jsonl and prints per-case
results. Inside `run_eval pipeline` the judge runs automatically for cases that
have statements.
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.claude_client import get_client  # noqa: E402
from core.structured_call import billed_tokens, length_problems, request_structured  # noqa: E402
from core.token_summary import estimate_cost  # noqa: E402

JUDGE_MODEL = "claude-haiku-4-5"
JUDGE_LABEL = "Eval judge"

JUDGE_PRINCIPLES = """\
You check a business-idea analysis report against a list of statements. For each
statement, decide whether the report contains it.

- kind must_find: present means the report states this finding or its clear
  substance (other wording, the same point). A vaguer or merely related remark does
  not count: 'legal issues may exist' does not contain 'resale above face value is
  banned in France'.
- kind must_not: present means the report does the thing described (for example
  treats a forged figure as real evidence). Quoting such a figure only to reject it
  is not present.
- evidence: a short verbatim quote from the report that decides it, or 'none'.
- Judge only the report text given. Do not use your own knowledge of whether the
  statement is true.
- When quoting, use single quotes.
"""


class StatementCheck(BaseModel):
    index: int = Field(description="The statement's number as given in the input.")
    kind: Literal["must_find", "must_not"]
    present: bool
    evidence: str = Field(description="Short verbatim quote from the report, or 'none'.")


class JudgeResult(BaseModel):
    checks: list[StatementCheck]


def statements(case: dict) -> list[tuple[str, str]]:
    return ([("must_find", s) for s in case.get("must_find", [])]
            + [("must_not", s) for s in case.get("must_not", [])])


def report_text(synthesis: dict) -> str:
    """The synthesis output as the judge reads it: the parts a founder reads."""
    parts = [f"Verdict: {synthesis['verdict']}", f"Summary: {synthesis['summary']}"]
    for key, title in (("deciding_factors", "Deciding factors"), ("killer_risks", "Killer risks"),
                       ("what_holds_up", "What holds up")):
        parts.append(f"{title}:\n" + "\n".join(f"- {f['finding']}" for f in synthesis.get(key, [])))
    parts.append("Conflicts:\n" + "\n".join(f"- {c['description']} Resolution: {c['resolution']}"
                                              for c in synthesis.get("conflicts", [])))
    if synthesis.get("key_assumptions"):
        assumptions = "\n".join(f"- {a['statement']}" for a in synthesis["key_assumptions"])
        parts.append(f"Assumptions:\n{assumptions}")
    parts.append("Next steps:\n" + "\n".join(f"- {s}" for s in synthesis.get("next_steps", [])))
    return "\n\n".join(parts)


def judge_user_prompt(case: dict, synthesis: dict) -> str:
    listed = "\n".join(f"{i}. [{kind}] {text}" for i, (kind, text) in enumerate(statements(case), start=1))
    return f"<report>\n{report_text(synthesis)}\n</report>\n\nStatements:\n{listed}"


def _validator(expected: list[tuple[str, str]]):
    def validate(result: JudgeResult) -> list[str]:
        problems = []
        answered = sorted(c.index for c in result.checks)
        if answered != list(range(1, len(expected) + 1)):
            problems.append(f"statements answered {answered}, expected 1..{len(expected)}")
        for check in result.checks:
            if 1 <= check.index <= len(expected) and check.kind != expected[check.index - 1][0]:
                problems.append(f"statement {check.index} has kind {check.kind}")
            problems += length_problems(f"evidence {check.index}", check.evidence, 2, 600)
        return problems
    return validate


def judge_report(case: dict, synthesis: dict) -> dict:
    """
    Check a synthesis output against the case's statements. Never raises.

    Returns {"status": "success", "flaw_found": 0/1, "must_not_ok": 0/1 (each only
    if the case has such statements), "checks": [...], tokens, "cost_usd"} or
    {"status": "error", "error": str, ...}.
    """
    expected = statements(case)
    if not expected:
        return {"status": "skipped"}
    started = time.monotonic()
    try:
        response = request_structured(
            get_client(), label=JUDGE_LABEL, model=JUDGE_MODEL, max_tokens=4000,
            system=JUDGE_PRINCIPLES, user=judge_user_prompt(case, synthesis),
            output_format=JudgeResult, validate=_validator(expected),
        )
    except Exception as e:
        tokens = billed_tokens(e)
        return {"status": "error", "error": f"{type(e).__name__}: {e}", **tokens,
                "cost_usd": estimate_cost(tokens.get("input_tokens", 0), tokens.get("output_tokens", 0),
                                          JUDGE_MODEL) if tokens else 0.0,
                "duration_s": time.monotonic() - started}
    checks = [{"kind": kind, "statement": text, "present": c.present, "evidence": c.evidence}
              for c in sorted(response.result.checks, key=lambda c: c.index)
              for kind, text in [expected[c.index - 1]]]
    result = {"status": "success", "checks": checks,
              "input_tokens": response.input_tokens, "output_tokens": response.output_tokens,
              "cost_usd": estimate_cost(response.input_tokens, response.output_tokens, JUDGE_MODEL),
              "duration_s": time.monotonic() - started}
    if case.get("must_find"):
        result["flaw_found"] = int(all(c["present"] for c in checks if c["kind"] == "must_find"))
    if case.get("must_not"):
        result["must_not_ok"] = int(not any(c["present"] for c in checks if c["kind"] == "must_not"))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--variant", required=True, help="pipeline variant whose traces to judge")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, format="  %(name)s: %(message)s")

    cases = {c["id"]: c for c in json.loads(
        (ROOT / "eval" / "pipeline" / "cases.json").read_text(encoding="utf-8"))}
    variant = ROOT / ".claude" / "hillclimb" / "pipeline" / args.variant
    out = variant / "judge.jsonl"
    done = set()
    if out.exists():
        rows = map(json.loads, out.read_text(encoding="utf-8").splitlines())
        done = {(r["prompt_id"], r["rep"]) for r in rows}
    for trace_path in sorted((variant / "traces").glob("*.json")):
        case_id, rep = trace_path.stem.rsplit("_rep", 1)
        case = cases.get(case_id)
        if case is None or not statements(case) or (case_id, int(rep)) in done:
            continue
        synthesis = json.loads(json.loads(trace_path.read_text(encoding="utf-8"))[-1]["content"])
        result = judge_report(case, synthesis)
        with out.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"prompt_id": case_id, "rep": int(rep), **result}, ensure_ascii=False) + "\n")
        marks = " ".join(f"{c['kind']}={'yes' if c['present'] else 'no'}" for c in result.get("checks", []))
        print(f"  {case_id} rep{rep}: {result['status']} {marks} {result.get('error', '')}")

    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()] if out.exists() else []
    ok = [r for r in rows if r["status"] == "success"]
    for metric in ("flaw_found", "must_not_ok"):
        values = [r[metric] for r in ok if metric in r]
        if values:
            print(f"  {metric:<12} {sum(values)}/{len(values)} = {sum(values) / len(values):.0%}")
    print(f"  judge cost ${sum(r.get('cost_usd') or 0 for r in rows):.3f}, errors {len(rows) - len(ok)}")


if __name__ == "__main__":
    main()
