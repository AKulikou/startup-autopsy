# Behavior changes log

Every change that can change what the model answers — prompts, lenses, schemas,
model or request settings — gets an entry here, newest first. The full pipeline
eval (`python -m eval.run_eval pipeline --reps 2 --variant <name>`, about 14 USD
per pass) runs weekly, not after every change, so this log is how its results
are read: which changes a pass covers, and what each was expected to do.

Experiments sit behind switches in `.env` (`ANALYSIS_MODEL`, `THINKING`), so one
code version can be measured in several variants.

Entry format: date, commit, what changed, expected effect, how it was checked
so far, and the eval result once there is one.

## 2026-09-25 — lens selection per idea (off by default)

- **Change:** lenses can carry an applicability condition (`Lens.applies_to`):
  No-Code Stack Master, Viral Product Designer, Churn Eliminator, and the
  not-enabled AI Tool Creator and SaaS Revenue Builder. With `LENS_SELECTION=on`
  a separate call (`gate/lens_fit.py`, about 0.006 USD) skips enabled lenses
  whose condition fails; the report lists them with the reason.
- **Expected:** less lens noise on ideas the lenses do not fit (cookies, salon
  bookkeeping, physical goods), so fewer "not viable because not scalable"
  verdicts; slightly cheaper runs. Risk: a skipped lens can no longer raise a
  problem, so a wrongly skipped lens can lose a real finding.
- **Checked:**
  - First version asked the input check itself: gate eval (`--variant
    lens_selection`) fell from 93/93 to 83/93, with 10 vague ideas accepted as
    analyzable. Moved to a separate call; the input check prompt is unchanged.
  - Lens fit on the 17 pipeline ideas, 2 reps: skips are plausible (viral for
    solo tools, no-code and viral for salon bookkeeping, three lenses for
    cookies); no lens skipped on software products because it would score badly
    (the first version skipped no-code for 'too complex'). 3 of 17 ideas got
    different skips between reps.
  - One full run (good_salon_bookkeeping): 4 of 6 lenses, Viable if, report
    lists the skipped lenses.
- **Eval:** planned variant `lens_selection` against the winner of the model
  and thinking comparison. Look at cookies, salon and forged lens cases.

## 2026-09-25 — model and thinking switches (off by default)

- **Change:** `ANALYSIS_MODEL` selects the analysis model (default
  `claude-sonnet-4-6`; `claude-sonnet-5` priced in). `THINKING=adaptive` turns on
  adaptive thinking for the lenses and the synthesis; the input check never
  thinks. Eval rows record `model` and `thinking`.
- **Expected:** defaults change nothing. Sonnet 5: about a third cheaper per
  token at list price (its tokenizer may produce more tokens for the same text),
  unknown effect on verdicts and malformed answers — the prompts were tuned on
  Sonnet 4.6. Adaptive thinking: more output tokens and time; hoped-for gains in
  verdict stability between reps and in the synthesis on the systematic miss
  (ticket resale, where it stays soft on "laws may prohibit").
- **Checked:** unit tests; one Reality Auditor call on `ideas/api_monitor.txt`
  per combination (single samples, so only a hint):

  | Model, thinking | Verdict | In / out tokens | Time | Cost |
  |---|---|---|---|---|
  | Sonnet 4.6, off | RISKY, HIGH | 2060 / 2536 | 62 s | 0.044 USD |
  | Sonnet 4.6, adaptive | RISKY, MEDIUM | 2060 / 4797 | 126 s | 0.078 USD |
  | Sonnet 5, off | RISKY, MEDIUM | 2743 / 5654 | 73 s | 0.062 USD |
  | Sonnet 5, adaptive | NEEDS_VALIDATION, MEDIUM | 2743 / 5212 | 67 s | 0.058 USD |

  Sonnet 5 counted the same prompt as 33% more input tokens and wrote about
  twice the output, so this call cost more, not less, despite the lower price
  per token. The eval must compare cost per case, not per token.
- **Eval:** planned variants against `baseline`: `sonnet5`, then thinking on
  the model that wins.

## 2026-09-25 — baseline

- Pipeline `baseline` (Sonnet 4.6, no thinking, 6 lenses):
  29/34 = 85% of attempts in the expected verdict range (Wilson 95% CI 70–94%),
  13.61 USD. Systematic miss: ticket resale. Verdict changed between the two
  reps for 9 of 17 cases. Calibration: HIGH in range 15/16 but the same verdict
  in both reps only 8/16.
- Gate `baseline`: 93/93 (saturated; kept as a regression check).
