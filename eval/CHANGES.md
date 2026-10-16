# Behavior changes log

Every change that can change what the model answers — prompts, lenses, schemas,
model or request settings — gets an entry here, newest first. The full pipeline
eval (`python -m eval.run_eval pipeline --reps 2 --variant <name>`, about 14 USD
per pass) runs when budget allows, not after every change, so this log is how its results
are read: which changes a pass covers, and what each was expected to do.

Experiments sit behind switches in `.env` (`ANALYSIS_MODEL`, `ANALYSIS_EFFORT`,
`THINKING`, `LENS_SELECTION`, `EXTRA_LENSES`, `WEB_SEARCH`), so one code version
can be measured in several variants.

Entry format: date, commit, what changed, expected effect, how it was checked
so far, and the eval result once there is one.

## At a glance

Milestones (details in the entries below, newest first):

- **2026-09-25** — baseline of the whole pipeline (six lenses, Sonnet 4.6); switches for
  model, thinking and lens selection; domain lenses with their own knowledge packs.
- **2026-09-26** — "What holds up" in the synthesis; web search for the fact-heavy lenses,
  Opus 5.5 support and an effort switch (all off by default); trigger test for the skill.
- **2026-09-27** — the eval rebuilt: one primary verdict per case, error costs and paired
  cases; a judge for planted flaws; a blind second annotation that settled the labels;
  constant and random baselines and stability in every summary; eval through Message
  Batches at half price; experiment A on where the instability comes from.
- **2026-10-07** — a warning when a lens says it searched the web without searching.
- **2026-10-14** — two prompt changes tried and reverted (no gain in a targeted eval);
  translation moved to Haiku 5.5.
- **2026-10-16** — translation section by section, with checks for text left in English
  or written in another language.

What the measurements showed:

- The reports find the planted flaws (22 of 24), yet the verdict drawn from them barely
  beats a constant answer: the weak point is the step from findings to a verdict.
- A large share of the verdict instability comes from the synthesis itself: on identical
  lens results its verdict still changed in 4 of 6 cases, mostly between "risky" and
  "needs validation" (experiment A). That is the planned v1.1 fix.
- Prompt changes that a targeted eval showed to bring no gain were reverted; the input
  check passed all 93 runs of its eval (31 cases, three runs each).

## 2026-10-16 — translation: wrong language and English headings caught, stricter retry

- **Why (owner's review of two live runs after the previous change):** in a Russian
  translation the "Next Steps" section came back in Lithuanian (the report is about
  Vilnius); the overlap check passed it, because Lithuanian shares no words with the
  English source. In both runs "Why: Deciding Factors" kept its English heading, and
  in one of them the whole section stayed English after the retry (kept and marked).
  What the rejected answers looked like is unknown: they were not logged.
- **Changed (translation only):** the prompt asks to write the whole translation in
  the target language, even where the text is about another country. A section of
  25+ words is also rejected when its letters are mostly in another script (Russian,
  Ukrainian and other Cyrillic languages; Greek, Japanese, Chinese, Korean, Arabic,
  Hebrew, Hindi; Latin for the Latin-script languages of the web page) or, for the
  eight Latin-script languages of the web page, when 2% or more of its letters (10
  or more) are outside the language's alphabet. A level-2 heading of two or more
  words that comes back unchanged is rejected too. A rejected section is asked once
  more with a stricter note in the prompt and effort `medium`
  (`TRANSLATION_RETRY_EFFORT`). If only the heading is still English, the translated
  section is kept; anything worse keeps the English original with the note, as
  before. The start of each rejected answer goes to the debug log.
- **Calibration:** on the four real Russian translations, translated sections have
  75-100% Cyrillic letters, the Lithuanian and the English sections 0%; one real
  Lithuanian name added 3 foreign letters in 4,000, the Lithuanian section had 115 in
  1,300. Run over those four reports, the checks flag exactly the known defects (the
  Lithuanian section, the English section, the English headings of the two older
  translations) and nothing else. The Latin-script rule has no real translation to
  be checked on yet.
- **Expected:** no section in a wrong language; English headings rare. A retry costs
  well under a cent (Haiku 5.5, one section). No effect on any verdict or on the eval.
- **Checked:** pytest (wrong script, foreign letters, names allowed, heading check,
  stricter retry, kept-in-English fallback, heading-only fallback), ruff. Not yet
  checked with a live translation.

## 2026-10-16 — translation section by section, headings translated

- **Why (owner's review of the web UI):** in two real Russian translations every
  heading and fixed label stayed English (the prompt said "keep the Markdown
  structure exactly: headings, ..."), and in one of them the whole last section,
  "Appendix: How the Verdict Was Reached", came back untranslated (0 Cyrillic
  letters in 5,600 characters) although the call ended normally.
- **Changed (translation only):** the prompt asks to translate all text, headings,
  table headers and labels included, and to keep the markup. A report is
  translated one level-2 section at a time (up to 4 calls in parallel) and put
  back together. A section whose words mostly come back unchanged (60% or more,
  sections of 25+ words) is retried once; if it is still English, it is kept with
  a note saying so instead of losing the whole translation. A failed call still
  fails the whole translation (the English report stays).
- **Calibration of the check:** on the two real translations, translated sections
  kept 4-35% of their words (names, file names, links), the untranslated appendix
  100%; the check flags exactly that one section.
- **Expected:** fully translated reports; about 10 small calls instead of one,
  slightly more input tokens (the prompt per call), shorter wall time. No effect on
  any verdict or on the eval (`analyze()` never translates).
- **Checked:** pytest (sections split and rejoined, retry, kept-and-marked section,
  one failed section fails the translation, the check on texts), ruff. Not yet
  checked with a live translation.

## 2026-10-14 — translation on Haiku 5.5

- **Changed (model, translation only):** `TRANSLATION_MODEL` from
  `claude-haiku-4-5` to `claude-haiku-5-5` with effort `low` (Haiku 5.5 thinks
  by default at medium). Prices checked on the pricing page 2026-10-14: 0.10 /
  0.50 USD per MTok for prompts up to 100K tokens (Haiku 4.5: 1 / 5). The
  analysis, the input check and the eval judge stay on their models: the
  translation never reaches the eval (`analyze()` does not translate), and the
  judge is calibrated against the author's annotation.
- **Expected:** the same translations at about a tenth of the cost; no change in
  any verdict.
- **Checked:** pytest (new test: thinking blocks before the text are ignored),
  ruff. One live translation of a 21k-character report into Russian: 7,360 in /
  9,448 out tokens, 35 s, 0.0055 USD (the same token counts on Haiku 4.5 would
  be about 0.05 USD). Same headings, bullets and tables as the Haiku 4.5 copy;
  every number kept, decimals written with a comma as Russian does.

## 2026-10-14 — shared standards: survivorship bias

- **Why:** a lens can argue from a success story ("X built this and grew to ...")
  without the attempts that failed, which makes an idea look more promising than
  the evidence supports. No measured case yet: this is a preventive rule, so it
  must earn its place in the eval.
- **Changed (prompt, all lenses):** one line in `ANALYSIS_STANDARDS` — a success
  story is not evidence on its own; for every comparable business cited as proof,
  consider how many similar attempts failed and why. Same principle added to
  `docs/prompt_framework.md`. Adapted from Anthropic's knowledge-work-plugins
  (`data/skills/validate-data`, common analysis pitfalls; Apache 2.0), rewritten.
- **Expected:** fewer verdicts carried by a single success example; no change in
  `flaw_found`.
- **Risk to watch:** a shared line moves every lens, so it can make the whole
  pipeline more cautious. Watch `primary_hit` and `error_cost` on the `good_`
  cases (`good_b2b_invoice_reminders`, `good_technical_translation`): a shift
  from viable to risky there means the rule costs more than it gives.
- **Evaluate separately** from the Reality Auditor change below (separate commit),
  otherwise the eval cannot tell which change moved the verdicts.
- **Checked so far:** pytest, ruff and `check_lenses.py` only.
- **Targeted eval (2026-10-14, variant `p0002_targeted`, both commits,
  `--reps 2 --batch`, 1.20 USD):** `good_b2b_invoice_reminders` VIABLE_IF x2
  (as baseline; Reality Auditor VIABLE_IF and NEEDS_VALIDATION),
  `good_technical_translation` VIABLE_IF x2 (its primary label; no baseline, the
  case was added later), `salon_bookkeeping` VIABLE_IF x2, flaw found 0/2. No
  case became more cautious. No lens and no synthesis in the six traces mentions
  survivorship or failed similar attempts, so these cases show no effect of the
  rule either way.
- **Decision (2026-10-14): reverted.** No lens or synthesis mentioned
  survivorship in 6 traces; the rule is inert on these cases. Kept in history
  for a case with success-story arguments: `git show d99912a --
  evaluators/lenses.py docs/prompt_framework.md | git apply` brings it back.

## 2026-10-14 — Reality Auditor: four kinds of competition

- **Seen:** in the regraded baseline the planted flaw was missed in 2 of 24
  reports, both `salon_bookkeeping`: neither report named the crowded market.
  In both baseline traces the Reality Auditor's stored result does not mention
  competition at all (keyword check: competit*, crowded, saturated, incumbent,
  alternative*; the only "switching" is a next step about interviewing leads who
  did not convert), although its question is "Who already solves this problem".
- **Changed (prompt):** the Reality Auditor's competition question now names four
  kinds: direct competitors, products that solve the problem differently, larger
  players who could add it as a feature, and the customer's current workaround (a
  spreadsheet, a freelancer, doing nothing); it also asks what switching costs the
  customer. Taxonomy adapted from Anthropic's knowledge-work-plugins
  (`product-management/skills/competitive-brief`, Apache 2.0), rewritten.
- **Expected:** `flaw_found` on `salon_bookkeeping` (crowded market) and the same
  finding on `meeting_schedule`; no change elsewhere.
- **Risk to watch:** competition weighed too heavily. `salon_bookkeeping` has
  `must_not` "Calls the idea not viable because of competition alone"; watch it
  and the verdicts of the `good_` cases.
- **Checked so far:** pytest, ruff and `check_lenses.py` only. Not evaluated yet:
  run the gate eval and one or two single-idea runs (`salon_bookkeeping`,
  `good_b2b_invoice_reminders`), then the pipeline eval when budget allows.
- **Result (2026-10-14, variant `p0001_competition`, before the survivorship-bias
  commit):** gate `--reps 3` unchanged (93/93 correct, 0 false reject, 0 false
  accept, 0.23 USD). One pipeline run of `salon_bookkeeping` (0.40 USD): the lens
  changed, the report did not pass. The Reality Auditor now covers all four kinds
  of competition (baseline: no mention at all) and names a cheaper freelance
  bookkeeper as its killer risk; the synthesis keeps that as a finding and adds
  "indistinguishable from the generic competitors" (Churn Eliminator), but never
  calls the market crowded, so the judge still gives `flaw_found` 0 (baseline
  0/2). Verdict VIABLE_IF as in both baseline reps, confidence HIGH (baseline
  MEDIUM); `must_not_ok` 1. The lens treats competition as specific threats and
  low switching costs as a point in the idea's favour, not as a saturated market.
  One run decides nothing; `good_b2b_invoice_reminders` and the pipeline eval of
  this commit alone were not run before the next commit landed.
- **Targeted eval (2026-10-14, variant `p0001_targeted`, commit 3848d14 in a
  worktree, `--reps 2 --batch`, 1.20 USD):**

  | Case | Baseline | p0001_targeted |
  |---|---|---|
  | `salon_bookkeeping` | VIABLE_IF x2, flaw found 0/2 | VIABLE_IF x2, flaw found 0/2 |
  | `meeting_schedule` | NEEDS_VALIDATION, RISKY; flaw found 2/2 | RISKY, **NOT_VIABLE** (outside the range); flaw found 2/2, `must_not_ok` 2/2 |
  | `good_b2b_invoice_reminders` | VIABLE_IF x2 | VIABLE_IF x2 |

  Target not reached: with this commit `salon_bookkeeping` is 0/3 (0/5 with the
  two reps of the next variant). The Reality Auditor names competitors in every
  run, but no report calls the market crowded; the judge is right on the
  wording ("saturation" means the founder's capacity, "commodity" a churn risk).
  The watched risk shows at lens level: the Reality Auditor's own verdict moved
  down on the good case (NEEDS_VALIDATION in 2/2, baseline VIABLE_IF 2/2) and on
  `meeting_schedule` (NOT_VIABLE once, baseline RISKY 2/2). The synthesis
  absorbed it on the good case and followed it once on `meeting_schedule`,
  where NOT_VIABLE rests on free incumbents plus a false technical assumption
  (Google Contacts holds no time zones) and churn economics, so `must_not` held.
  Two reps per case: a direction, not a measurement.
- **Decision (2026-10-14): reverted.** `salon_bookkeeping` flaw found 0/5; on
  the three targeted cases the error cost equals the baseline (7 vs 7 over 6
  runs); one verdict out of range (`meeting_schedule` NOT_VIABLE); the Reality
  Auditor stricter on `good_b2b_invoice_reminders` (NEEDS_VALIDATION 2/2,
  baseline VIABLE_IF 2/2).
- **Next hypothesis for `salon_bookkeeping`:** market crowding in Vilnius is a
  fact the model may not know without live data; test `WEB_SEARCH=on` on
  `salon_bookkeeping`, 2 reps. Label unchanged.
- **Hypothesis test (2026-10-14, variant `websearch_salon`, `WEB_SEARCH=on`, code
  after the revert, 2 reps, not batched, 1.01 USD):** flaw found 1/2, verdict
  VIABLE_IF/MEDIUM in both, `must_not_ok` 2/2. The split follows the searches:
  rep1 made 3 searches and cited "127 listed bookkeeping providers in Vilnius,
  about 71 EUR/month on average" (paslaugos.lt), so the report priced the idea
  at 2.1x the market and the judge found the flaw (its Reality Auditor said
  NEEDS_VALIDATION; the synthesis stayed VIABLE_IF). Rep0 made no search while
  writing "I searched below to confirm" (`unbacked_search_claim` warning fired),
  used model-knowledge prices and missed the flaw like every run without search
  (0/5). Supports the hypothesis that the miss is missing live data, not the
  question; the open problem is that the lens does not always use the tool it
  has. The 127 / 71 EUR figures were not checked by hand. One run each way.

## 2026-10-07 — warning when a lens claims a web search it did not make

- **Seen:** a single run with `LENS_SELECTION=on` and `WEB_SEARCH=on` (a solo
  smart-contract auditing idea, 0.64 USD). Reality Auditor and Legal Counsel both
  had the search tool and made **no** search (`web_searches=0` in the log, input
  tokens 8.5k and 9.9k against about 45k when results come back), yet wrote
  "I searched for current platform eligibility policies", "search results suggest…"
  and "Verified current platforms (searched May 2026)". Model knowledge was
  presented as checked: wrong provenance, not a style issue.
- **Changed (code only, no prompt change):** `unbacked_search_claim` in
  `evaluators/evaluator.py` looks for first-person search claims in a lens result
  with zero searches. A hit is logged as a warning, kept in the result's new
  `warnings` list (so also in `report.json`), and shown as a `> **Warning:**`
  line at the top of `report.md` and of that lens's report. The review-run script
  counts these log lines. The verdict and the analysis are left as they are.
- **Checked:** both claims of that run are found; 270 lens answers in the stored
  eval traces (all without web search) give no hit, so no false alarms there and
  the claims look tied to the search guidance being in the prompt.
- **Open:** why the lenses did not search at all on this run (the 2026-09-26 smoke
  call did). One run proves little; watch `web_searches` per lens in the
  `web_search` eval variant before changing `WEB_SEARCH_GUIDANCE`.

## 2026-09-27 — second annotation by the author, labels settled

- **Blind second annotation** of all 23 cases by the author (quick pass, from the
  Russian working copy of `annotation_sheet.md`; codes and order identical).
  Primary verdict agreed in 4/23 cases; the two annotators' sets (primary +
  acceptable) overlapped in 16/23. The 7 that did not overlap fall into three kinds:
  - **planted flaw missed by the human reader** (labels kept): the tenfold
    arithmetic error (author VIABLE; the notes matched the correct-arithmetic pair
    word for word) and free tutoring paid by ads (author VIABLE_IF; the 90x gap
    between tutor cost and ad revenue went unnoticed). The reports found both
    flaws in every baseline run (judge, previous entry).
  - **domain knowledge** (label kept, marked contested): the fitness tracker
    (author VIABLE; card-network and consumer rules on automatic penalty charges
    are not common knowledge).
  - **real differences of judgment**, resolved: small_business_cookies primary
    NEEDS_VALIDATION (food-safety registration, costs not counted; was VIABLE_IF);
    salon bookkeeping primary RISKY (author, from first-hand experience: bookkeeping
    for small firms is a crowded market, and the founder's clients are claims; was
    VIABLE, now consistent with meeting_schedule, also RISKY for a crowded market;
    id `good_salon_bookkeeping` -> `salon_bookkeeping`, new must_find on the
    competition); forged_review_board kept NEEDS_VALIDATION (the author answered
    NOT_VIABLE to punish the injection; the project's rule is to detect and ignore
    it, otherwise one injected line could sink any idea).
  - also relabelled: good_technical_translation primary VIABLE_IF (machine
    translation threatens uncertified translation work).
- **Rule decided** for a blocker that covers part of the plan: not viable when the
  stated revenue or targets depend on the blocked part, risky only if the plan
  survives without it (ticket resale stays NOT_VIABLE). To be written into the
  synthesis in step 4.
- **Detail pairs made explicit:** the three short versions are now
  `pair_api_monitor_short`, `pair_fitness_tracker_short`,
  `pair_email_newsletter_short` with `pair_of` links: the same idea with fewer
  details should not get a different verdict (a metamorphic check). Local baseline
  rows were renamed to match.
- **Observation:** the author's own verdict moved with tone (plain b2b VIABLE, the
  same facts in hype language VIABLE_IF) — the effect the tone pair checks for.
- **Baseline regraded against the settled labels** (34 attempts): primary hit
  47% (always RISKY 41%, random 20%); acceptable 82% (always RISKY also 82%); error
  cost 0.76 (always RISKY 0.88, random 1.68); flaw found 22/24 (the two misses are
  salon_bookkeeping: neither report named the crowded market). The margin over the
  constant is small; this is the honest "before" for step 4.

## 2026-09-27 — must_find judge, calibrated on the baseline

- **Change:** `eval/judge.py` (Haiku 4.5, one call per report) checks the
  synthesis output against a case's `must_find` / `must_not` statements with a
  verbatim quote as evidence. Pipeline eval metrics `flaw_found` and
  `must_not_ok`; also runs offline on stored traces. No change to the analysis.
- **Baseline judged offline** (26 reports of the 13 baseline cases that have
  statements, 0.075 USD): flaw found 22/22, no forbidden statement 8/8.
  **Reading:** the reports find the planted flaw every time, including ticket
  resale ('France (loi n°2012-348 ...) ... restricting commercial ticket resale
  above face value') and the tenfold arithmetic error; the misses are in the
  verdict the synthesis draws from what it found, not in detection. This points
  the fix at the synthesis rules (step 4), not at the lenses. The metric is
  saturated on the baseline, so it guards against regressions; harder statements
  (the garden delivery cost, which one run lost) are needed to make it discriminate.
- **Judge calibration:** all 13 rep-0 decisions checked by hand, all correct
  (quotes contain the finding; the one retry was a misnumbered answer caught by
  the validator). Negative check: three reports judged against another case's
  statements (salon vs arithmetic error, api monitor vs ticket resale,
  newsletter vs LinkedIn API): every statement correctly absent. Small sample:
  enough to trust the direction, not a measured error rate.

## 2026-09-27 — eval labels: one primary verdict per case, error costs, pairs

- **Change:** `eval/pipeline/cases.json` gives every case one `primary` verdict and
  optional `acceptable` neighbours instead of a wide expected range; `must_find` /
  `must_not` statements record the flaw planted in a case (graded by a judge, next
  entry); `pair_of` links minimal pairs. New cases: `pair_ticket_resale_fr_be_it`
  (NOT_VIABLE) and `pair_ticket_resale_de` (RISKY), `pair_arithmetic_correct`
  (VIABLE_IF, pair of the arithmetic error), `pair_good_b2b_invoice_reminders_hype`
  (same facts in hype language, VIABLE), `good_technical_translation` (VIABLE):
  23 cases. The headline metric is `primary_hit`; `in_range` (primary or
  acceptable) and a mean `error_cost` from an asymmetric matrix (`ERROR_COST` in
  `eval/grading.py`: a positive verdict on a not-viable idea costs 5, erring
  cautious costs 1-2) come next. Summaries regrade stored rows against the current
  labels, so old runs stay comparable.
- **Labels are provisional:** set by the developer from the case notes; a blind
  second annotation by the author is pending (`eval/pipeline/annotation_sheet.md`).
  Notable choices: fitness tracker primary RISKY (commitment-contract products
  exist, so the core is contested, not clearly illegal); NFT puddles primary
  RISKY (weak demand is not an impossibility); arithmetic error primary RISKY
  (loses money as described, fixable by price or volume; VIABLE_IF no longer
  acceptable); ticket resale primary NOT_VIABLE with RISKY acceptable, pending the
  rule for a blocker that covers part of the plan; the German pair assumes
  above-face resale is legal in Germany (to confirm).
- **Baseline regraded** (same 34 attempts, 17 of the 23 cases): primary hit
  16/34 = 47% (CI 31-63%), acceptable 28/34 = 82%, error cost 0.71. Always RISKY:
  primary 35%, acceptable 71%, error cost 1.00; random: 20%, 42%, 1.69. The system
  now clears the constant by 12 points on the headline and by 0.29 in error cost;
  the intervals still overlap at 34 attempts.

## 2026-09-27 — experiment A: how much instability comes from the synthesis

- **Setup:** one fresh pipeline run (variant `expA_lenses`, batch, Sonnet 4.6,
  default settings) of the six cases whose verdict changed in the baseline:
  api_monitor, automatic_cv_update, borderline_arithmetic_error,
  forged_review_board, meeting_schedule, nft_puddle_photos (5/6 in range, 1.23
  USD). Then `eval/replay_synthesis.py`: the synthesis 4 more times on each
  run's fixed lens results (batch, 1.41 USD). 30 syntheses, 5 per case.
- **Result (synthesis alone, lens results fixed):** modal agreement 80%;
  verdict changed in 4/6 cases; 0 cross-side flips; pair disagreement 0.33.
  - stable: api_monitor NEEDS_VALIDATION x5, borderline_arithmetic_error
    NEEDS_VALIDATION x5; their baseline changes came from the lenses.
  - unstable on identical inputs: automatic_cv_update RISKY 3 / NEEDS_VALIDATION 2;
    nft_puddle_photos RISKY 3 / NEEDS_VALIDATION 2; meeting_schedule RISKY 4 /
    NEEDS_VALIDATION 1; forged_review_board RISKY 4 / NOT_VIABLE 1.
- **Reading:** the synthesis is a real source of instability on its own, mainly
  at the RISKY / NEEDS_VALIDATION boundary (7 of 8 minority verdicts). For
  comparison, the full pipeline's pair disagreement over all 17 baseline cases is
  0.53; on these six (picked because they changed) it was 1.0 with 2 reps. So
  roughly: a large share of the instability survives with the lenses held fixed,
  and the rest comes from the lenses. Small sample (6 cases x 5), picked for
  instability: a direction, not a precise split.
- **Implication for the plan:** fixing the synthesis (step 4) matters for
  stability, not only for soft blockers. The RISKY / NEEDS_VALIDATION boundary
  is the one to define sharply (the review's "two axes" point: evidence vs
  outcome). Synthesis-only changes can be measured cheaply with this replay
  (about 0.06 USD per synthesis in batch).
- **Added:** pair disagreement in summaries (share of pairs of runs with
  different verdicts; comparable across numbers of reps).

## 2026-09-27 — grader tested, constant baseline and stability in the summary

- **Change:** grading moved to `eval/grading.py` with unit tests; summaries show
  constant and random reference scores and verdict stability; `--summary-only`
  recomputes a summary for free. Pipeline traces now keep the full lens results.
  No prompt or model change.
- **Baseline recomputed** (same 34 attempts, no new API calls):
  - in range 29/34 = 85% (CI 70-94%); **always RISKY 24/34 = 71%**, random
    verdict 44%. The in-range metric barely separates the system from a
    constant, because RISKY is allowed in 13 of 18 cases. It also hid the soft
    blocker problem: RISKY on an illegal core counted as a hit.
  - stability: modal agreement 74%; verdict changed in 9/17 cases; **0
    cross-side flips** (all changes between neighbours; two RISKY <-> NOT_VIABLE,
    both with HIGH confidence in both reps); mean ordinal spread 0.53.
  - calibration: HIGH in range 15/16 but all reps agreeing only 8/16; MEDIUM
    11/15 and 8/15; LOW 3/3 and 0/3. HIGH does not predict stability.
  - lens flip rates: Launch Expert 11/17, Profitable App Designer 6/17, Reality
    Auditor 6/17, Churn Eliminator 4/17, No-Code Stack Master 3/17, Viral 3/17.
- **Correction:** until this change, traces dropped the lens `analysis` text
  that the synthesis reads, so baseline traces cannot replay the synthesis on
  identical inputs (the review bundle said they could). Replays need traces
  written from now on.
- **Source:** external review of 2026-09-27 (three parts plus a summary); its
  plan is the working plan: grader and baselines, stability decomposition
  (synthesis replay), eval redesign, synthesis fix, citations, report, README.

## 2026-09-27 — eval through Message Batches (`--batch`)

- **Change:** `run_eval.py --batch` sends every request through the Message
  Batches API (`core/batch_client.py`). Prompts, schemas and settings are
  unchanged; only the transport and the price differ. Rows carry `batch: true`,
  their cost is at batch prices, and their latency measures batch waiting.
- **Expected effect:** half the token cost, same verdicts within normal
  variation.
- **Checked:** gate, 4 cases in one batch: 4/4 correct, 135 s, 0.01 USD.
  Pipeline, `good_salon_bookkeeping`: in range, consistent, all lenses ok,
  430 s, 0.20 USD against 0.39-0.40 USD for the same case in `baseline`.
- **Prompt caching, measured and not enabled:** the repeated prefix is the
  output schema (about 1,170 tokens for a lens, 1,720 for the synthesis) plus
  the system prompt (about 410 tokens for a core lens). The lenses of one run
  start together and have different system prompts, so a single run gets no
  cache hits and would pay the cache-write premium; only the eval repeats a lens
  prompt across ideas, estimated at about 6% of a pass. Worth one measured try
  in batch mode later, not a default.

## 2026-09-27 — eval cases renamed, two pipeline ideas translated

- **Change:** pipeline case ids `zz_cookies_ru` → `small_business_cookies` and
  `zz_forged_lens` → `forged_review_board`; `garden_tool_rental_ru` →
  `garden_tool_rental`. The cookies and garden ideas are now in English (the
  gate eval keeps its Russian cases, including the same cookies text, as
  language coverage). `forged_review_board.txt` moved from `ideas/` to
  `eval/pipeline/ideas/`: it is a test case, not a showcase idea.
- **Expected effect:** none on the other cases. The `small_business_cookies`
  baseline was measured on the Russian text, so a verdict change there can come
  from the language, not from a later change. The local baseline results were
  renamed to the new ids so comparisons still line up.
- **Checked:** pytest and ruff; no API calls.

## 2026-09-26 — Opus 5.5 support and an effort switch

- **Change:** pricing for `claude-opus-5-5` (4 / 20 USD per MTok) and
  `ANALYSIS_EFFORT` (low ... max) for the lenses and the synthesis; unset keeps
  each model's default (Opus 5.5: medium). Opus 5.5 always thinks: the code
  sends no thinking parameter with `THINKING=off`, so requests are valid, and
  effort is the only depth control. No forced tool_choice, refusals already
  raise. Prompt audit: the synthesis `reasoning` field is a report section for
  the reader, not a request for internal reasoning; kept, watch for
  `reasoning_extraction` refusals.
- **Checked:** effort together with structured output (smoke call). One run of
  the garden idea, `ANALYSIS_MODEL=claude-opus-5-5`, default effort: 0 refusals,
  0 malformed; 0.87 USD (Sonnet 4.6: 0.43); synthesis 53 s instead of about
  95 s. All six lenses costed the delivery loss (11-50 BYN per trip, each
  estimate attributed), one attribution warning instead of five. Verdict
  Viable if conditions hold, outside the case's expected Risky / Needs
  validation - defensible under 'a replaceable implementation choice is a
  condition', one run, not tuned.
- **Eval:** variant `opus55` (`ANALYSIS_MODEL=claude-opus-5-5`, then
  `ANALYSIS_EFFORT=low` as a cheaper arm); about twice the Sonnet 4.6 cost per
  case, so roughly 30 USD per pass.

## 2026-09-26 — web search for fact-heavy lenses (off by default)

- **Change:** `WEB_SEARCH=on` gives the Reality Auditor and Legal Counsel the
  server-side web search tool (`web_search_20260209`, max 3 searches) and a
  line asking them to check competitors, laws and prices and mark what they
  could not confirm. `pause_turn` is resumed up to 3 times; searches are
  counted and priced (0.01 USD each).
- **Why:** the garden tool rental report named Leroy Merlin as a Minsk
  competitor; it left Belarus in 2020-2022 (a user's Claude caught it).
- **Checked:** web search works together with structured output (smoke call
  on Sonnet 4.6). One run of the garden idea: the Reality Auditor made 3
  searches and named four real Minsk rental firms with their prices (20-40
  BYN/day), no Leroy Merlin, prices it could not confirm marked unverified.
  Reality Auditor 0.23 USD instead of about 0.04 (45k input tokens of search
  results); the run 0.61 USD instead of 0.43. Verdict Needs validation.
- **Eval:** variant `web_search` (`WEB_SEARCH=on`); watch cost per case and
  whether verdicts on legal cases (ticket resale, Alibaba) change.

## 2026-09-26 — startup-autopsy skill description (trigger)

- **Change:** the user skill's description now says why the tools beat an
  answer from model knowledge, to use them even when the user gives numbers,
  covers shared business plans and quitting a job to start a business, and
  lists what it is not for (a career move, writing a business plan,
  brainstorming, market statistics, plain calculations).
- **Why:** in the manual MCP test it triggered on 1 of 2 idea prompts.
- **Checked:** new trigger test `eval/trigger/run_trigger.py`, 24 queries
  (13 should trigger, 11 should not), 3 runs each, Opus 5.5:

  | Description | Effort | Triggered when wanted | Quiet when not wanted |
  |---|---|---|---|
  | old | default | 12/13 | 11/11 |
  | old | low | 10/13 | 11/11 |
  | new | default | 12/13 | 11/11 |
  | new | low | 12/13 | 11/11 |

  Old at default: 11/12 on the first 23 queries plus the business-plan query
  (2/3) run separately. The one miss left is moonshine sold to neighbours
  (0/3 in every setting): Claude answers illegal ideas itself. Not tuned for.
- **Lessons:** an unquoted ': ' in the description broke the YAML frontmatter
  and made one run meaningless (3/13); the test now refuses to run on it.
  A usage-limit error once counted as 'not triggered'; it now counts as a
  failed run.

## 2026-09-26 — Unit Economics Analyst (defined, not enabled)

- **Change:** SaaS Revenue Builder re-scoped into Unit Economics Analyst
  (`unit_economics`): cost to serve, gross margin, acquisition cost and payback,
  break-even. Not in `ENABLED_LENSES`; default runs unchanged.
- **Why:** manual MCP test, garden tool rental near Minsk (15 BYN/day + 10 BYN
  delivery, 10 tools for 3000 BYN): the synthesis dropped the delivery cost
  (60-120 km round trips for 10 BYN) that Reality Auditor had listed as an
  assumption; the client Claude spotted it.
- **Checked:** one run of the same idea with the lens added (ad-hoc script):
  delivery cost moved into the deciding factors and 'What Must Be True', the
  lens added 'year-one LTV below acquisition cost'; verdict Risky (without the
  lens: Needs validation); +0.03 USD. One run each - not evidence of a verdict
  shift.
- **Eval:** variant `unit_economics`: `EXTRA_LENSES=unit_economics python -m eval.run_eval
  pipeline --reps 2 --variant unit_economics`. New pipeline case
  `garden_tool_rental` (expected Risky or Needs validation) is not in the
  baseline: compare the 17 shared cases, and run the new case on the baseline
  settings too (`--cases garden_tool_rental --variant baseline`).

## 2026-09-26 — 'What holds up' in the synthesis

- **Change:** new synthesis field `what_holds_up` (0-4 findings the lenses examined
  and found sound, with lens attribution; empty allowed) and a principle in
  `SYNTHESIS_PRINCIPLES`: strengths are evidence, never outweigh a blocker. New
  report section 'What Holds Up'.
- **Expected:** no verdict change. Risk to watch: softer verdicts (strengths
  pulling bad ideas up) and marketing-style strengths on weak ideas; output
  tokens up slightly.
- **Checked:** pytest; one run each of beer subscription and salon bookkeeping:
  both VIABLE_IF, 3-4 attributed strengths, none flagged by the review-run
  attribution check. Observation (one run, not tuned): one salon strength rests
  on the founder's own claim (12 years certified), which the field excludes.

## 2026-09-25 — domain lenses with knowledge packs (with lens selection only)

- **Change:** `DOMAIN_LENSES` (AI Tool Creator, new Legal Counsel, new Software
  Architect) run only with `LENS_SELECTION=on`, where the lens fit check finds
  their condition holds. Each has a knowledge pack in `lens_knowledge/<name>/`
  (an Agent Skill) added to its system prompt. Default runs are unchanged.
- **Expected:** the ticket resale miss fixed by a lens that owns legality;
  illegal cores (Alibaba, fitness penalties) caught by a lens, not only by red
  flags. Cost per case up by roughly 0.05–0.10 USD per domain lens that runs.
- **Checked:**
  - First conditions were too broad: lens fit added Legal Counsel to 17 of 17
    pipeline ideas (any personal data counted) and Software Architect to 12.
    Narrowed ("paperwork every business has does not count", "a standard app
    does not count"): Legal 12/17, Architect 9/17, on plausible ideas.
  - `--variant domain_smoke`, ticket resale and Alibaba, 2 reps each: 4/4 in
    range. Ticket resale: RISKY/HIGH twice (baseline: NEEDS_VALIDATION twice,
    out of range), Legal Counsel leads the first deciding factor. Alibaba:
    NOT_VIABLE/HIGH twice, as in baseline. 0.49–0.57 USD per case (baseline
    about 0.42). Remaining softness: the ticket resale summary calls the core
    'a statutory offence' that 'collapses the revenue model' yet the verdict is
    RISKY, not NOT_VIABLE.
- **Eval:** part of the `lens_selection` variant.

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
