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

Abridged from a real run on [`ideas/alibaba_jewelry_flip.txt`](ideas/alibaba_jewelry_flip.txt):
resell cheap Alibaba jewelry through influencers, funded by investors who are
promised monthly dividends.

> ## Verdict: Not viable
>
> *A fundamental flaw that no amount of research or iteration fixes.*
>
> As described, this business is not viable. The investor-dividend structure is
> almost certainly an unregistered collective investment scheme under EU financial
> law, exposing the founder to criminal prosecution before a single piece of
> jewelry is sold. Separately, the founder explicitly plans to mis-declare goods to
> avoid customs duties — customs fraud under EU law. […]
>
> **Confidence:** High — Six independent lenses unanimously identified the same
> legal blocker […]
>
> ## Conflicts
>
> - No-Code Stack Master issued a 'Needs validation' verdict while its own analysis
>   states the investor platform 'cannot be legally launched' […]
>   - **Resolution:** The lens reasoning is correct and the verdict label
>     understates severity. […]

Only one of the six lenses answered "not viable" here; three said "needs
validation". The synthesis still reached "not viable": it weighs what the lenses
found, not how they voted, and flags a lens whose label contradicts its own
reasoning.

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
      report.json                    the same analysis as structured data
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
| AI Tool Creator | Is the AI capability genuinely useful and differentiated? | domain: AI products |
| Unit Economics Analyst | Does each customer bring in more than it costs to win and serve, and when does the business break even? | |
| Viral Product Designer | Can this grow through users themselves, without paid acquisition? | yes |
| Launch Expert | What can realistically be achieved in the first week after launch? | yes |
| Churn Eliminator | Will users stay, and what keeps them from cancelling? | yes |
| Reality Auditor | Are the founder's assumptions, competitive position and timeline realistic, and what early evidence should decide whether to continue? | yes |
| Legal Counsel | Can this business legally operate as described, and which legal requirements decide its cost or survival? | domain: regulated areas |
| Software Architect | What does it take to run this software reliably beyond the first version, and which technical risk could sink it? | domain: technically demanding software |

Domain lenses run only with `LENS_SELECTION=on`, and only on ideas they fit (see
Experiments below). Their expert knowledge lives in
[`lens_knowledge/`](lens_knowledge/) as Agent Skills: the pipeline adds each
skill to its lens's prompt, and the same folder can be installed as a
standalone skill in Claude Code. The legal lens is a screen for blockers, not
legal advice.

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

`ideas/` holds a few showcase ideas, each showing something different:

| Idea | What it shows |
|---|---|
| `alibaba_jewelry_flip` | An illegal core model found by every lens; conflicting margin estimates |
| `automatic_cv_update` | A hidden blocker the founder never mentions (LinkedIn API access) |
| `api_monitor` | A plausible idea whose honest answer is "validate this first" |
| `good_salon_bookkeeping` | A sound, boring business: the system can also say "viable" |

The full test set lives in `eval/`, including deliberately broken input and a
manipulation attempt (`forged_review_board`: a forged "review board" result
inside the idea text, which the analysis must ignore).

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

**Reports in other languages.** The analysis always runs in English, and the
English reports are the source of truth. A translated copy can be added in any
language Claude writes (Lithuanian, German, Japanese, ...) with one extra call to
Claude Haiku 4.5 (`TRANSLATION_MODEL`), the cheapest model: about a third of the
$0.12 the same translation cost on Sonnet 4.6.

- CLI: add `REPORT_TRANSLATION=Lithuanian` to `.env`; each run then writes
  `report.lithuanian.md` next to `report.md`. `TRANSLATE_LENS_REPORTS=true`
  translates the lens reports too.
- MCP: `analyze_idea` takes a `language` argument, so Claude passes the user's
  language itself; the path of the translation comes back as
  `translated_report_path`. Without the argument the `.env` setting applies.

Translation is a separate step over a finished run (`core/translator.py`,
`translate_run`): an existing translation is reused, not paid for again, and a
failed one never affects the English report. The eval never translates.

**Experiments.** Six `.env` switches change model behavior. They stay off
until the pipeline eval shows they help (see [eval/CHANGES.md](eval/CHANGES.md)):

| Switch | Effect |
|---|---|
| `ANALYSIS_MODEL` | Another model for the lenses and the synthesis, e.g. `claude-sonnet-5` or `claude-opus-5-5` |
| `ANALYSIS_EFFORT` | `low` ... `max`: how much the model thinks; the only depth control on Opus 5.5, which always thinks |
| `THINKING=adaptive` | The lenses and the synthesis think before answering |
| `LENS_SELECTION=on` | One small call (about $0.006) skips lenses whose question does not fit the idea, such as the viral lens for a local bakery, and adds the domain lenses that fit; the report lists what was skipped and why |
| `EXTRA_LENSES` | Defined lenses to run after the enabled ones, e.g. `EXTRA_LENSES=unit_economics` |
| `WEB_SEARCH=on` | The Reality Auditor and Legal Counsel check competitors, laws and prices on the web instead of relying on model memory; about $0.20 more per run |

## Project structure

```
main.py                    CLI: logging setup and idea selection
config.py                  API key check, model, token limit, enabled lenses, experiment switches
lens_knowledge/            domain knowledge for lenses, one Agent Skill per folder
evaluators/
  lenses.py                all lenses as data + shared analysis standards
  knowledge.py             loads a lens knowledge pack into the lens prompt
  evaluator.py             builds prompts from a lens and calls Claude
  schemas.py               EvaluatorResult: the structured output schema
gate/
  idea_gate.py             input check: is this an analyzable business idea?
  lens_fit.py              lens fit: which conditional lenses fit this idea (LENS_SELECTION)
  schemas.py               GateResult: the input check output schema
synthesis/
  synthesizer.py           overall verdict from all lens results
  schemas.py               SynthesisResult: the synthesis output schema
core/
  analysis_runner.py       orchestration: lenses, synthesis, reports
  structured_call.py       shared Claude request with validation and one retry
  claude_client.py         the Anthropic client (direct, or batching for the eval)
  batch_client.py          sends requests through the Message Batches API at half price
  idea_input.py            local checks and quote normalization of the idea text
  report_builder.py        the final report.md
  json_export.py           report.json, the analysis as structured data
  translator.py            optional translated copies of finished reports
  result_writer.py         Markdown report files
  idea_processor.py        idea loading and result saving facade
  file_manager.py          reading idea files
  token_summary.py         token usage and cost table
mcp_server.py              MCP server: check_idea and analyze_idea tools
skills/startup-autopsy/    Agent Skill for using the MCP tools
.claude/skills/            project skills for development (review-run, add-lens)
ideas/                     showcase ideas (.txt)
eval/                      eval cases, runner and behavior-change log (CHANGES.md)
tests/                     unit tests with a fake Claude client
docs/prompt_framework.md   evaluator framework specification
```

`results/` and `logs/` are generated and git-ignored.

## Use it from Claude (MCP server)

`mcp_server.py` exposes the analysis as two MCP tools, so Claude Code, Claude
Desktop or any MCP client can call it:

| Tool | What it does | Cost |
|---|---|---|
| `check_idea` | Is this a business idea, and is it detailed enough? Says what is missing. | ~$0.003, seconds |
| `analyze_idea` | The full analysis; saves the report under `results/` and returns the verdict, the full `report.md` and the path of `report.json`. | ~$0.40, ~3 minutes |

Add it to Claude Code (use absolute paths; on macOS/Linux the Python path is
`venv/bin/python`):

```bash
claude mcp add startup-autopsy -- /path/to/startup-autopsy/venv/Scripts/python.exe /path/to/startup-autopsy/mcp_server.py
```

Then ask Claude to evaluate an idea. The server reads the API key from `.env`
like the CLI does, and logs to `logs/mcp_server_*.log` (stdout carries the
protocol). Reports go to the project's `results/`, whichever folder the client
runs in. A full analysis takes a few minutes, so a client with a short tool
timeout needs it raised.

### A skill that teaches Claude to use the tools

`skills/startup-autopsy/` is an Agent Skill for the MCP tools: it tells Claude to
screen short or vague ideas with `check_idea` and ask what is missing, to confirm
the cost before a full run, and to present the verdict without softening it.
For Claude Code, copy the folder into your skills directory:

```bash
cp -r skills/startup-autopsy ~/.claude/skills/
```

## Testing

```bash
pip install -r requirements-dev.txt
pytest                                     # unit tests: no API calls, under a second
ruff check .                               # lint, targeting Python 3.10
python -m eval.run_eval gate --reps 3      # eval of the input check (~$0.25)
python -m eval.run_eval pipeline --reps 2  # eval of the whole pipeline (~$14)
python -m eval.run_eval pipeline --reps 2 --batch  # the same at half price, via Message Batches (slower)
python -m eval.trigger.run_trigger         # does the skill trigger on the right requests (Claude Code login)
```

The unit tests replace Claude with a scripted fake and cover the guards around
the model: malformed-answer detection and retry, input checks, parallel lenses,
report rendering and cost. The eval runs the real pipeline over reviewed cases
in `eval/` and grades the outcomes (see `eval/run_eval.py`). With `--batch`, every
request goes through the Message Batches API (`core/batch_client.py`): tokens
cost half, each pipeline stage waits for its batch, and the pipeline code is
unchanged, because the batching client answers the same call the direct client does. Some input-check
and trigger cases are in Russian on purpose: people describe ideas in their own
language, and the system has to handle that.

## Status and roadmap

Working now: lenses defined as data, run in parallel with structured output; a
Claude-based synthesis that decides the overall verdict; Markdown and JSON
reports; an input check; conditional domain lenses with their own knowledge
packs; an MCP server with a user skill; unit tests and an eval set.

Measured baseline (Sonnet 4.6, six lenses, 17 cases × 2 runs): 85% of runs gave a
verdict in the expected range. The input check passes all 93 of its eval cases.

Known limitations:

- Verdicts vary between runs of the same idea: in the baseline, 9 of 17 cases
  got a different verdict on the second run.
- The synthesis can stay soft on a blocker it describes as certain, answering
  "risky" instead of "not viable".
- Facts such as laws, competitors and prices come from model knowledge unless
  `WEB_SEARCH=on`.

Next:

1. Eval the experiment switches (newer models, thinking, lens selection, unit
   economics lens, web search) and make the winners the default.
2. A firmer synthesis on certain blockers, and more stable verdicts, both
   measured by the eval.
3. Re-analysis of an improved idea that shows what changed since the last report.
4. A local web UI with the report language chosen per user: the page renders
   `report.json`, so the translation will cover its text fields (verdict codes
   stay as codes) and interface labels come from a small dictionary. Later,
   optional PDF export and persistence.
5. Stock Autopsy: a follow-up project that applies the same multi-lens approach
   to public companies, with every number taken from official filings.

## License

MIT, see [LICENSE](LICENSE).
