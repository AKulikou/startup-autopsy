# Analytical Prompt Framework

Startup Autopsy evaluates a business idea through eight independent analytical
lenses. Each lens is implemented as a separate evaluator (one Claude call per
lens); their outputs are then synthesized into a single report.

This document is the specification for those evaluators. When adding or changing
an evaluator in `evaluators/`, keep it consistent with the lens described here.

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
  (0–100), and actionable next steps — not free-form narrative only.

## Verdicts

| Verdict | Meaning |
|---------|---------|
| `VIABLE` | High confidence; ready to build |
| `VIABLE_IF` | Viable under explicit, testable conditions |
| `NEEDS_VALIDATION` | Too early to judge; requires user or market research first |
| `RISKY` | Major risks identified; needs mitigation before investment |
| `NOT_VIABLE` | Fundamental flaw found |

## The eight lenses

### 1. Profitable App Designer — product and revenue model
Evaluates software viability with an emphasis on recurring revenue and low
operational overhead.

- What specific problem would people pay for monthly?
- Which no-code tools could build it without custom code?
- Which automations reduce day-to-day intervention?
- What is a realistic revenue range at months 3 and 6?
- **Critical:** what assumptions underpin these numbers?

**Output:** revenue projections with explicit assumptions.

### 2. No-Code Stack Master — technical feasibility under time pressure
Designs a minimum viable product using only no-code tools within 7 days.

- Which specific tool for each component?
- Why is this combination better than alternatives for this case?
- What is the day-by-day plan from day 1 to launch?
- What can realistically ship on day 7 that someone would pay for?

**Output:** concrete stack, prioritized features, realistic day-7 scope.

### 3. AI Tool Creator — AI-first product and distribution
Evaluates AI-powered subscription tools with a focus on differentiation and
customer acquisition.

- What concrete AI capability makes this useful rather than a curiosity?
- What interface conveys credibility?
- What pricing model, and why this price point?
- What is the concrete plan to acquire the first 10 paying customers?
- Which real channels (not "do marketing")?

**Output:** positioning, pricing rationale, specific acquisition channels.

### 4. SaaS Revenue Builder — growth and monetization
Designs a path from MVP to sustainable recurring revenue.

- Which pricing tiers, with what conversion rates, and why?
- Which features reduce churn after month 1?
- What low-cost acquisition strategy?
- What are the projections for months 3, 6, and 12?
- **Critical:** clearly separate optimistic and conservative scenarios.

**Output:** tiered pricing, churn-reduction tactics, two-scenario projections.

### 5. Viral Product Designer — organic growth and network effects
Evaluates the potential for user-driven growth without paid acquisition.

- What is the core value proposition?
- At which point in the user journey should sharing be incentivized?
- Which network effect makes the product more valuable with more users?
- What would need to be true for organic growth to happen?
- **Critical:** which conditions are required rather than assumed?

**Output:** viral mechanics, network effects, preconditions for organic growth.

### 6. Launch Expert — first-week traction
Maximizes first-week results, grounded in the founder's actual audience size.

- What pre-launch waitlist strategy?
- What launch-day sequence and timing?
- What incentive for early adopters?
- **Critical:** what is reasonable given the real audience size, not a
  hypothetical one?

**Output:** launch sequence, incentive structure, realistic first-week numbers.

### 7. Churn Eliminator — retention and unit economics
Designs mechanisms that keep users engaged and reduce cancellations.

- What onboarding demonstrates value in the first session?
- Which feature becomes part of a daily routine?
- How are cancellation signals detected before they happen?
- What churn reduction is realistic in 30 days?
- **Critical:** under which conditions would these tactics fail?

**Output:** onboarding flow, habit-forming mechanisms, churn targets with failure
conditions.

### 8. Reality Auditor — critical assessment and decision framework
Provides an unfiltered skeptical evaluation before significant time is committed.

- Which parts depend on unrealistic assumptions?
- What is the true timeline to a first working version (not the ideal case)?
- What is the single biggest risk that kills the project?
- What evidence in the first weeks would justify continuing?
- Is the idea flawed, or does it need validation first?

**Output:** realistic timeline, critical risks, go/no-go criteria.

## Synthesis

Evaluator results are aggregated into one report that shows:

- each perspective with its verdict and confidence;
- where evaluators agree, and where they conflict — including conflicting numbers
  (e.g. different conversion or audience assumptions);
- the assumptions the whole idea depends on and how to test them;
- a final recommendation synthesized from all perspectives, with clear next steps
  or an explicit "don't pursue".

The synthesis must not depend on specific evaluator names or on a fixed number of
evaluators: lenses can be modified, combined, reordered, or replaced, and
domain-specific lenses can be added.

## Implementation status

| # | Lens | Module |
|---|------|--------|
| 1 | Profitable App Designer | `evaluators/profitable_designer.py` |
| 2 | No-Code Stack Master | `evaluators/no_code_stack.py` |
| 3 | AI Tool Creator | planned |
| 4 | SaaS Revenue Builder | planned |
| 5 | Viral Product Designer | planned |
| 6 | Launch Expert | planned |
| 7 | Churn Eliminator | planned |
| 8 | Reality Auditor | `evaluators/reality_auditor.py` |
