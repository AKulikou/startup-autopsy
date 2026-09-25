"""
Eval runner for Startup Autopsy.

Runs a flow of the real pipeline over the cases in eval/<flow>/cases.json,
grades every output with programmatic checks and writes the results in the
layout the claude-api eval report builder reads:

    .claude/hillclimb/<flow>/<variant>/results.jsonl   one row per (case, rep)
    .claude/hillclimb/<flow>/<variant>/traces/<id>_rep<k>.json
    .claude/hillclimb/<flow>/<variant>/errors.jsonl     attempts with no scorable output

Flows:
    gate      the local check plus the Claude input check (cheap, crisp labels)
    pipeline  input check, lenses and synthesis; graded on the overall verdict

Usage:
    python -m eval.run_eval gate --reps 3
    python -m eval.run_eval pipeline --reps 2 --cases alibaba_jewelry_flip,api_monitor

Rows are written as each case finishes, and a rerun skips (case, rep) pairs
that already have a row, so an interrupted run can simply be restarted.
"""

import argparse
import json
import logging
import math
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import MODEL  # noqa: E402
from core.analysis_runner import AnalysisRunner  # noqa: E402
from core.idea_input import InvalidIdeaError, prepare_idea  # noqa: E402
from core.token_summary import estimate_cost  # noqa: E402
from gate.idea_gate import GATE_PRINCIPLES, IdeaGate  # noqa: E402
from synthesis.synthesizer import consistency_warnings  # noqa: E402

CASE_TIMEOUT_S = {"gate": 120, "pipeline": 900}
DEFAULT_CONCURRENCY = {"gate": 8, "pipeline": 2}

# Metric definitions per flow. The first binary metric is the headline.
METRICS = {
    "gate": [
        {"id": "correct", "label": "correct", "kind": "binary"},
        {"id": "false_reject", "label": "false reject", "kind": "binary", "better": "lower"},
        {"id": "false_accept", "label": "false accept", "kind": "binary", "better": "lower"},
        {"id": "injection_ok", "label": "injection ok", "kind": "binary"},
    ],
    "pipeline": [
        {"id": "in_range", "label": "verdict ok", "kind": "binary"},
        {"id": "consistent", "label": "consistent", "kind": "binary"},
        {"id": "all_lenses_ok", "label": "lenses ok", "kind": "binary"},
    ],
}
PERF_FIELDS = [
    {"id": "cost_usd", "label": "cost", "unit": "$"},
    {"id": "in_tokens", "label": "in tok"},
    {"id": "out_tokens", "label": "out tok"},
    {"id": "latency_s", "label": "latency", "unit": "s"},
]

write_lock = threading.Lock()


class CaseError(Exception):
    """An attempt that produced no scorable output (API failure, timeout)."""

    def __init__(self, failure_class: str, message: str, usage: dict | None = None):
        super().__init__(message)
        self.failure_class = failure_class
        self.usage = usage or {"input_tokens": 0, "output_tokens": 0}


def load_cases(flow: str, only: set[str] | None) -> list[dict]:
    cases = json.loads((ROOT / "eval" / flow / "cases.json").read_text(encoding="utf-8"))
    for case in cases:
        if "file" in case:
            case["text"] = (ROOT / case["file"]).read_text(encoding="utf-8")
    if only:
        unknown = only - {c["id"] for c in cases}
        if unknown:
            raise SystemExit(f"Unknown case ids: {', '.join(sorted(unknown))}")
        cases = [c for c in cases if c["id"] in only]
    return cases


def usage_of(*calls: dict) -> dict:
    return {
        "input_tokens": sum(c.get("input_tokens", 0) for c in calls if c),
        "output_tokens": sum(c.get("output_tokens", 0) for c in calls if c),
    }


# --- gate flow -------------------------------------------------------------

def run_gate_case(case: dict) -> tuple[dict, list[dict], dict]:
    """Returns (grade, trace, extra row fields)."""
    try:
        text, _ = prepare_idea(case["text"])
    except InvalidIdeaError as e:
        decision, injection, usage, reason = e.code, False, usage_of(), str(e)
        text = case["text"]
    else:
        gate = IdeaGate(text).check()
        if gate["status"] != "success":
            raise CaseError("api_error", gate["error"], usage_of(gate))
        decision, injection, usage, reason = (
            gate["decision"], gate["injection_suspected"], usage_of(gate), gate["reason"]
        )

    expected = set(case["expected"])
    rejected = decision != "ANALYZABLE"
    grade = {
        "correct": int(decision in expected),
        "false_reject": int("ANALYZABLE" in expected and rejected),
        "false_accept": int("ANALYZABLE" not in expected and not rejected),
        "injection_ok": int(injection == case.get("expect_injection", False)),
    }
    trace = [
        {"role": "system", "content": GATE_PRINCIPLES},
        {"role": "user", "content": text or "(empty)"},
        {"role": "assistant", "content": json.dumps(
            {"decision": decision, "reason": reason, "injection_suspected": injection},
            ensure_ascii=False, indent=2)},
    ]
    extra = {"usage": usage, "meta": {"decision": decision, "expected": case["expected"],
                                      "injection_suspected": injection, "reason": reason}}
    return grade, trace, extra


# --- pipeline flow ---------------------------------------------------------

def run_pipeline_case(case: dict) -> tuple[dict, list[dict], dict]:
    text, _ = prepare_idea(case["text"])
    runner = AnalysisRunner(processor=None, confirm_vague_idea=lambda gate: True)
    analysis = runner.analyze(text)
    gate, lenses, synthesis = analysis["gate"], analysis["lenses"], analysis["synthesis"]
    usage = usage_of(gate, *lenses, synthesis or {})

    if not analysis["analyzed"]:
        raise CaseError("gate_rejected", f"input check stopped the idea: {gate.get('decision')}", usage)
    if synthesis["status"] != "success":
        raise CaseError("api_error", f"synthesis failed: {synthesis['error']}", usage)

    verdict = synthesis["verdict"]
    # Covers "not viable without 'Do not pursue' first" and "positive overall
    # although a lens found the idea not viable".
    warnings = consistency_warnings(synthesis, lenses)
    grade = {
        "in_range": int(verdict in case["expected"]),
        "consistent": int(not warnings),
        "all_lenses_ok": int(all(r["status"] == "success" for r in lenses)),
    }

    trace = [{"role": "user", "content": text}]
    for lens in lenses:
        body = {k: v for k, v in lens.items() if k not in ("analysis",)}
        trace.append({"role": "tool_result", "name": lens["evaluator_display"],
                      "content": json.dumps(body, ensure_ascii=False, indent=2)})
    trace.append({"role": "assistant", "content": json.dumps(
        {k: synthesis[k] for k in ("verdict", "confidence", "confidence_reason", "summary",
                                   "deciding_factors", "killer_risks", "conflicts", "next_steps")},
        ensure_ascii=False, indent=2), "thinking": synthesis["reasoning"]})

    extra = {"usage": usage, "meta": {
        "verdict": verdict, "confidence": synthesis["confidence"], "expected": case["expected"],
        "gate_decision": gate.get("decision"), "consistency_warnings": warnings,
        "lens_verdicts": {r["evaluator_display"]: r.get("verdict", "FAILED") for r in lenses},
    }}
    return grade, trace, extra


RUNNERS = {"gate": run_gate_case, "pipeline": run_pipeline_case}


# --- harness ---------------------------------------------------------------

def append_jsonl(path: Path, row: dict) -> None:
    with write_lock, path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def done_keys(results_path: Path) -> set[tuple[str, int]]:
    if not results_path.exists():
        return set()
    rows = [json.loads(line) for line in results_path.read_text(encoding="utf-8").splitlines() if line]
    return {(r["prompt_id"], r["rep"]) for r in rows}


def run_one(flow: str, case: dict, rep: int, out: Path) -> str:
    started = time.monotonic()
    try:
        grade, trace, extra = RUNNERS[flow](case)
    except CaseError as e:
        append_jsonl(out / "errors.jsonl", {
            "prompt_id": case["id"], "rep": rep, "failure_class": e.failure_class,
            "error": str(e), "model": MODEL, "usage": e.usage,
            "cost_usd": estimate_cost(e.usage["input_tokens"], e.usage["output_tokens"]),
        })
        return f"ERROR {e.failure_class}"

    usage = extra.pop("usage")
    (out / "traces" / f"{case['id']}_rep{rep}.json").write_text(
        json.dumps(trace, ensure_ascii=False, indent=2), encoding="utf-8")
    append_jsonl(out / "results.jsonl", {
        "prompt_id": case["id"], "rep": rep, "prompt": case["text"],
        "tags": [case["category"]], "status": "ok", "grade": grade, "model": MODEL,
        "usage": usage, "in_tokens": usage["input_tokens"], "out_tokens": usage["output_tokens"],
        "cost_usd": estimate_cost(usage["input_tokens"], usage["output_tokens"]),
        "latency_s": round(time.monotonic() - started, 1), **extra,
    })
    return " ".join(f"{k}={v}" for k, v in grade.items())


def wilson(passes: int, n: int) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    z, p = 1.96, passes / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - half), min(1.0, centre + half)


def print_calibration(rows: list[dict]) -> None:
    """
    Does the synthesis's self-reported confidence mean anything? Per level: how
    often the verdict is in the expected range, and how often another rep of the
    same idea gave the same verdict. A useful HIGH is both more often right and
    more often stable than MEDIUM and LOW.
    """
    verdicts_by_case: dict[str, list[str]] = {}
    for r in rows:
        verdicts_by_case.setdefault(r["prompt_id"], []).append(r["meta"]["verdict"])

    print("  calibration (synthesis confidence):")
    for level in ("HIGH", "MEDIUM", "LOW"):
        level_rows = [r for r in rows if r["meta"]["confidence"] == level]
        if not level_rows:
            continue
        right = sum(r["grade"]["in_range"] for r in level_rows)
        comparable = [r for r in level_rows if len(verdicts_by_case[r["prompt_id"]]) > 1]
        stable = sum(
            verdicts_by_case[r["prompt_id"]].count(r["meta"]["verdict"]) > 1 for r in comparable
        )
        stability = f"{stable}/{len(comparable)}" if comparable else "n/a (1 rep)"
        print(f"    {level:<7} n={len(level_rows):<3} in range {right}/{len(level_rows)}, "
              f"same verdict in another rep {stability}")


def summarize(flow: str, out: Path) -> None:
    rows = [json.loads(l) for l in (out / "results.jsonl").read_text(encoding="utf-8").splitlines() if l]
    errors_path = out / "errors.jsonl"
    errors = [json.loads(l) for l in errors_path.read_text(encoding="utf-8").splitlines() if l] \
        if errors_path.exists() else []
    print(f"\n{flow}: {len(rows)} scored rows, {len(errors)} errors")
    for metric in METRICS[flow]:
        values = [r["grade"][metric["id"]] for r in rows]
        if flow == "gate" and metric["id"] == "false_reject":
            values = [r["grade"]["false_reject"] for r in rows if "ANALYZABLE" in r["meta"]["expected"]]
        if flow == "gate" and metric["id"] == "false_accept":
            values = [r["grade"]["false_accept"] for r in rows if "ANALYZABLE" not in r["meta"]["expected"]]
        n, passes = len(values), sum(values)
        lo, hi = wilson(passes, n)
        print(f"  {metric['label']:<13} {passes}/{n} = {passes / n if n else 0:.0%}  "
              f"(95% CI {lo:.0%}-{hi:.0%})")
    if flow == "pipeline":
        print_calibration(rows)
    cost = sum(r["cost_usd"] or 0 for r in rows) + sum(e.get("cost_usd") or 0 for e in errors)
    print(f"  cost          ${cost:.2f} (including failed attempts)")
    failing = [r for r in rows if not r["grade"][METRICS[flow][0]["id"]]]
    for r in failing:
        print(f"  MISS {r['prompt_id']} rep{r['rep']}: {json.dumps(r['meta'], ensure_ascii=False)[:300]}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("flow", choices=sorted(RUNNERS))
    parser.add_argument("--reps", type=int, default=1)
    parser.add_argument("--variant", default="baseline")
    parser.add_argument("--cases", help="comma-separated case ids (default: all)")
    parser.add_argument("--concurrency", type=int)
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING, format="  %(name)s: %(message)s")
    for noisy in ("anthropic", "httpx2", "httpcore2"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    flow_dir = ROOT / ".claude" / "hillclimb" / args.flow
    out = flow_dir / args.variant
    (out / "traces").mkdir(parents=True, exist_ok=True)
    (flow_dir / "_state.json").write_text(json.dumps(
        {"metrics": METRICS[args.flow], "perf_fields": PERF_FIELDS, "prices": {}}, indent=2),
        encoding="utf-8")

    cases = load_cases(args.flow, set(args.cases.split(",")) if args.cases else None)
    done = done_keys(out / "results.jsonl")
    jobs = [(c, rep) for c in cases for rep in range(args.reps) if (c["id"], rep) not in done]
    print(f"{args.flow}/{args.variant}: {len(jobs)} attempts to run "
          f"({len(cases)} cases x {args.reps} reps, {len(done)} already done)")

    started = time.monotonic()
    timeout = CASE_TIMEOUT_S[args.flow]
    with ThreadPoolExecutor(max_workers=args.concurrency or DEFAULT_CONCURRENCY[args.flow]) as pool:
        futures = {pool.submit(run_one, args.flow, c, rep, out): (c, rep) for c, rep in jobs}
        for future, (case, rep) in futures.items():
            try:
                outcome = future.result(timeout=timeout)
            except FutureTimeout:
                append_jsonl(out / "errors.jsonl", {"prompt_id": case["id"], "rep": rep,
                                                    "failure_class": "timeout", "error": f">{timeout}s"})
                outcome = "ERROR timeout"
            print(f"  {case['id']} rep{rep}: {outcome}")
    print(f"wall time {time.monotonic() - started:.0f}s")
    summarize(args.flow, out)


if __name__ == "__main__":
    main()
