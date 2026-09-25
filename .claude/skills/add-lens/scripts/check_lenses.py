"""
Check that the lens definitions, the configuration and the docs agree.

Usage (from the project root):
    python .claude/skills/add-lens/scripts/check_lenses.py

Prints every lens with its enabled status and question, then any mismatch:
duplicate keys or names, enabled keys that do not exist, and lenses missing
from (or with the wrong status in) the lens tables of README.md, CLAUDE.md and
docs/prompt_framework.md. Exits with status 1 if anything is out of sync.
"""

import os
import re
import sys
from pathlib import Path

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-check-only")  # config.py demands a key

from config import ENABLED_LENSES  # noqa: E402
from evaluators.lenses import LENSES  # noqa: E402


def table_row(doc: str, pattern: str) -> str | None:
    match = re.search(pattern, doc, re.M)
    return match.group(0) if match else None


def main() -> None:
    problems = []
    keys = [lens.key for lens in LENSES]
    names = [lens.name for lens in LENSES]
    for label, values in (("key", keys), ("name", names)):
        duplicates = {v for v in values if values.count(v) > 1}
        if duplicates:
            problems.append(f"duplicate lens {label}(s): {', '.join(sorted(duplicates))}")
    unknown = [key for key in ENABLED_LENSES if key not in keys]
    if unknown:
        problems.append(f"ENABLED_LENSES has unknown key(s): {', '.join(unknown)}")

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    claude_md = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    framework = (ROOT / "docs" / "prompt_framework.md").read_text(encoding="utf-8")

    print("| Lens | Key | Enabled | Question |\n|---|---|---|---|")
    for lens in LENSES:
        enabled = lens.key in ENABLED_LENSES
        print(f"| {lens.name} | `{lens.key}` | {'yes' if enabled else ''} | {lens.focus} |")
        name = re.escape(lens.name)

        row = table_row(readme, rf"^\| {name} \|.*\|$")
        if row is None:
            problems.append(f"README.md lens table has no row for {lens.name}")
        elif row.rstrip("| ").endswith("yes") != enabled:
            problems.append(f"README.md shows the wrong 'Enabled by default' value for {lens.name}")

        row = table_row(claude_md, rf"^\| \d+ \| {name} \|.*\|$")
        if row is None:
            problems.append(f"CLAUDE.md lens table has no row for {lens.name}")
        elif ("| enabled |" in row) != enabled:
            problems.append(f"CLAUDE.md shows the wrong status for {lens.name}")

        if table_row(framework, rf"^\| \d+ \| {name} \| `{re.escape(lens.key)}` \|.*\|$") is None:
            problems.append(f"docs/prompt_framework.md lens table has no row for {lens.name} (`{lens.key}`)")

    print()
    if problems:
        print("Out of sync:")
        for problem in problems:
            print(f"- {problem}")
        sys.exit(1)
    print(f"All {len(LENSES)} lenses agree with config and docs ({len(ENABLED_LENSES)} enabled).")


if __name__ == "__main__":
    main()
