# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project

**Startup Autopsy** evaluates business ideas from several independent analytical
perspectives and produces a structured, brutally honest report: viability verdict,
confidence, hidden assumptions, killer risks, and concrete next steps (including
"don't pursue this").

Target architecture: an **MCP server** that runs each evaluator as a separate
agent/tool call in parallel and synthesizes the results. Current state is a local
CLI (`main.py`) calling the Anthropic API directly.

## Commands

```bash
python -m venv venv && venv\Scripts\activate   # Windows
pip install -r requirements-dev.txt            # app + pytest
python main.py                                 # interactive: pick an idea from ideas/
pytest                                         # unit tests, fake Claude client, no API calls
python -m eval.run_eval gate --reps 3          # eval: input check (~$0.25)
python -m eval.run_eval pipeline --reps 2      # eval: whole pipeline (~$14, paid)
```

Requires `ANTHROPIC_API_KEY` in `.env` (never commit it). Run `pytest` after any
change; run the eval after any change to prompts, lenses or the model.

## Layout

- `main.py` — CLI entry point, logging setup, idea selection
- `config.py` — API key check, model, token limit, enabled lenses
- `evaluators/lenses.py` — all lenses as data (role, focus, questions) + shared `ANALYSIS_STANDARDS`
- `evaluators/evaluator.py` — `Evaluator`: builds prompts from a lens, calls Claude with structured output
- `evaluators/schemas.py` — `EvaluatorResult` Pydantic schema (verdict, confidence, assumptions, killer risk, next steps)
- `synthesis/synthesizer.py` — `Synthesizer`: one Claude call that reads all lens results and decides the overall verdict (`SYNTHESIS_PRINCIPLES`); `synthesis/schemas.py` — `SynthesisResult`
- `core/structured_call.py` — shared structured request: stop-reason checks, result validation, one retry
- `gate/idea_gate.py` — `IdeaGate`: one Claude call that decides NOT_AN_IDEA / TOO_VAGUE / ANALYZABLE before the lenses run (`gate/schemas.py` — `GateResult`)
- `core/idea_input.py` — local checks before any API call (empty or letterless input is rejected; straight double quotes become typographic)
- `core/analysis_runner.py` — orchestrates load → lenses → synthesis → reports → token stats
- `core/translator.py` — optional translated copies of finished reports (`REPORT_TRANSLATION` in `.env`); the analysis stays English
- `core/report_builder.py` — builds `report.md` (synthesis first, lens results as appendix)
- `core/idea_processor.py`, `file_manager.py`, `result_writer.py` — idea I/O and Markdown output
- `ideas/` — input ideas (`.txt`); `results/`, `logs/` — generated, git-ignored

## Evaluator framework

Full specification: [docs/prompt_framework.md](docs/prompt_framework.md) — read it
before adding or changing an evaluator or the synthesis.

Each prompt is a distinct lens (lenses must not overlap):

| # | Evaluator | Lens | Status |
|---|-----------|------|--------|
| 1 | Profitable App Designer | Revenue model, recurring revenue, assumptions behind numbers | enabled |
| 2 | No-Code Stack Master | 7-day no-code MVP, concrete stack, day-7 scope | enabled |
| 3 | AI Tool Creator | AI differentiation, pricing rationale, first 10 customers | defined |
| 4 | SaaS Revenue Builder | Pricing tiers, churn, 3/6/12-month optimistic vs conservative | defined |
| 5 | Viral Product Designer | Network effects, conditions for organic growth | enabled |
| 6 | Launch Expert | First-week traction grounded in real audience size | enabled |
| 7 | Churn Eliminator | Onboarding, habit loops, when retention tactics fail | enabled |
| 8 | Reality Auditor | Killer risk, true timeline, go/no-go criteria | enabled |

Prompts are meant to be modified, combined, or replaced. **Synthesis and reporting
code must not depend on specific evaluator names or on a fixed evaluator count.**

All lenses are defined in `evaluators/lenses.py`; `ENABLED_LENSES` in `config.py`
selects which run. Lens prompts ask only lens-specific questions — the output
format comes from the schema.

Verdicts: `VIABLE`, `VIABLE_IF`, `NEEDS_VALIDATION`, `RISKY`, `NOT_VIABLE`.
A lens verdict answers only that lens's question; problems outside the lens go to
`out_of_lens_red_flags`. The overall verdict is the synthesis's job.
Confidence: `LOW` / `MEDIUM` / `HIGH` with a one-sentence reason.

## Analysis quality requirements

These define what a "correct" report is — apply them when editing prompts or synthesis:

- Brutally honest; no marketing language. "Interesting concept" ≠ "viable business".
- Every number carries context: why this estimate, what would change it.
- Surface assumptions explicitly: "What would need to be true for this to work?"
- Demand specificity ("active traders" → "EU day traders with €5k+ portfolios").
- Separate possible from probable; focus on risks that kill projects, not nice-to-haves.
- Distinguish "idea is bad" from "idea needs validation first".
- Output is a structured report with confidence levels and actionable next steps.
- Synthesis highlights conflicting perspectives (including conflicting numbers).

## Engineering standards

- Production quality: explicit error handling, no silent fallbacks that fabricate data
  (e.g. a default confidence when parsing fails).
- Prefer structured outputs (tool use / JSON schema) over parsing free text.
- Keep core logic free of CLI I/O so it can be exposed through an MCP server later.
- Code, comments, docstrings, and commit messages in English.
- Realistic estimates for timelines and costs in docs and prompts.

## Roadmap

- **Phase 2 (done):** 3 evaluators, CLI, Markdown reports, heuristic synthesis.
- **Phase 3 (current):** Claude-based synthesis replacing keyword heuristics; structured
  evaluator output; parallel evaluation; remaining and domain-specific lenses; error handling.
- **Phase 4:** MCP server interface; optional web UI, persistence, JSON/PDF export.

## Known issues

- The synthesis prompt is new and not yet measured; there is no eval set yet.
