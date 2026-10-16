// The page: input -> live analysis -> result with downloads (docs/web_ui.md).

import { createCard, el, updateCard, verdictBadge, verdictClass } from "./cards.js";
import { followRun } from "./events.js";
import { createLanguagePicker } from "./languages.js";
import { renderMarkdown } from "./markdown.js";

const $ = (id) => document.getElementById(id);
const VIEWS = ["input-view", "live-view", "result-view"];

let languagePicker;
let timer = null;
let lensCounts = { started: 0, finished: 0 };

function show(view) {
  for (const id of VIEWS) $(id).hidden = id !== view;
  window.scrollTo({ top: 0 });
}

async function request(method, url, body) {
  const response = await fetch(url, {
    method,
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await response.json().catch(() => ({}));
  return { status: response.status, data };
}

function detailText(data) {
  // FastAPI validation errors come as a list; our own errors as a string.
  if (typeof data.detail === "string") return data.detail;
  return "The request was not accepted. Check the idea text and try again.";
}

// ---------- 1. Input ----------

function setBusy(busy) {
  $("analyze").disabled = busy;
  languagePicker.setDisabled(busy);
}

function inputMessage(nodes, isError = false) {
  const box = $("input-message");
  box.classList.toggle("is-error", isError);
  box.replaceChildren(...nodes);
  box.hidden = nodes.length === 0;
}

function needsDetailsMessage(check) {
  const nodes = [];
  if (check.decision === "TOO_VAGUE") {
    const p = el("p");
    p.append(el("strong", null, "The input check needs more detail. "), check.reason);
    nodes.push(p);
    if (check.missing.length) nodes.push(el("p", null, `Missing: ${check.missing.join("; ")}.`));
    const buttons = el("div", "buttons");
    const add = el("button", "primary", "Add details");
    add.type = "button";
    add.addEventListener("click", () => $("idea").focus());
    const anyway = el("button", "secondary", "Analyze anyway");
    anyway.type = "button";
    anyway.addEventListener("click", () => analyze(true));
    buttons.append(add, anyway);
    nodes.push(buttons);
  } else {
    const p = el("p");
    p.append(el("strong", null, "This does not read as a business idea. "), check.reason);
    nodes.push(p, el("p", null, check.hint));
  }
  return nodes;
}

async function analyze(analyzeIfVague = false) {
  const idea = $("idea").value;
  if (!idea.trim()) {
    inputMessage([el("p", null, "Describe the idea first, or pick an example.")], true);
    return;
  }
  setBusy(true);
  inputMessage([]);
  const { status, data } = await request("POST", "/api/runs", {
    idea,
    language: languagePicker.value(),
    analyze_if_vague: analyzeIfVague,
  }).catch(() => ({ status: 0, data: {} }));
  if (status === 202) {
    startLive(data.run_id, 0);
  } else if (status === 409 && data.active_run_id) {
    startLive(data.active_run_id, null, detailText(data));
  } else {
    setBusy(false);
    const text = status === 0 ? "The local server does not answer. Is it still running?" : detailText(data);
    inputMessage([el("p", null, text)], true);
  }
}

// ---------- 2. Live analysis ----------

function setStage(id, state, text) {
  const stage = $(id);
  stage.hidden = false;
  stage.className = `stage is-${state}`;
  stage.querySelector(".stage-text").textContent = text;
}

function startTimer(elapsedS) {
  clearInterval(timer);
  const label = $("elapsed");
  if (elapsedS === null) {
    label.textContent = "";
    return;
  }
  const started = Date.now() - elapsedS * 1000;
  const tick = () => {
    const s = Math.round((Date.now() - started) / 1000);
    label.textContent = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  };
  tick();
  timer = setInterval(tick, 1000);
}

function waitingText() {
  const left = lensCounts.started - lensCounts.finished;
  return left > 0 ? `Waits for ${left} of ${lensCounts.started} analyses.` : "Starting…";
}

function onProgress(event) {
  const cards = $("cards");
  switch (event.stage) {
    case "input_check":
      if (event.status === "started") break;
      setStage("stage-input-check", event.status === "done" ? "done" : "failed",
        event.status === "done" ? capitalize(event.text) : "Unavailable; the idea is analyzed without it.");
      break;
    case "lens_fit":
      setStage("stage-lens-fit", event.status === "started" ? "running" : event.status,
        event.status === "started" ? "Checking which specialist analyses fit this idea…"
          : event.status === "done" ? capitalize(event.text) : "Unavailable; running every analysis.");
      break;
    case "lens": {
      let card = cards.querySelector(`[data-key="${CSS.escape(event.key)}"]`);
      if (event.status === "started") {
        if (!card) createCard(cards, event);
        lensCounts.started += 1;
      } else {
        if (!card) card = createCard(cards, event);
        updateCard(card, event);
        if (event.status !== "skipped") lensCounts.finished += 1;
      }
      setStage("stage-synthesis", "waiting", waitingText());
      break;
    }
    case "synthesis":
      if (event.status === "started") {
        setStage("stage-synthesis", "running", "Weighing the analyses against each other…");
      } else if (event.status === "done") {
        const stage = $("stage-synthesis");
        setStage("stage-synthesis", "done", "");
        stage.querySelector(".stage-text").append(verdictBadge(event.verdict_text, event.verdict));
      } else {
        setStage("stage-synthesis", "failed", "No overall verdict: the synthesis did not run.");
      }
      break;
    case "translation":
      if (event.status === "started") {
        setStage("stage-translation", "running", "Translating the report…");
      } else {
        setStage("stage-translation", event.status === "done" ? "done" : "failed",
          event.status === "done" ? "Translated copy ready." : "The translation failed; the English report is complete.");
      }
      break;
    default:
      break;
  }
}

function capitalize(text) {
  return text ? text[0].toUpperCase() + text.slice(1) : "";
}

function resetLive() {
  $("cards").replaceChildren();
  lensCounts = { started: 0, finished: 0 };
  setStage("stage-input-check", "running", "Checking that the idea is specific enough to analyze…");
  $("stage-lens-fit").hidden = true;
  setStage("stage-synthesis", "waiting", "Waits for the analyses.");
  $("stage-translation").hidden = true;
  $("live-message").hidden = true;
}

function startLive(runId, elapsedS, note) {
  resetLive();
  show("live-view");
  startTimer(elapsedS);
  if (note) {
    $("live-message").textContent = note;
    $("live-message").classList.remove("is-error");
    $("live-message").hidden = false;
  }
  followRun(`/api/runs/${runId}/events`, onProgress, (end) => finishRun(runId, end));
}

async function finishRun(runId, end) {
  clearInterval(timer);
  const { status, data } = await request("GET", `/api/runs/${runId}/result`).catch(() => ({ status: 0 }));
  if (status !== 200) {
    liveError(end.text || "The analysis stopped unexpectedly.");
    return;
  }
  if (data.error) {
    liveError(`The analysis stopped with an error: ${data.error}`);
    return;
  }
  setBusy(false);
  if (!data.analyzed) {
    show("input-view");
    inputMessage(needsDetailsMessage(data.input_check));
    return;
  }
  renderResult(runId, data);
  show("result-view");
}

function liveError(text) {
  setBusy(false);
  const box = $("live-message");
  box.classList.add("is-error");
  box.replaceChildren(el("p", null, text));
  const back = el("button", "secondary", "Back to the idea");
  back.type = "button";
  back.addEventListener("click", () => show("input-view"));
  box.append(back);
  box.hidden = false;
}

// ---------- 3. Result, 4. saving ----------

function section(title, wide = false) {
  const panel = el("section", wide ? "panel wide" : "panel");
  panel.append(el("h3", null, title));
  return panel;
}

function findingsList(items, emptyText) {
  if (!items.length) return el("p", "empty", emptyText);
  const list = el("ul");
  for (const item of items) {
    const li = el("li", null, item.text);
    if (item.lenses.length) li.append(el("span", "sources", item.lenses.join(", ")));
    list.append(li);
  }
  return list;
}

function plainList(items, ordered = false) {
  const list = el(ordered ? "ol" : "ul");
  for (const item of items) list.append(el("li", null, item));
  return list;
}

function assumptionsTable(items) {
  const table = el("table", "assumptions");
  const head = el("tr");
  for (const title of ["What must be true", "Cheapest test", "It is wrong if"]) head.append(el("th", null, title));
  table.append(head);
  for (const a of items) {
    const row = el("tr");
    row.append(el("td", null, a.statement), el("td", null, a.how_to_test), el("td", null, a.failure_signal));
    table.append(row);
  }
  const wrap = el("div", "table-wrap");
  wrap.append(table);
  return wrap;
}

function verdictBanner(synthesis) {
  const banner = el("div", `verdict-banner verdict-${verdictClass(synthesis.verdict)}`);
  banner.append(
    el("p", "verdict-label", "Overall verdict"),
    el("p", "verdict-text", synthesis.verdict_text),
    el("p", "verdict-meaning", capitalize(synthesis.verdict_meaning) + "."),
  );
  const confidence = el("p");
  confidence.append(el("strong", null, `${synthesis.confidence_text} confidence. `), synthesis.confidence_reason);
  banner.append(confidence, el("p", "verdict-summary", synthesis.summary));
  return banner;
}

function lensDetails(lens) {
  const details = el("details", lens.ok ? `lens-details verdict-${verdictClass(lens.verdict)}` : "lens-details is-failed");
  const summary = el("summary");
  const head = el("div", "lens-head");
  head.append(el("strong", null, lens.name));
  if (lens.ok) {
    head.append(verdictBadge(lens.verdict_text, lens.verdict), el("span", "confidence", `${lens.confidence_text} confidence`));
  } else {
    head.append(el("span", "badge badge-failed", "Failed"));
  }
  summary.append(head);
  if (lens.focus) summary.append(el("span", "muted", lens.focus));
  summary.append(el("span", null, lens.ok ? lens.summary : lens.text));
  details.append(summary);
  if (!lens.ok) return details;

  const body = el("div", "lens-body");
  const analysis = el("div", "markdown");
  analysis.innerHTML = renderMarkdown(lens.analysis); // escaped inside renderMarkdown
  body.append(analysis);
  body.append(el("h4", null, "Killer risk"), el("p", null, lens.killer_risk));
  body.append(el("p", "muted", `Confidence: ${lens.confidence_reason}`));
  body.append(el("h4", null, "Assumptions"), assumptionsTable(lens.key_assumptions));
  body.append(el("h4", null, "Next steps"), plainList(lens.next_steps, true));
  if (lens.red_flags.length) body.append(el("h4", null, "Problems noticed outside this analysis"), plainList(lens.red_flags));
  if (lens.warnings.length) body.append(el("h4", null, "Warnings"), plainList(lens.warnings));
  details.append(body);
  return details;
}

function fileUrl(runId, kind) {
  return `/api/runs/${runId}/files/${kind}`;
}

function saveLink(runId, file) {
  const link = el("a", "download", file.label);
  link.href = fileUrl(runId, file.kind);
  link.setAttribute("download", "");
  return link;
}

// The translated copy is shown on the page from its Markdown file, loaded on first view.
async function loadTranslation(runId, pane) {
  if (pane.dataset.state === "loading" || pane.dataset.state === "loaded") return;
  pane.dataset.state = "loading";
  pane.replaceChildren(el("p", "muted", "Loading the translation…"));
  try {
    const response = await fetch(fileUrl(runId, "translation"));
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const body = el("div", "markdown translated-report");
    body.innerHTML = renderMarkdown(await response.text()); // escaped inside renderMarkdown
    pane.replaceChildren(body);
    pane.dataset.state = "loaded";
  } catch {
    pane.dataset.state = "";
    pane.replaceChildren(el("div", "notice is-error",
      "The translation could not be shown here. Use the save button to open the file."));
  }
}

function tabButton(text, selected, controls) {
  const tab = el("button", "tab", text);
  tab.type = "button";
  tab.setAttribute("role", "tab");
  tab.setAttribute("aria-selected", String(selected));
  tab.setAttribute("aria-controls", controls);
  return tab;
}

// Above the report: which copy is shown (when there is a translation) and the button
// that saves exactly the copy on screen.
function reportToolbar(runId, files, translation, reportPane, translationPane) {
  const bar = el("div", "report-toolbar");
  const save = files.report ? saveLink(runId, files.report) : null;
  if (translation && files.translation) {
    const tabs = el("div", "tabs");
    tabs.setAttribute("role", "tablist");
    tabs.setAttribute("aria-label", "Report language");
    const original = tabButton("English report", true, reportPane.id);
    const translated = tabButton(`${translation.language} translation`, false, translationPane.id);
    const select = (showTranslation) => {
      original.setAttribute("aria-selected", String(!showTranslation));
      translated.setAttribute("aria-selected", String(showTranslation));
      reportPane.hidden = showTranslation;
      translationPane.hidden = !showTranslation;
      const file = showTranslation ? files.translation : files.report;
      save.textContent = file.label;
      save.href = fileUrl(runId, file.kind);
      if (showTranslation) loadTranslation(runId, translationPane);
    };
    original.addEventListener("click", () => select(false));
    translated.addEventListener("click", () => select(true));
    tabs.append(original, translated);
    bar.append(tabs);
  } else {
    bar.append(el("span", "report-title", "Report"));
  }
  if (save) bar.append(save);
  return bar;
}

function renderResult(runId, view) {
  const root = $("result");
  root.replaceChildren();
  const s = view.synthesis;
  const files = Object.fromEntries(view.downloads.map((d) => [d.kind, d]));
  const translation = view.translation && view.translation.made ? view.translation : null;

  const reportPane = el("div", "report-pane");
  reportPane.id = "report-pane";
  reportPane.setAttribute("role", "tabpanel");
  const translationPane = el("div", "report-pane");
  translationPane.id = "translation-pane";
  translationPane.setAttribute("role", "tabpanel");
  translationPane.hidden = true;
  root.append(reportToolbar(runId, files, translation, reportPane, translationPane), reportPane);
  if (translation) root.append(translationPane);

  if (s.ok) {
    reportPane.append(verdictBanner(s));
  } else {
    reportPane.append(el("div", "notice is-error", s.text));
  }
  if (view.input_note) reportPane.append(el("div", "notice", view.input_note));

  if (s.ok) {
    const grid = el("div", "result-grid");
    const risks = section("Killer risks");
    risks.append(findingsList(s.killer_risks, "None named."));
    const holds = section("What holds up");
    holds.append(findingsList(s.what_holds_up, "Nothing held up under scrutiny."));
    const deciding = section("What the verdict rests on");
    deciding.append(findingsList(s.deciding_factors, "Not stated."));
    const steps = section("Next steps");
    steps.append(plainList(s.next_steps, true));
    grid.append(risks, holds, deciding, steps);

    const conflicts = section("Where the analyses disagree", true);
    if (s.conflicts.length) {
      const list = el("ul");
      for (const c of s.conflicts) {
        const li = el("li", null, c.description);
        li.append(el("span", "conflict-resolution", `Resolution: ${c.resolution}`));
        list.append(li);
      }
      conflicts.append(list);
    } else {
      conflicts.append(el("p", "empty", "No conflicts between the analyses."));
    }
    const assumptions = section("What would need to be true", true);
    assumptions.append(assumptionsTable(s.key_assumptions));
    grid.append(conflicts, assumptions);
    reportPane.append(grid);
  }

  reportPane.append(el("h2", null, "The separate analyses"));
  for (const lens of view.lenses) reportPane.append(lensDetails(lens));
  for (const skipped of view.skipped_lenses) {
    reportPane.append(el("p", "muted", `${skipped.lens} was not run: ${skipped.reason}`));
  }

  // After the report, whichever copy is shown.
  const footer = el("div", "result-footer");
  if (view.translation && !view.translation.made) footer.append(el("p", "muted", view.translation.text));
  footer.append(el("p", "muted", `Estimated API cost of this run: $${view.cost_usd.toFixed(2)}.`));
  root.append(footer);
}

// ---------- Start ----------

async function init() {
  const { data } = await request("GET", "/api/options");
  const chips = $("examples");
  for (const example of data.examples) {
    const chip = el("button", "chip", example.title);
    chip.type = "button";
    chip.addEventListener("click", () => {
      $("idea").value = example.text;
      inputMessage([]);
      $("idea").focus();
    });
    chips.append(chip);
  }
  languagePicker = createLanguagePicker($("language-picker"), data.languages);
  const searching = data.web_search_lenses || [];
  if (searching.length) {
    const names = searching.join(" and ");
    const kind = searching.length === 1 ? "analysis" : "analyses";
    $("facts-note").textContent =
      `The ${names} ${kind} may search the web; the others answer from the model's own ` +
      "knowledge. Check market sizes, prices, competitors and laws before relying on them.";
  }
  $("analyze").addEventListener("click", () => analyze(false));
  $("again").addEventListener("click", () => {
    inputMessage([]);
    show("input-view");
  });

  // A run started before a reload (or in another tab) keeps going; follow it.
  const active = await request("GET", "/api/runs/active");
  if (active.data.run_id) {
    setBusy(true);
    startLive(active.data.run_id, active.data.elapsed_s);
  }
}

init();
