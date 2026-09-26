"""
Trigger test for the user skill skills/startup-autopsy: how often does Claude
Code invoke it for prompts that should (and should not) use it?

Each query in eval/trigger/queries.json runs through `claude -p` several times
from a fresh folder where the skill is installed as a project skill, the way a
user would have it. A run counts as triggered when Claude's first tool call is
the skill or one of the Startup Autopsy MCP tools. Runs stop at that first tool
call, so no paid analysis starts; they use the Claude Code login, not the
project's API key.

Models and effort levels change over time, so both are parameters: measure a
description change on at least the default and the low effort level, and
accept it only if it is no worse on each.

Usage:
    python -m eval.trigger.run_trigger --effort low
    python -m eval.trigger.run_trigger --skill path/to/SKILL.md --model claude-sonnet-5 --runs 3

About 15 minutes for 24 queries x 3 runs with 6 workers.
"""

import argparse
import json
import os
import shutil
import subprocess
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SKILL_NAME = "startup-autopsy"
DEFAULT_SKILL = ROOT / "skills" / SKILL_NAME / "SKILL.md"
QUERIES = Path(__file__).with_name("queries.json")
RESULTS_DIR = ROOT / ".claude" / "hillclimb" / "trigger"
MAX_DESCRIPTION_CHARS = 1024


def check_frontmatter(skill_md: Path) -> str:
    """Return the description, or raise if the frontmatter would not load.

    A broken frontmatter (for example an unquoted ': ' in the description)
    leaves Claude with a skill that has no usable description, so every
    measurement on it is meaningless.
    """
    parts = skill_md.read_text(encoding="utf-8").split("---", 2)
    if len(parts) < 3:
        raise ValueError(f"{skill_md}: no YAML frontmatter")
    meta = yaml.safe_load(parts[1])
    description = meta.get("description") if isinstance(meta, dict) else None
    if meta.get("name") != SKILL_NAME or not isinstance(description, str):
        raise ValueError(f"{skill_md}: frontmatter needs name '{SKILL_NAME}' and a description")
    if len(description) > MAX_DESCRIPTION_CHARS:
        raise ValueError(
            f"{skill_md}: description is {len(description)} chars, limit {MAX_DESCRIPTION_CHARS}"
        )
    return description


def one_run(workdir: Path, query: str, model: str | None, effort: str | None, timeout: int) -> bool | None:
    """True if the first tool call uses the skill, False otherwise, None if the run failed."""
    cmd = ["claude", "-p", query, "--output-format", "stream-json", "--verbose"]
    if model:
        cmd += ["--model", model]
    if effort:
        cmd += ["--effort", effort]
    # CLAUDECODE is cleared so the test also runs from inside a Claude Code session.
    env = {**os.environ, "CLAUDECODE": ""}
    proc = subprocess.Popen(cmd, cwd=workdir, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env)
    # Reading lines and killing on a timer works on Windows, where select() on pipes does not.
    timer = threading.Timer(timeout, proc.kill)
    timer.start()
    try:
        for raw in proc.stdout:
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "assistant":
                for item in event["message"].get("content", []):
                    if item.get("type") == "tool_use":
                        called = item.get("name", "") + json.dumps(item.get("input", {}))
                        return SKILL_NAME in called
            elif event.get("type") == "result":
                # An error result (usage limit, API error) is a failed run, not a miss:
                # counting it as 'not triggered' once turned a hit limit into fake misses.
                if event.get("is_error") or event.get("subtype") != "success":
                    return None
                return False
        return None
    finally:
        timer.cancel()
        proc.kill()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--skill", type=Path, default=DEFAULT_SKILL, help="SKILL.md to test")
    parser.add_argument("--queries", type=Path, default=QUERIES)
    parser.add_argument("--model", default=None, help="model for claude -p (default: the CLI default)")
    parser.add_argument("--effort", default=None, choices=["low", "medium", "high", "xhigh", "max"])
    parser.add_argument("--runs", type=int, default=3, help="runs per query")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--timeout", type=int, default=90, help="seconds per run")
    args = parser.parse_args()

    check_frontmatter(args.skill)
    queries = json.loads(args.queries.read_text(encoding="utf-8"))

    workdir = Path(tempfile.mkdtemp(prefix="trigger_"))
    try:
        skill_dir = workdir / ".claude" / "skills" / SKILL_NAME
        skill_dir.mkdir(parents=True)
        shutil.copy(args.skill, skill_dir / "SKILL.md")
        jobs = [(i, r) for i in range(len(queries)) for r in range(args.runs)]
        with ThreadPoolExecutor(args.workers) as pool:
            outcomes = list(pool.map(
                lambda job: one_run(workdir, queries[job[0]]["query"], args.model, args.effort, args.timeout),
                jobs,
            ))
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    rows = []
    for i, query in enumerate(queries):
        got = [outcome for (j, _), outcome in zip(jobs, outcomes, strict=True) if j == i]
        hits = sum(o is True for o in got)
        ok = (hits / args.runs >= 0.5) == query["should_trigger"]
        rows.append({**query, "hits": hits, "failed_runs": sum(o is None for o in got), "ok": ok})
        print(f"{'PASS' if ok else 'FAIL'} {hits}/{args.runs} failed={rows[-1]['failed_runs']} "
              f"want={'yes' if query['should_trigger'] else 'no '} {query['query'][:70]}")

    positives = [r for r in rows if r["should_trigger"]]
    negatives = [r for r in rows if not r["should_trigger"]]
    summary = {
        "skill": str(args.skill), "model": args.model or "default", "effort": args.effort or "default",
        "runs": args.runs,
        "triggered_when_wanted": f"{sum(r['ok'] for r in positives)}/{len(positives)}",
        "quiet_when_not_wanted": f"{sum(r['ok'] for r in negatives)}/{len(negatives)}",
    }
    failed = sum(r["failed_runs"] for r in rows)
    summary["failed_runs"] = failed
    print(json.dumps(summary))
    if failed:
        print(f"WARNING: {failed} of {len(jobs)} runs failed (usage limit or API error); "
              "rerun before trusting these numbers.")
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / f"{datetime.now():%Y-%m-%d_%H-%M-%S}_{summary['model']}_{summary['effort']}.json"
    report = {"summary": summary, "rows": rows}
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Saved {out}")


if __name__ == "__main__":
    main()
