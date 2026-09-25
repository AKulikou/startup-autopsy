# Startup Autopsy

Brutally honest evaluation of business ideas from several independent analytical
perspectives, powered by Claude.

Startup Autopsy runs a business idea through a set of evaluators, called *lenses*.
Each lens looks at the idea from one angle only (revenue, buildability, risk, and
so on) and returns a structured verdict. The reports name the one risk most likely
to kill the project, the assumptions the verdict depends on, and concrete next
steps. "Do not pursue this" is a valid next step.

The goal is to answer one question before you spend months building:
**what would need to be true for this to work, and how cheaply can I find out?**

## Example

Abridged excerpt from a real run on [`ideas/fitness_tracker_short.txt`](ideas/fitness_tracker_short.txt),
an app that charges your card when your weight goes up:

> **Reality Auditor. Verdict: NOT_VIABLE (confidence HIGH)**
>
> **Killer risk:** Stripe and all major payment processors reject the variable
> automatic charge mechanic as a gambling/wagering scheme, making the core
> financial penalty loop impossible to implement without building a regulated
> escrow product.

| Assumption | How to test | Failure signal |
|---|---|---|
| A major payment processor will approve automatic variable charges tied to body weight | Submit a merchant application to Stripe describing the exact use case | Stripe rejects it or requires an escrow model |
| Users will trust a new app with card authorization for unpredictable charges | Landing page asking 200 visitors to pre-authorize a $10 variable charge | Fewer than 10 of 200 complete it |

All three lenses enabled at the time independently named the payment processor as the
killer risk; the synthesis treats such independent agreement as strong evidence.

## How it works

```
ideas/<idea>.txt
      |
      v
  input check: local (empty or letterless text is rejected), then one short
  Claude call: not a business idea / too vague (you may analyze anyway) / analyzable
      |
      v
  one Claude call per enabled lens, each with its own role and questions
      |
      v
  structured result per lens (validated with a Pydantic schema):
  lens verdict, confidence + reason, summary, killer risk within the lens,
  key assumptions (how to test, failure signal), next steps,
  red flags outside the lens, full analysis
      |
      v
  synthesis: one more Claude call reads every lens result and decides
  the overall verdict, resolving conflicts between lenses
      |
      v
  results/<timestamp>_<idea>/        one directory per run, sorted by time
      report.md                      the final report: verdict, reasons,
                                     risks, conflicts, next steps
      lenses/<lens>.md               full report of each lens (appendix)
```

Each lens verdict answers only that lens's question ("can an MVP be built in
7 days?", "will people pay monthly?"). Problems a lens notices outside its scope
are reported as red flags, and the overall verdict is left to the synthesis.

Evaluators use Claude structured outputs, so reports are built from typed fields
rather than parsed from free text. A malformed response is retried once; a
truncated, refused or repeatedly malformed one is reported as an error, never
filled in with defaults.

### Verdicts

| Verdict | Meaning |
|---|---|
| `VIABLE` | Evidence supports building now |
| `VIABLE_IF` | Can work, but only if specific testable conditions hold |
| `NEEDS_VALIDATION` | Too little evidence to judge; research must come first |
| `RISKY` | No fundamental flaw, but serious risks need mitigation before investing |
| `NOT_VIABLE` | A fundamental flaw that no research or iteration fixes |

Confidence is `LOW`, `MEDIUM` or `HIGH`, always with a one-sentence reason.

### Lenses

The lenses are defined in [`evaluators/lenses.py`](evaluators/lenses.py);
`ENABLED_LENSES` in [`config.py`](config.py) selects which ones run.

| Lens | Answers the question | Enabled by default |
|---|---|---|
| Profitable App Designer | Would people pay for this every month, and how much revenue is realistic? | yes |
| No-Code Stack Master | Can a sellable MVP be built with no-code tools in 7 days? | yes |
| AI Tool Creator | Is the AI capability genuinely useful and differentiated? | |
| SaaS Revenue Builder | Is there a realistic path to sustainable recurring revenue? | |
| Viral Product Designer | Can this grow through users themselves, without paid acquisition? | yes |
| Launch Expert | What can realistically be achieved in the first week after launch? | yes |
| Churn Eliminator | Will users stay, and what keeps them from cancelling? | yes |
| Reality Auditor | Are the founder's assumptions, competitive position and timeline realistic, and what early evidence should decide whether to continue? | yes |

The design rules behind the lenses (no overlap, shared analysis standards, output
defined by the schema) are described in [`docs/prompt_framework.md`](docs/prompt_framework.md).

## Quick start

Requirements: Python 3.10+ and an [Anthropic API key](https://console.anthropic.com/).

```bash
git clone <repository-url>
cd startup-autopsy

python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env              # then set ANTHROPIC_API_KEY in .env
python main.py
```

The CLI lists the ideas in `ideas/`. Pick one by number or name, and the reports
are written to `results/`. Logs go to `logs/`.

**Time and cost.** The lenses run in parallel, about a minute or so each, followed by
the synthesis (about a minute and a half), so a run takes about 3 minutes. One run
on `claude-sonnet-4-6` costs roughly $0.30–0.40, depending on the length of the idea
and of the answers.

## Adding your own idea

Create a text file in `ideas/`, for example `ideas/my_idea.txt`. Plain prose is
fine; the more concrete the input, the more concrete the analysis. It helps to cover:

- the problem and who exactly has it
- the solution
- the target customer, as specifically as you can
- pricing and revenue model
- your own numbers and assumptions: evaluators check them rather than accept them

If something is missing, evaluators state what they had to assume instead. An empty
file or text with almost no letters is rejected before any API call is made.

### Demo ideas

The bundled ideas deliberately range from plausible to absurd, and several contain
flawed numbers or hidden legal problems on purpose. They show what the evaluators catch.

| Idea | What it exercises |
|---|---|
| `api_monitor` | A plausible developer tool; competition and willingness to pay |
| `meeting_schedule` | A crowded market with free alternatives |
| `automatic_cv_update` | Dependence on a third-party API the product cannot control |
| `email_newsletter` | Optimistic growth numbers for a low-price subscription |
| `fitness_tracker` | Payment and regulatory blockers in the core mechanic |
| `alibaba_jewelry_flip` | Unrealistic margins; taking investor money is itself a legal problem |
| `nft_puddle_photos` | A speculative market, a hype-driven idea, and inconsistent math |

`*_short` variants contain the same idea in a few sentences and are useful for
quick, cheaper runs.

## Configuration

[`config.py`](config.py):

| Setting | Default | Purpose |
|---|---|---|
| `MODEL` | `claude-sonnet-4-6` | Claude model used by all lenses |
| `MODEL_PRICING_PER_MTOK` | Sonnet 4.6 rates | Input/output prices for the cost estimate after a run; add an entry when changing `MODEL` |
| `MAX_TOKENS` | `16000` | Output limit per lens; a truncated answer is treated as an error |
| `ENABLED_LENSES` | see the lens table | Which lenses run, by key |

The API key is read from `.env` (`ANTHROPIC_API_KEY`). The program stops at
startup if the key is missing or malformed.

## Project structure

```
main.py                    CLI: logging setup and idea selection
config.py                  API key check, model, token limit, enabled lenses
evaluators/
  lenses.py                all lenses as data + shared analysis standards
  evaluator.py             builds prompts from a lens and calls Claude
  schemas.py               EvaluatorResult: the structured output schema
gate/
  idea_gate.py             input check: is this an analyzable business idea?
  schemas.py               GateResult: the input check output schema
synthesis/
  synthesizer.py           overall verdict from all lens results
  schemas.py               SynthesisResult: the synthesis output schema
core/
  analysis_runner.py       orchestration: lenses, synthesis, reports
  structured_call.py       shared Claude request with validation and one retry
  idea_input.py            local checks and quote normalization of the idea text
  report_builder.py        the final report.md
  result_writer.py         Markdown report files
  idea_processor.py        idea loading and result saving facade
  file_manager.py          reading idea files
  token_summary.py         token usage table
ideas/                     input ideas (.txt)
docs/prompt_framework.md   evaluator framework specification
```

`results/` and `logs/` are generated and git-ignored.

## Status and roadmap

Working now: lenses defined as data (most enabled by default, all run in parallel), structured output,
a Claude-based synthesis that decides the overall verdict, and a final report
with the lens reports as an appendix.

Known limitations:

- The synthesis is new and not yet measured against an eval set.

Next:

1. An eval set: ideas with expected verdicts and automated consistency checks,
   run several times per prompt change.
2. Lens selection per idea by the input check, and domain lenses (legal, AI,
   software architecture) enabled only where they apply.
3. An MCP server interface, so the analysis can be called as a tool from Claude
   and other MCP clients.
4. Optional: JSON/PDF export, persistence, web UI.
