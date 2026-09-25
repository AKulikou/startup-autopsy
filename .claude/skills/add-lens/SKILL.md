---
name: add-lens
description: Add, enable, disable, rename or rewrite an analytical lens (evaluator) in the Startup Autopsy project - defining it in evaluators/lenses.py, checking it does not overlap existing lenses, keeping config and the three lens tables in the docs in sync, and verifying the change. Use this whenever the user wants a new perspective or expert in the analysis (a legal, AI, software-architecture or other domain lens), wants to switch lenses on or off, or asks to change what a lens asks - even if they call it an evaluator, expert or analyst rather than a lens.
---

# Add or change a lens

A lens is one independent perspective on a business idea: a role, a focus
question and a few lens-specific questions, defined as data in
`evaluators/lenses.py`. Every enabled lens runs in parallel; the synthesis
reads them all and alone decides the overall verdict. Read
`docs/prompt_framework.md` before designing a lens - it holds the rules below
in full.

## Design the lens before writing it

**One question, not overlapping others.** The focus is the single question
this lens answers. List the current lenses first:

```bash
python .claude/skills/add-lens/scripts/check_lenses.py
```

and compare the new focus with each existing one. Two lenses covering the same
ground (for example pricing tiers and monthly revenue) look to the synthesis
like independent agreement when they are one view counted twice. If the new
lens overlaps, narrow it, merge it into the existing lens, or say so to the user.

**Its own question, not the whole idea.** A lens verdict answers only the lens's
question; problems outside it go into `out_of_lens_red_flags`, and the overall
verdict belongs to the synthesis. Do not write a focus like "is this worth
pursuing at all?": a lens that judges the whole idea becomes a second judge,
and in this project the synthesis then followed that lens's verdict in every
run (this is why the Reality Auditor was narrowed).

**Applies to most ideas, or is marked as domain-specific.** A lens whose
question does not fit an idea produces confident noise (subscription and viral
lenses called a local cookie business "not viable"). A domain lens (legal, AI,
software architecture, construction) should only run where it applies; until
the input check selects lenses per idea, leave such a lens defined but not
enabled, and tell the user.

**Questions ask, they do not format.** Three to five lens-specific questions.
The output format, verdict scale, confidence and red flags come from the shared
schema - do not repeat them in the lens. Keep the tone requirements in
`ANALYSIS_STANDARDS`, which every lens shares.

## Make the change

1. Add or edit the `Lens(...)` entry in `evaluators/lenses.py`: a stable
   snake_case `key` (used in config, file names and eval data - do not rename
   an existing key casually), a display `name`, a `role`, the `focus` and the
   `questions`.
2. To enable it, add the key to `ENABLED_LENSES` in `config.py`. Order is the
   order the synthesis reads the lenses in.
3. Update the three lens tables: `README.md` (Lenses: name, question, enabled
   by default), `CLAUDE.md` (Evaluator framework: number, name, short lens
   description, `enabled` or `defined`) and `docs/prompt_framework.md` (The
   lenses: number, name, key, question).
4. Run `check_lenses.py` again until it reports everything in sync, then
   `pytest` and `ruff check .`.

## Verify with real runs

A new or rewritten lens changes model behavior, so unit tests cannot show
whether it helps. Say what verification would cost before running anything
paid: a single run is about 0.40 USD; the pipeline eval
(`python -m eval.run_eval pipeline --reps 2 --variant v1`) is about 14 USD and
compares against the baseline. For a first look, suggest one or two runs on
ideas where the lens should matter and one where it should not, and review them
with the review-run skill. Do not tune the lens wording to one run: verdicts
vary between runs of the same idea.
