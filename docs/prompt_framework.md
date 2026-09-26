# Analytical Prompt Framework

Startup Autopsy evaluates a business idea through several independent analytical
lenses. Each lens is run by the same evaluator (one Claude call per
lens); their outputs are then synthesized into a single report.

This document is the specification for those evaluators. When adding or changing
an evaluator in `evaluators/`, keep it consistent with the principles described here.

## Design principles

- **One lens per evaluator.** Evaluators must not overlap; each answers questions
  the others do not.
- **Assumptions over numbers.** Every estimate states the assumptions behind it and
  what would change it. A number without context is a defect.
- **Possible ≠ probable.** Separate what could happen from what is likely to happen.
- **Specificity.** Replace vague segments with concrete ones
  ("active traders" → "EU day traders with €5k+ portfolios").
- **Killer risks first.** Focus on risks that end the project, not nice-to-haves.
- **Two kinds of "no".** Distinguish "the idea is flawed" from "the idea is
  unvalidated".
- **Structured output.** Each evaluator returns a verdict, a confidence level
  (LOW / MEDIUM / HIGH, with the reason), and actionable next steps — not free-form narrative only.

## Verdicts

| Verdict | Meaning |
|---------|---------|
| `VIABLE` | Evidence supports building now |
| `VIABLE_IF` | Can work, but only if specific testable conditions hold |
| `NEEDS_VALIDATION` | Too little evidence to judge; research must come first |
| `RISKY` | No fundamental flaw, but serious risks need mitigation before investing |
| `NOT_VIABLE` | Fundamental flaw that no amount of research or iteration fixes |

Rules for choosing (sent to the model with the schema, see `VERDICT_RULES` in
`evaluators/schemas.py`):

- **A verdict answers the lens's own question**, not whether the whole business
  succeeds. The overall verdict belongs to the synthesis. A lens that notices a
  serious problem outside its scope lists it in `out_of_lens_red_flags` without
  letting it change its verdict. No lens judges the whole idea: when the Reality
  Auditor did, the synthesis followed its verdict in every run, even when the other
  lenses stayed the same and only the Reality Auditor's verdict changed.
- Judge the idea as described; a pivot belongs in the next steps, not in the verdict.
- Something within the lens that makes the idea unworkable as described (illegal,
  policy-blocked, economically impossible) is `NOT_VIABLE`.
- `RISKY` means every serious risk within the lens can be mitigated without
  changing the core model.
- `NEEDS_VALIDATION` means the deciding question is still open; an established
  blocker calls for `RISKY` or `NOT_VIABLE`.
- The killer risk is also scoped to the lens, so that verdict, summary and killer
  risk agree.

Confidence describes how sure the evaluator is that the verdict is right, not how
good the idea is: `HIGH` rests on facts, regulations or arithmetic, `MEDIUM` on
plausible but unverified assumptions, `LOW` on a judgement call with key
information missing.

## The lenses

The prompt text of every lens lives in `evaluators/lenses.py`; this section
summarises what each lens covers. A lens only asks its own questions: the
verdict, confidence, key assumptions, killer risk and next steps are requested
from every lens by the shared output schema, not by the lens prompt.

| # | Lens | Key | Answers the question |
|---|------|-----|----------------------|
| 1 | Profitable App Designer | `profitable_designer` | Would people pay for this every month, and how much revenue is realistic? |
| 2 | No-Code Stack Master | `no_code_stack` | Can a sellable MVP be built with no-code tools in 7 days? |
| 3 | AI Tool Creator | `ai_tool_creator` | Is the AI capability genuinely useful and differentiated, and can it find paying customers? |
| 4 | SaaS Revenue Builder | `saas_revenue_builder` | Is there a realistic path from MVP to sustainable recurring revenue? |
| 5 | Viral Product Designer | `viral_designer` | Can this grow through users themselves, without paid acquisition? |
| 6 | Launch Expert | `launch_expert` | What can realistically be achieved in the first week after launch? |
| 7 | Churn Eliminator | `churn_eliminator` | Will users stay, and what keeps them from cancelling? |
| 8 | Reality Auditor | `reality_auditor` | Are the founder's assumptions, competitive position and timeline realistic, and what early evidence should decide whether to continue? |
| 9 | Legal Counsel | `legal_counsel` | Can this business legally operate as described, and which legal requirements decide its cost or survival? |
| 10 | Software Architect | `software_architect` | What does it take to run this software reliably beyond the first version, and which technical risk could sink it? |

Lenses must not overlap. For example, tool selection belongs only to the
No-Code Stack Master; the Profitable App Designer looks at automation only as an
operating-cost question. The Software Architect starts where the No-Code Stack
Master stops: not the first sellable version, but running the product reliably
at a cost below its price. The Legal Counsel owns legality; other lenses record a
legal problem only as a red flag.

Lenses 3, 9 and 10 are domain lenses: they run only with lens selection on and
where they fit (see Lens applicability). Each has a knowledge pack in
`lens_knowledge/<name>/`, written as an Agent Skill (`SKILL.md` with `name` and
`description` frontmatter, optional `references/`). The pipeline strips the
frontmatter and adds the instructions and references to the lens's system prompt;
the same folder installs unchanged as a skill in Claude Code or claude.ai.

### How a prompt is assembled

- **System prompt:** the lens role, the shared `ANALYSIS_STANDARDS`
  (honesty, numbers with context, specificity, flawed vs unvalidated, missing
  information), and the lens focus.
- **User message:** the lens questions as a numbered list, followed by the idea.
- **Output:** `EvaluatorResult` (`evaluators/schemas.py`) via structured outputs.

Which lenses run is configured by `ENABLED_LENSES` in `config.py`; an unknown key
fails at startup.

## Synthesis

One more Claude call (`synthesis/synthesizer.py`) reads every lens result — the
structured fields and the full analysis — and decides the overall verdict. Its
principles (`SYNTHESIS_PRINCIPLES`): weakest link rather than majority vote;
substance over labels (a lens verdict that contradicts its own reasoning is recorded
as a conflict); independent corroboration raises weight, an unsupported claim is an
assumption to test; a blocker counts as fatal only if it lies in the business
itself, not in a replaceable implementation choice (stack, channel, supplier);
flawed versus unvalidated; lower confidence when lenses disagree
or some failed. It must name the deciding factors and the lenses behind each, so the
verdict can be checked. Code only warns about obvious inconsistencies (for example an
overall "viable" when a lens found the idea not viable); it never overrides the verdict.

The final report (`report.md`) shows:

- each perspective with its lens verdict and confidence;
- red flags that lenses raised outside their own scope (several lenses flagging the
  same problem independently is strong evidence);
- where evaluators agree, and where they conflict — including conflicting numbers
  (e.g. different conversion or audience assumptions);
- the assumptions the whole idea depends on and how to test them;
- what holds up: the parts the lenses examined and found sound (may be empty);
- a final recommendation synthesized from all perspectives, with clear next steps
  or an explicit "don't pursue".

The synthesis must not depend on specific evaluator names or on a fixed number of
evaluators: lenses can be modified, combined, reordered, or replaced, and
domain-specific lenses can be added.

## Lens applicability

A lens asked a question that does not fit the idea produces confident noise: the
subscription and viral lenses called a local cookie business "not viable". A lens
can therefore carry an applicability condition (`Lens.applies_to`, e.g. "the
product's value depends on AI"); a lens without one fits every business idea.
With `LENS_SELECTION=on`, one small call (`gate/lens_fit.py`) decides for each
enabled conditional lens whether its condition holds, and the lenses that do not
fit are skipped and listed in the report. It judges fit, not quality, and when
unsure the lens runs.

This is a separate call from the input check on purpose: asked together, the lens
conditions leaked into the input check, which then accepted vague ideas ("an online
learning platform") as analyzable.
