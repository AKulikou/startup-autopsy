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
ruff check .                                   # lint (config in pyproject.toml, target Python 3.10)
python -m eval.run_eval gate --reps 3          # eval: input check (~$0.25)
python -m eval.run_eval pipeline --reps 2      # eval: whole pipeline (~$14, paid)
python -m eval.trigger.run_trigger --effort low # skill trigger test (~15 min, Claude Code login, no API key)
```

Requires `ANTHROPIC_API_KEY` in `.env` (never commit it). Run `pytest` and `ruff check .`
after any change. After a change to prompts, lenses or the model, run the cheap gate eval
and one or two single-idea runs; the pipeline eval runs only when budget allows, with
the change logged in `eval/CHANGES.md` so that run can be read against it. After a change to
the user skill's description, or when the default Claude model changes, run the trigger
test at the default and the low effort level; accept a change only if it is no worse on both.

## Layout

- `main.py` — CLI entry point, logging setup, idea selection
- `mcp_server.py` — MCP server (`check_idea`, `analyze_idea`) over stdio; logs only to file, never to stdout
- `config.py` — API key check, model, token limit, enabled lenses
- `evaluators/lenses.py` — all lenses as data (role, focus, questions) + shared `ANALYSIS_STANDARDS`
- `evaluators/evaluator.py` — `Evaluator`: builds prompts from a lens, calls Claude with structured output
- `evaluators/schemas.py` — `EvaluatorResult` Pydantic schema (verdict, confidence, assumptions, killer risk, next steps)
- `synthesis/synthesizer.py` — `Synthesizer`: one Claude call that reads all lens results and decides the overall verdict (`SYNTHESIS_PRINCIPLES`); `synthesis/schemas.py` — `SynthesisResult`
- `core/structured_call.py` — shared structured request: stop-reason checks, result validation, one retry
- `gate/lens_fit.py` — `LensFitCheck`: with `LENS_SELECTION` on, one call that decides which conditional lenses (`Lens.applies_to`) fit the idea
- `gate/idea_gate.py` — `IdeaGate`: one Claude call that decides NOT_AN_IDEA / TOO_VAGUE / ANALYZABLE before the lenses run (`gate/schemas.py` — `GateResult`)
- `core/idea_input.py` — local checks before any API call (empty or letterless input is rejected; straight double quotes become typographic)
- `core/analysis_runner.py` — orchestrates load → lenses → synthesis → reports → token stats
- `core/translator.py` — optional translated copies of finished reports in any language (`translate_run`; `REPORT_TRANSLATION` in `.env`, or `language` in the MCP call); the analysis stays English
- `core/report_builder.py` — builds `report.md` (synthesis first, lens results as appendix)
- `core/json_export.py` — builds `report.json`: the same analysis as structured data (codes, not display words; failed calls kept with their error)
- `core/idea_processor.py`, `file_manager.py`, `result_writer.py` — idea I/O and Markdown output
- `skills/startup-autopsy/` — user-facing Agent Skill for the MCP tools (install into ~/.claude/skills); not auto-loaded in this repo
- `eval/trigger/` — trigger test for that skill: `queries.json` (should / should not trigger) and `run_trigger.py` (runs `claude -p`, model and effort as parameters, checks the frontmatter first)
- `.claude/skills/review-run/` — project skill: review a finished run (script for mechanical checks + judgment guide)
- `.claude/skills/add-lens/` — project skill: add or change a lens; `scripts/check_lenses.py` checks lenses, config and doc tables agree
- `ideas/` — a few showcase ideas for the CLI and README; `eval/` — eval cases (`gate/`, `pipeline/` with their own ideas) and `run_eval.py`; `results/`, `logs/`, `.claude/hillclimb/` — generated, git-ignored

## Evaluator framework

Full specification: [docs/prompt_framework.md](docs/prompt_framework.md) — read it
before adding or changing an evaluator or the synthesis.

Each prompt is a distinct lens (lenses must not overlap):

| # | Evaluator | Lens | Status |
|---|-----------|------|--------|
| 1 | Profitable App Designer | Revenue model, recurring revenue, assumptions behind numbers | enabled |
| 2 | No-Code Stack Master | 7-day no-code MVP, concrete stack, day-7 scope | enabled |
| 3 | AI Tool Creator | AI differentiation, pricing rationale, first 10 customers | domain |
| 4 | Unit Economics Analyst | Cost to serve, gross margin, acquisition cost and payback, break-even | defined |
| 5 | Viral Product Designer | Network effects, conditions for organic growth | enabled |
| 6 | Launch Expert | First-week traction grounded in real audience size | enabled |
| 7 | Churn Eliminator | Onboarding, habit loops, when retention tactics fail | enabled |
| 8 | Reality Auditor | Killer risk, true timeline, go/no-go criteria | enabled |
| 9 | Legal Counsel | Legality of the model, licences, compliance cost, questions for a lawyer | domain |
| 10 | Software Architect | Hardest technical capability, dependencies, cost per customer, production team | domain |

Prompts are meant to be modified, combined, or replaced. **Synthesis and reporting
code must not depend on specific evaluator names or on a fixed evaluator count.**

All lenses are defined in `evaluators/lenses.py`; `ENABLED_LENSES` in `config.py`
selects which run. `domain` lenses (`DOMAIN_LENSES`) run only with `LENS_SELECTION`
on and where their `applies_to` condition fits; their knowledge is an Agent Skill in
`lens_knowledge/<name>/`, added to the lens prompt by `evaluators/knowledge.py`. Lens prompts ask only lens-specific questions — the output
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
- **Phase 4 (started):** MCP server (`mcp_server.py`) and a user skill for it (`skills/startup-autopsy/`), done; JSON export (`report.json`) done; optional web UI, persistence, PDF export.
- **Next project:** Stock Autopsy — the same multi-lens approach applied to public
  companies, with every number taken from official filings.

## Known issues

- Verdicts vary between runs of the same idea (9 of 17 eval cases changed verdict
  between two reps in the baseline); judge prompt changes by the eval, not one run.
- The synthesis can stay soft on a blocker it describes as certain (calls the core
  illegal, yet says RISKY rather than NOT_VIABLE).
- Facts (laws, competitors, prices) come from model knowledge, not live sources, unless
  `WEB_SEARCH=on` (Reality Auditor and Legal Counsel only; off by default).
- Experiments behind `.env` switches (`ANALYSIS_MODEL`, `ANALYSIS_EFFORT`, `THINKING`, `LENS_SELECTION`, `EXTRA_LENSES`, `WEB_SEARCH`)
  are off by default until the pipeline eval decides; see `eval/CHANGES.md`.
