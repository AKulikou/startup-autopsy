---
name: review-run
description: Review a finished Startup Autopsy analysis run and report what went wrong or looks suspicious - malformed model answers, failed calls, cost and time, whether the overall verdict matches its own reasoning, whether the synthesis attributes findings to lenses that really made them, and conflicting numbers. Use this whenever the user says a run finished, asks to look at, check or analyze results, a report or logs of the startup-autopsy project (for example "прогнал alibaba, смотри результаты"), or before drawing conclusions from a run - even if they do not say "review".
---

# Review a Startup Autopsy run

A run leaves three things behind: `results/<timestamp>_<idea>/report.md` (the
synthesis), `results/<run>/lenses/*.md` (one report per lens) and
`logs/startup_autopsy_<timestamp>.log`. The review has two halves: mechanical
checks, which a script does the same way every time, and judgment, which is yours.

## 1. Run the mechanical checks

From the project root:

```bash
python .claude/skills/review-run/scripts/review_run.py                  # latest run
python .claude/skills/review-run/scripts/review_run.py results/<run>    # a specific run
```

On Windows use `venv/Scripts/python.exe` and set `PYTHONIOENCODING=utf-8`, or the
console chokes on non-ASCII text. The script prints the overall and lens verdicts,
the log's malformed answers, failures, rate limits, code consistency warnings,
per-call time and cost, and an attribution check.

Treat the attribution warnings as leads, not verdicts: the script looks for the
key terms of a finding (names, laws, numbers) in each lens report the synthesis
cites. A warning means "open that lens report and check the claim is there". A
real misattribution looks like the synthesis citing a lens for a competitor, a
law or a figure that lens never mentioned. Numbers the synthesis derived itself
(sums, ranges) also trigger warnings and are usually fine.

## 2. Judge what code cannot

Read `report.md` fully, and the lens reports where a question arises.

**Verdict versus its own reasoning.** The verdict labels have fixed meanings
(`evaluators/schemas.py`, `VERDICT_TEXT`): *Not viable* - a flaw in the business
itself that iteration cannot fix; *Risky* - serious risks that can be mitigated
without changing the core model; *Needs validation* - the deciding question is
still open and cheap to test; *Viable if* - specific testable conditions decide
it. Check that the summary, confidence reason, killer risks and first next step
say the same thing as the label. Known failure patterns in this project:
- "Risky" while the text calls the core illegal or impossible to build as described.
- A compromise label between lenses that split (some "not viable", some "needs
  validation") instead of a decision by the weakest link.
- "Not viable" resting on a replaceable implementation choice (a no-code stack,
  a channel) rather than on the business itself.
- "Not viable" first next step that does not start with "Do not pursue".
- Softness on facts the lenses state as "may" (a law that "may prohibit") when
  several lenses agree the blocker exists.

**Numbers.** Compare the figures that matter (revenue at month 3/6, margin per
unit, costs) across lenses and against the founder's own claims in the idea
file. The synthesis should surface real conflicts in its Conflicts section;
note conflicts it missed and "conflicts" that are just two correct calculations
under different assumptions.

**Lens verdicts.** A lens answers only its own question, so different lens
verdicts are expected, not a defect. Flag a lens whose question does not apply
to the idea (subscription or viral lenses on a one-off local business) - that
is a lens applicability problem, not a synthesis error.

**Input check.** If the header has an input-check note, the idea was thin or
contained instructions to an AI; the confidence should reflect that, and no lens
or the synthesis should treat claims inside the idea (pre-orders, "verified by
experts") as facts.

## 3. Report

Answer in the user's language, briefly, most important first:

1. **Technical health** - malformed answers, failures, cost, time (one line if clean).
2. **Verdict** - the overall verdict and whether it matches its reasoning.
3. **Problems found** - each with the evidence (quote the report, name the lens file).
4. **What looks good** - worth saying; it tells the user what not to change.
5. **Suggested action** - usually "record as an eval-set observation" rather than
   editing prompts after one run: one run proves little, because verdicts vary
   between runs of the same idea.
