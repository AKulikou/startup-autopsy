"""
Mechanical checks of one Startup Autopsy run, printed as Markdown.

Usage (from the project root):
    python .claude/skills/review-run/scripts/review_run.py            # latest run
    python .claude/skills/review-run/scripts/review_run.py results/<run-dir>

Checks what code can check reliably; judgment (does a verdict match its
reasoning, do numbers conflict) is left to the reader of this output:
- the run log: malformed answers and retries, failed calls, rate limits,
  code consistency warnings, per-call time and cost, totals
- report.md: overall verdict, confidence, lens verdicts
- attribution: for every finding the synthesis attributes to lenses, whether
  its key terms appear in each cited lens report (catches "Temu risk
  attributed to a lens that never mentioned Temu")
"""

import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path.cwd()
RUN_DIR_TIME = "%Y-%m-%d_%H-%M-%S"
# Capitalised words too common to identify a claim.
STOP_TERMS = {
    "The", "This", "That", "These", "Those", "There", "Their", "They", "Even", "With", "Without",
    "When", "While", "Where", "Which", "What", "Only", "Most", "Many", "Every", "Each", "Both",
    "Month", "Year", "Week", "EUR", "USD", "And", "But", "For", "Not", "All", "Any", "Its",
    "Lens", "Lenses", "Profitable", "App", "Designer", "Stack", "Master", "Launch", "Expert",
    "Churn", "Eliminator", "Viral", "Product", "Reality", "Auditor", "No-Code",
}
FINDING = re.compile(r"^- (?P<text>.+?) \*\((?P<lenses>[^)]+)\)\*\s*$")
TERM = re.compile(r"\b[A-Z][A-Za-z0-9&\-]{2,}\b|\b\d[\d,.]*\d%?\b")


def latest_run() -> Path:
    runs = sorted(p for p in (ROOT / "results").iterdir() if (p / "report.md").exists())
    if not runs:
        sys.exit("No run with a report.md under results/")
    return runs[-1]


def log_for(run_dir: Path) -> Path | None:
    """The CLI log starts a few seconds before the run directory's timestamp."""
    started = datetime.strptime(run_dir.name[:19], RUN_DIR_TIME)
    candidates = []
    for log in (ROOT / "logs").glob("startup_autopsy_*.log"):
        log_time = datetime.strptime(log.stem.removeprefix("startup_autopsy_"), RUN_DIR_TIME)
        if 0 <= (started - log_time).total_seconds() <= 600:
            candidates.append((started - log_time, log))
    return min(candidates)[1] if candidates else None


def section(report: str, heading: str) -> str:
    match = re.search(rf"^## {re.escape(heading)}.*?$(.*?)(?=^## |\Z)", report, re.M | re.S)
    return match.group(1).strip() if match else ""


def check_log(log: Path) -> None:
    lines = log.read_text(encoding="utf-8").splitlines()
    info = [line for line in lines if " INFO " in line or " WARNING " in line or " ERROR " in line]
    print(f"## Log: {log.name}\n")
    for label, pattern in [
        ("Malformed answers (retried or failed)", "invalid result"),
        ("Failed calls", "FAILED"),
        ("Rate limits (429)", " 429"),
        ("Code consistency warnings", "Synthesis: overall verdict"),
    ]:
        hits = [line for line in lines if pattern in line]
        print(f"- **{label}:** {len(hits)}")
        for hit in hits[:5]:
            print(f"  - `{hit.split(': ', 1)[-1][:180]}`")
    print("\nProgress lines:\n")
    for line in info:
        message = line.split(": ", 1)[-1]
        if any(key in message for key in ("done in", "FAILED", "Lenses finished", "Tokens:", "Translation")):
            print(f"- `{line[11:19]}` {message[:200]}")
    if len(lines) > 1:
        start, end = lines[0][:19], next(line for line in reversed(lines) if line[:4].isdigit())[:19]
        seconds = (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds()
        print(f"\n- **Wall time:** {seconds:.0f}s (log start to last entry)")
    print()


def check_attribution(run_dir: Path, report: str) -> None:
    print("## Attribution of findings to lenses\n")
    print("Key terms of each finding, looked up in each cited lens report. "
          "Low coverage means: open the lens report and check the claim is really there.\n")
    lens_text = {p.stem: p.read_text(encoding="utf-8").lower() for p in (run_dir / "lenses").glob("*.md")
                 if p.stem.count(".") == 0}
    suspicious = 0
    for heading in ("Why: Deciding Factors", "What Could Kill This Project"):
        for line in section(report, heading).splitlines():
            match = FINDING.match(line.strip())
            if not match:
                continue
            first_word = match["text"].split()[0]
            terms = sorted(
                {t for t in TERM.findall(match["text"]) if t not in STOP_TERMS and t != first_word}
            )
            if not terms:
                continue
            for lens in (name.strip() for name in match["lenses"].split(",")):
                key = re.sub(r"_+", "_", re.sub(r"[^\w\s]", " ", lens).lower().strip().replace(" ", "_"))
                text = lens_text.get(key)
                if text is None:
                    print(f"- ⚠ cited lens **{lens}** has no report in this run")
                    suspicious += 1
                    continue
                missing = [t for t in terms if t.lower() not in text]
                # Two or more missing terms, and most of them: one stray word is noise.
                if len(missing) >= 2 and len(missing) > len(terms) / 2:
                    suspicious += 1
                    print(f"- ⚠ **{lens}** is cited for: _{match['text'][:140]}…_ "
                          f"but its report lacks: {', '.join(missing[:8])}")
    if not suspicious:
        print("- No citation with low term coverage.")
    print()


def main() -> None:
    run_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else latest_run()
    report = (run_dir / "report.md").read_text(encoding="utf-8")
    print(f"# Review: {run_dir.name}\n")

    verdict = re.search(r"^## Verdict: (.+)$", report, re.M)
    confidence = re.search(r"^\*\*Confidence:\*\* (.+)$", report, re.M)
    note = re.search(r"^> \*\*Input check:\*\* (.+)$", report, re.M)
    print(f"- **Overall verdict:** {verdict[1] if verdict else 'NONE (synthesis failed?)'}")
    print(f"- **Confidence:** {confidence[1][:220] if confidence else '-'}")
    if note:
        print(f"- **Input check note:** {note[1][:220]}")
    conflicts = [line for line in section(report, "Conflicts").splitlines() if line.startswith("- ")]
    print(f"- **Conflicts listed:** {len(conflicts)}")
    print("\n**Lens verdicts** (from the appendix):\n")
    for row in section(report, "Appendix: Lens Results").splitlines():
        cells = [c.strip() for c in row.strip("|").split("|")]
        if len(cells) >= 3 and cells[0].startswith("["):
            print(f"- {cells[0].split(']')[0][1:]}: {cells[1]} ({cells[2]})")
    print()

    log = log_for(run_dir)
    if log:
        check_log(log)
    else:
        print("## Log\n\n- No matching CLI log (run via MCP or the eval runner?).\n")
    check_attribution(run_dir, report)


if __name__ == "__main__":
    main()
