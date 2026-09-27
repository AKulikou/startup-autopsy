"""
Replay the synthesis on the exact lens results of earlier pipeline runs.

The lens results are held fixed, so any change in the overall verdict between
replays comes from the synthesis alone. Comparing that with the variation of
full pipeline runs splits verdict instability between the lenses and the
synthesis (experiment A of the 2026-09-27 review).

Usage:
    python -m eval.replay_synthesis --source expA_lenses --reps 4 --batch
    python -m eval.replay_synthesis --source expA_lenses --cases api_monitor --reps 2
    python -m eval.replay_synthesis --source expA_lenses --summary-only

Input: .claude/hillclimb/pipeline/<source>/traces/*.json, written by run_eval
after lens results were first kept in full (older traces lack the analysis text
the synthesis reads and are refused).
Output: .claude/hillclimb/synthesis_replay/<source>/results.jsonl, one row per
replay; rep "original" rows record the verdict of the source run itself.
"""

import argparse
import json
import logging
import sys
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.claude_client import use_batches  # noqa: E402
from core.token_summary import estimate_cost  # noqa: E402
from eval.grading import stability  # noqa: E402
from synthesis.synthesizer import Synthesizer  # noqa: E402

PIPELINE_DIR = ROOT / ".claude" / "hillclimb" / "pipeline"
REPLAY_DIR = ROOT / ".claude" / "hillclimb" / "synthesis_replay"
write_lock = threading.Lock()


class TraceError(ValueError):
    """A trace that cannot be replayed faithfully."""


def load_inputs(trace: list[dict]) -> dict:
    """The synthesis inputs stored in a pipeline trace, and the source run's own output."""
    user = trace[0]
    lenses = [json.loads(m["content"]) for m in trace if m["role"] == "tool_result"]
    missing = [r["evaluator_display"] for r in lenses if r["status"] == "success" and "analysis" not in r]
    if missing:
        raise TraceError(f"lens results without analysis text ({', '.join(missing)}): "
                         "the trace predates full lens results")
    original = json.loads(trace[-1]["content"])
    return {"idea": user["content"], "input_note": user.get("input_note"), "lenses": lenses,
            "original_verdict": original["verdict"], "original_confidence": original["confidence"]}


def replay_row(case_id: str, rep: int, inputs: dict, expected: list[str]) -> dict:
    synthesis = Synthesizer(inputs["idea"], inputs["lenses"], inputs["input_note"]).synthesize()
    row = {"prompt_id": case_id, "rep": rep, "status": synthesis["status"]}
    row["cost_usd"] = estimate_cost(synthesis.get("input_tokens", 0), synthesis.get("output_tokens", 0))
    if synthesis["status"] != "success":
        row["error"] = synthesis["error"]
        return row
    row["grade"] = {"in_range": int(synthesis["verdict"] in expected)}
    row["meta"] = {"verdict": synthesis["verdict"], "confidence": synthesis["confidence"],
                   "expected": expected, "summary": synthesis["summary"]}
    return row


def read_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def summarize(rows: list[dict]) -> None:
    ok = [r for r in rows if r["status"] == "success" and r["rep"] != "original"]
    originals = {r["prompt_id"]: r["meta"]["verdict"] for r in rows if r["rep"] == "original"}
    print(f"\nsynthesis replay: {len(ok)} replays, {sum(r['status'] != 'success' for r in rows)} errors")
    by_case: dict[str, list[str]] = {}
    for r in ok:
        by_case.setdefault(r["prompt_id"], []).append(r["meta"]["verdict"])
    for case_id, verdicts in sorted(by_case.items()):
        counts = ", ".join(f"{v} x{n}" for v, n in Counter(verdicts).most_common())
        print(f"  {case_id:<30} source run: {originals.get(case_id, '?'):<17} replays: {counts}")
    # The source run's verdict is one more synthesis on the same inputs.
    with_original = ok + [r for r in rows if r["rep"] == "original"]
    stab = stability(with_original)
    print(f"  synthesis alone, lens results fixed ({stab['cases']} cases, {stab['attempts']} syntheses):")
    print(f"    modal agreement   {stab['modal_agreement']:.0%}")
    print(f"    verdict changed   {len(stab['changed_cases'])}/{stab['cases']} cases: "
          f"{', '.join(stab['changed_cases']) or '-'}")
    print(f"    cross-side flips  {len(stab['cross_side_cases'])}/{stab['cases']}")
    print(f"    pair disagreement {stab['pairwise_disagreement']:.2f} (share of pairs of runs "
          "with different verdicts)")
    print(f"    ordinal spread    {stab['mean_ordinal_spread']:.2f}")
    print(f"  cost ${sum(r['cost_usd'] or 0 for r in rows):.2f}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--source", required=True, help="pipeline variant whose traces to replay")
    parser.add_argument("--cases", help="comma-separated case ids (default: all traces of the source)")
    parser.add_argument("--reps", type=int, default=4)
    parser.add_argument("--batch", action="store_true", help="send the syntheses as Message Batches")
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, format="  %(name)s: %(message)s")

    out = REPLAY_DIR / args.source
    out.mkdir(parents=True, exist_ok=True)
    results = out / "results.jsonl"
    if args.summary_only:
        summarize(read_rows(results))
        return

    case_file = ROOT / "eval" / "pipeline" / "cases.json"
    cases = {c["id"]: c for c in json.loads(case_file.read_text(encoding="utf-8"))}
    wanted = set(args.cases.split(",")) if args.cases else None
    jobs, done = [], {(r["prompt_id"], r["rep"]) for r in read_rows(results)}
    for trace_path in sorted((PIPELINE_DIR / args.source / "traces").glob("*.json")):
        case_id = trace_path.stem.rsplit("_rep", 1)[0]
        if wanted and case_id not in wanted:
            continue
        inputs = load_inputs(json.loads(trace_path.read_text(encoding="utf-8")))
        expected = cases[case_id]["expected"]
        if (case_id, "original") not in done:
            with results.open("a", encoding="utf-8") as f:
                original = {
                    "prompt_id": case_id, "rep": "original", "status": "success", "cost_usd": 0,
                    "grade": {"in_range": int(inputs["original_verdict"] in expected)},
                    "meta": {"verdict": inputs["original_verdict"],
                             "confidence": inputs["original_confidence"], "expected": expected},
                }
                f.write(json.dumps(original, ensure_ascii=False) + "\n")
        jobs += [(case_id, rep, inputs, expected) for rep in range(args.reps) if (case_id, rep) not in done]

    print(f"{len(jobs)} syntheses to run from {args.source}")
    if args.batch:
        use_batches()
    with ThreadPoolExecutor(max_workers=max(len(jobs), 1) if args.batch else 4) as pool:
        for row in pool.map(lambda job: replay_row(*job), jobs):
            with write_lock, results.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            outcome = row.get("meta", {}).get("verdict", row.get("error"))
            print(f"  {row['prompt_id']} rep{row['rep']}: {outcome}")
    summarize(read_rows(results))


if __name__ == "__main__":
    main()
