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
pip install -r requirements.txt
python main.py                                 # interactive: pick an idea from ideas/
```

Requires `ANTHROPIC_API_KEY` in `.env` (never commit it).
No test suite yet.

## Layout

- `main.py` — CLI entry point, logging setup, idea selection
- `config.py` — API key check, model, token limit, enabled lenses
- `evaluators/lenses.py` — the eight lenses as data (role, focus, questions) + shared `ANALYSIS_STANDARDS`
- `evaluators/evaluator.py` — `Evaluator`: builds prompts from a lens, calls Claude with structured output
- `evaluators/schemas.py` — `EvaluatorResult` Pydantic schema (verdict, confidence, assumptions, killer risk, next steps)
- `core/analysis_runner.py` — orchestrates load → evaluate → save → synthesize → token stats
- `core/report_aggregator.py` — builds the synthesis report
- `core/idea_processor.py`, `file_manager.py`, `result_writer.py` — idea I/O and Markdown output
- `ideas/` — input ideas (`.txt`); `results/`, `logs/` — generated, git-ignored

## Evaluator framework

Full specification: [docs/prompt_framework.md](docs/prompt_framework.md) — read it
before adding or changing an evaluator or the synthesis.

Eight prompts, each a distinct lens (must not overlap):

| # | Evaluator | Lens | Status |
|---|-----------|------|--------|
| 1 | Profitable App Designer | Revenue model, recurring revenue, assumptions behind numbers | enabled |
| 2 | No-Code Stack Master | 7-day no-code MVP, concrete stack, day-7 scope | enabled |
| 3 | AI Tool Creator | AI differentiation, pricing rationale, first 10 customers | defined |
| 4 | SaaS Revenue Builder | Pricing tiers, churn, 3/6/12-month optimistic vs conservative | defined |
| 5 | Viral Product Designer | Network effects, conditions for organic growth | defined |
| 6 | Launch Expert | First-week traction grounded in real audience size | defined |
| 7 | Churn Eliminator | Onboarding, habit loops, when retention tactics fail | defined |
| 8 | Reality Auditor | Killer risk, true timeline, go/no-go criteria | enabled |

Prompts are meant to be modified, combined, or replaced. **Synthesis and reporting
code must not depend on specific evaluator names or on a fixed evaluator count.**

All eight are defined in `evaluators/lenses.py`; `ENABLED_LENSES` in `config.py`
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
  evaluator output; async parallel evaluation; remaining 5 evaluators; error handling.
- **Phase 4:** MCP server interface; optional web UI, persistence, JSON/PDF export.

## Known issues

- `core/report_aggregator.py` only restates evaluator fields (verdicts, killer risks,
  next steps); Claude-based synthesis that resolves conflicts is still Phase 3 work.
- Evaluators run sequentially.
