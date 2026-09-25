---
name: startup-autopsy
description: Evaluate a business or startup idea with the Startup Autopsy MCP tools (check_idea, analyze_idea) and present a brutally honest verdict - viable, viable if conditions hold, needs validation, risky or not viable - with the reasons, killer risks and next steps. Use this whenever someone describes a business, product or startup idea and asks whether it is worth doing, will work, makes money, or what is wrong with it, or asks to validate, stress-test, review or "tear apart" an idea - even if they do not mention Startup Autopsy.
compatibility: Needs the startup-autopsy MCP server (tools check_idea and analyze_idea) connected to the client.
---

# Evaluate a business idea with Startup Autopsy

Startup Autopsy runs several independent analytical lenses over an idea and a
synthesis that decides one overall verdict. Two MCP tools expose it:

| Tool | Use it for | Cost and time |
|---|---|---|
| `check_idea` | Is this a business idea, and is it detailed enough? What is missing? | ~0.003 USD, seconds |
| `analyze_idea` | The full analysis; returns the verdict and the full report | ~0.40 USD, about 3 minutes |

The user pays for every call with their own API key, so the cheap check comes
first whenever it can save a wasted full run.

## 1. Get an analyzable description

Pass the idea in the founder's own words. The analysis is only as concrete as
its input: what is sold, to whom, at what price, and the founder's own numbers
and plans. Their numbers matter even if they are optimistic - the analysis
checks them.

If the idea is short, vague, or you are unsure it is a business at all, call
`check_idea` first. When it says the idea is too vague, turn its
`missing_information` into a few short questions for the user, then combine the
answers with the original text. When it says it is not a business idea, relay
the reason plainly; a wish ("get rich fast") or a one-off personal sale is not
something this tool analyzes.

## 2. Confirm before the full run

Tell the user the full analysis takes about 3 minutes and costs about 0.40 USD,
and run it when they agree. Pass a short `name` (it becomes the results folder
name). Set `analyze_if_vague` only if the user explicitly wants to go ahead
with a description the check found too vague - the report will then say its
conclusions rest on assumptions.

## 3. Present the result without softening it

Lead with the verdict in the tool's words and the one or two reasons that
decide it. The point of this tool is an honest answer before someone spends
months building; a "not viable" wrapped in encouragement defeats that. Then:

- **Confidence** and what it depends on. It is the model's own assessment, not
  a statistic, and the same idea can get a neighbouring verdict on another run -
  say so if the user is about to make a big decision on it.
- **What could kill the project** - the top risks, with the lenses that raised them.
- **Conflicts** - especially where the analysis contradicts the founder's own
  numbers (for example realistic revenue several times lower than claimed).
- **Next steps** - the first one or two, concretely. If the verdict is not
  viable, the first step is not to pursue it as described; mention a pivot only
  if the report suggests one.
- Where the full report is saved (`report_path`), for the details.

Keep your own opinion separate. If you disagree with the verdict, say so as
your view with your reason, after presenting the tool's verdict - do not blend
the two.

Facts in the report (laws, market sizes, competitors, prices) come from the
model's knowledge, not from live sources. When a verdict hinges on one of them
- a regulation that may ban the model, a competitor that may already offer it -
tell the user to verify that fact before acting on it.

Answer in the user's language; the report itself is in English.

## If the tools are not available

Say that the Startup Autopsy MCP server is not connected, and point to the
project README ("Use it from Claude") for the one-line setup. Do not imitate
the analysis yourself and present it as the tool's result.
