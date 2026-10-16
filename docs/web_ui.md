# Web UI (v1.0, step A) — agreed design

Agreed with the owner on 2026-10-15, before any code. Scope stays inside the v1.0
Definition of Done: a minimal local web UI (FastAPI + plain HTML/JS, server-sent
events for progress); no accounts, history, persistence or public hosting.

## The page

One page with four states:

1. **Input.** A large text field and an "Analyze" button. Above it, 5-6 example
   ideas; choosing one **fills the field** (it stays editable) and does not start
   the analysis. If the input check finds the idea too vague, its hint appears below
   the field: add details or analyze anyway.
2. **Live analysis** — the moment of the demo. One card per lens (revenue, 7-day
   MVP, growth, launch, retention, reality check) starts grey and lights up with its
   verdict as that lens finishes; a last line shows the synthesis waiting, then
   running. The ~3 minutes of a run become part of the show.
3. **Result.** The verdict in words and the confidence on top; killer risks, what
   holds up, conflicts between lenses, next steps. Each lens opens in full on click.
4. **Saving.** Each file has its own handling (owner's review, 2026-10-16):
   - the report is what the page shows; a button saves it as `report.md`;
   - the translated copy, when asked for, opens in its own tab, rendered on the
     page, with a button that saves it;
   - `report.json` is data for programs: saved only, from a line under the report.

## Example ideas

Chosen to show the range of verdicts, not only "risky":

| Example | What it shows |
|---------|---------------|
| Bookkeeping for hair and beauty salons in Vilnius | A realistic small business in a crowded market |
| Overdue-invoice reminders for B2B | A good idea: the system can say yes |
| Ticket resale in France, Belgium and Italy | An illegal core |
| API limit monitor for developers | Plausible, demand needs validation |
| A one-line idea ("a fitness app") | The input check asks for details instead of analyzing anything |

Personal ideas (`ideas/private/`) never appear in the list.

## Translation

- A checkbox "Add translation" enables a language list. **Lietuvių** is the default
  and comes first; the rest follow alphabetically by their own names: Deutsch,
  Eesti, Español, Français, Italiano, Latviešu, Polski, Русский, Українська. English
  is not in the list: the original is English.
- Only the checkbox before the run; no "translate" button on the result screen.
- The interface and the original report stay English. The translated copy is marked
  as a machine translation of the English original; numbers and structure are kept.

## Footer

States what runs where (the page on this computer; the analysis by Anthropic's
Claude API), where the facts come from (model knowledge, or web search for two
analyses when `WEB_SEARCH=on`), and that it is not financial or legal advice.

## Wording

Everything a person reads shows meanings in words, never internal codes (verdict
enums, lens keys, field names). `report.json` keeps the codes for programs.

## Running and showing

- Locally at `http://127.0.0.1:8000` (bound to this machine only; the API key stays
  in `.env`).
- Presentations: screen share of a local run; a visitor may dictate an idea.
- Variance between runs is a talking point, not a defect: wording and emphasis vary,
  while in the baseline eval the side of the verdict never flipped (0 of 17 cases
  went from not viable to viable or back).

## Decided against

- A gallery of saved past reports (a wall of text nobody reads in a demo).
- Showing the eval label after a run.
- A replay of a recorded run (a cartoon; a live run is the point).

## After v1.0 (later list)

Hosting with an invite code, a separate API workspace key with a monthly spend
limit, per-user and daily cost caps, the cheap input check before any expensive call.
