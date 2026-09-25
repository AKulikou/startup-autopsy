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
