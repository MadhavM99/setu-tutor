"""Build the mid-submission report (HTML + PDF) from the repository's actual result files.

    python -m scripts.build_report          # docs/submission/report/SETU_mid_submission_report.{html,pdf}

Every number comes from a file in `reports/` or from git; nothing is typed in by hand. The PDF is printed with
headless Chrome (no other tool is installed).
"""
import html
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/submission/report"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
REPO = "https://github.com/MadhavM99/setu-tutor"
BRANCH = "redesign/phase0-spec"
COLORS = {"A": "#2a78d6", "B": "#eb6834", "C": "#1baf7a"}
NAMES = {"A": "A · Reverse learning (teach Raju)", "B": "B · Same content, no classmate", "C": "C · Conventional tutor"}


def load(p):
    return json.loads((ROOT / p).read_text(encoding="utf-8"))


def esc(s):
    return html.escape(str(s))


def f3(x):
    return "—" if x is None else f"{x:.3f}"


def ci(d):
    return f"{d['mean']:+.3f} [{d['ci95'][0]:+.3f}, {d['ci95'][1]:+.3f}]"


def table(head, rows, cls=""):
    h = "".join(f"<th>{esc(x)}</th>" for x in head)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<table class="{cls}"><thead><tr>{h}</tr></thead><tbody>{body}</tbody></table>'


def recall_chart(sim1, sim2) -> str:
    """Day-7 recall by condition, sim-0.1 vs sim-0.2 (main runs): bars with 95% CI whiskers, direct labels."""
    groups = [("sim-0.1 (original)", sim1["runs"]["main"]["conditions"]),
              ("sim-0.2 (FSRS memory, matched exchanges)", sim2["runs"]["main_matched_exchanges"]["conditions"]),
              ("sim-0.2 (matched time)", sim2["runs"]["main_matched_time"]["conditions"])]
    w, h, left, top, bottom = 760, 300, 52, 24, 58
    ymax = 0.4
    plot_h = h - top - bottom
    gw = (w - left - 20) / len(groups)
    bw = 34
    y = lambda v: top + plot_h * (1 - v / ymax)  # noqa: E731
    parts = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Day-7 recall by condition and simulator version">']
    for t in (0, 0.1, 0.2, 0.3, 0.4):
        parts.append(f'<line x1="{left}" x2="{w - 10}" y1="{y(t):.1f}" y2="{y(t):.1f}" stroke="#e8e6e0"/>'
                     f'<text x="{left - 8}" y="{y(t) + 4:.1f}" text-anchor="end" class="ax">{t:.1f}</text>')
    for gi, (label, cond) in enumerate(groups):
        x0 = left + gi * gw + (gw - 3 * bw - 2 * 6) / 2
        for ci_, k in enumerate("ABC"):
            m = cond[k]["recall_day7"]
            x = x0 + ci_ * (bw + 6)
            parts.append(f'<rect x="{x:.1f}" y="{y(m["mean"]):.1f}" width="{bw}" height="{y(0) - y(m["mean"]):.1f}" '
                         f'rx="4" fill="{COLORS[k]}"><title>{esc(NAMES[k])}: {m["mean"]:.3f}</title></rect>')
            lo, hi = m["ci95"]
            cx = x + bw / 2
            parts.append(f'<line x1="{cx}" x2="{cx}" y1="{y(hi):.1f}" y2="{y(lo):.1f}" stroke="#1f1c18" stroke-width="1.5"/>')
            parts.append(f'<text x="{cx}" y="{y(m["mean"]) - 7:.1f}" text-anchor="middle" class="val">{m["mean"]:.3f}</text>')
            parts.append(f'<text x="{cx}" y="{y(0) + 15:.1f}" text-anchor="middle" class="ax">{k}</text>')
        parts.append(f'<text x="{left + gi * gw + gw / 2:.1f}" y="{h - 14}" text-anchor="middle" class="grp">{esc(label)}</text>')
    parts.append("</svg>")
    legend = "".join(f'<span class="key"><i style="background:{COLORS[k]}"></i>{esc(NAMES[k])}</span>' for k in "ABC")
    return f'<figure>{"".join(parts)}<figcaption><div class="legend">{legend}</div>Figure 3. Simulated day-7 cue-free ' \
           f'recall (probability, mean with 95% CI; n = 100 simulated learners per condition). Simulation only — not ' \
           f'evidence about human learners.</figcaption></figure>'


def sim_rows(run, metrics):
    c = run["conditions"]
    return [[esc(NAMES[k])] + [f'{c[k][m]["mean"]:.3f} ± {c[k][m]["sd"]:.3f}' for m in metrics] for k in "ABC"]


def diff_rows(run, metrics):
    d = run["paired_differences"]
    return [[esc(k)] + [ci(d[k][m]) + (f' (d<sub>z</sub> {d[k][m]["cohens_dz"]})' if m.startswith("recall_day7") else "")
                        for m in metrics] for k in ("A-B", "A-C", "B-C")]


def ablation_rows(sim, runs, base):
    out = []
    for name in runs:
        r = sim["runs"][name]
        c, d = r["conditions"], r["paired_differences"]
        out.append([esc(name)] + [f3(c[k]["recall_day7"]["mean"]) for k in "ABC"] +
                   [ci(d["A-B"]["recall_day7"]), ci(d["A-C"]["recall_day7"])])
    return out


def build():
    sim1, sim2 = load("reports/simulation/results.json"), load("reports/simulation_v2/results.json")
    card = load("reports/scorecard-2026-10-31-heldout.json")
    base_run1 = load("reports/generation_baselines_run1_rate_limited.json")
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    log = subprocess.run(["git", "log", "--reverse", "--format=%h|%ad|%s", "--date=short"], cwd=ROOT,
                         capture_output=True, text=True).stdout.strip().splitlines()

    shots = [("01-home", "Home: one recommended lesson with its reason and time"),
             ("02-lesson-letter", "Lesson: one exercise per screen (letter intro)"),
             ("03-raju", "Raju (classmate) shows a sentence with one planted error"),
             ("04-coach-hint", "The coach (दीदी) gives a hint without the answer after a miss"),
             ("06-friend-scene", "रवि (native friend) speaks an approved line; comprehension question"),
             ("05-progress", "Progress: the learning ladder")]

    def shot(name, cap, n):
        return (f'<figure class="shot"><img src="../screenshots/{name}-desktop.png" alt="{esc(cap)}">'
                f'<img class="mob" src="../screenshots/{name}-mobile.png" alt="{esc(cap)} (mobile)">'
                f'<figcaption>Figure {n}. {esc(cap)} — desktop and mobile, captured from the running app.</figcaption></figure>')

    score_rows = [[m["id"], esc(m["target"].get("note", "")), f3(m["value"]) if isinstance(m["value"], float) else esc(m["value"] if m["value"] is not None else "—"),
                   esc(m["n"] or "—"), esc(", ".join(f"{k} {v}" for k, v in m["target"].items() if k != "note")),
                   {"pass": "pass", "fail": "<b>FAIL</b>", "not_measured": "not yet"}[m["status"]]]
                  for m in card["metrics"]]

    abl1 = ["main", "no_mechanism_bonus", "raju_forgetting_off", "direct_answers", "no_error_share_0", "no_error_share_0.4",
            "own_sentences_0", "sensitivity_half_life_4"]
    abl2 = list(sim2["runs"])

    tool = base_run1["methods"]["tool"]
    commits_rows = [[esc(h), esc(d), esc(s)] for h, d, s in (x.split("|", 2) for x in log)]

    body = f"""
<header class="title">
  <p class="kicker">Mid-submission report · 31 October 2026 · final submission due 15 November 2026</p>
  <h1>SETU: a Hindi-first Telugu tutor in which the learner teaches an AI classmate</h1>
  <p class="sub">Implementation of “Teaching the Machine in Your Mother Tongue” (paper v8): reverse learning with a
  weaker classmate (Raju), a hint-only coach and a native friend, on a deterministic, auditable learning core.</p>
  <p class="meta">Code: <a href="{REPO}/tree/{BRANCH}">{REPO}</a> · branch <code>{BRANCH}</code> · commit
  <code>{commit}</code> · {len(log)} commits</p>
</header>

<section class="summary">
<h2>Summary</h2>
<ul>
<li><b>Built:</b> a working web application (FastAPI + PostgreSQL) with the full learning ladder — Telugu letters,
aksharas, words, phrases, Raju correction practice, spaced re-teaching, placement, a progress ladder and conversation
scenes — plus a teacher console for native review and for settling answers the checker could not judge. A redesigned
learner interface recommends one lesson at a time.</li>
<li><b>Safety architecture:</b> a deterministic checker (four verdicts, no model), a leak filter, one database role that
alone may change learning state, a hash-chained event log, and Hindi-only learner text enforced by a lint.
1,096 automated tests pass (plus 138 legacy).</li>
<li><b>Real AI:</b> Raju, the coach and the friend call a hosted model (Google <code>gemini-3.5-flash</code>, OpenAI-compatible
API); real calls were verified in the live app. Model output is shown only after deterministic validation; otherwise the
approved fallback is shown.</li>
<li><b>Experiments:</b> two versions of an exploratory simulated-learner study (A/B/C, 100 simulated learners per
condition, 7 and 11 runs incl. ablations). The improved version reverses the original ranking: reverse learning is
<i>not</i> better than a conventional tutor in either, and the outcome depends on the memory model. Simulation results
are not evidence about people.</li>
<li><b>Not yet valid:</b> the 29-case real-model generation baseline (the API key's free-tier quota ran out mid-run);
native-speaker review of the Telugu content (0 items reviewed); the human pilot.</li>
</ul>
</section>

<h2>1. Progress</h2>
<h3>1.1 What exists</h3>
{table(["Phase", "Content", "Implementation", "Evaluation"], [
["0 · Specification", "PRD, learning ladder L0–L5, session/exchange spec, architecture, data model, ~230-row traceability matrix to the paper, 7 ADRs", "complete", "reviewed and approved"],
["1 · Foundations", "PostgreSQL with 5 roles; OutcomeWriter (only writer of learning state); hash-chained append-only ledger; pseudonymous accounts; Hindi string catalog + lint; content importer with provenance", "complete", "contract tests"],
["2 · Deterministic core", "Normaliser (Devanagari↔Telugu typing), checker with 4 verdicts, tokenizer/TMR, leveler v0, leak filter, planner, FSRS + mastery tracker, Stage-A suite (663 cases, frozen held-out split), scorecard, OKF export", "complete", "held-out scorecard (§5.1)"],
["3 · Learner slices S1–S8", "Letters, aksharas, words (cognates, false friends), phrases in scenes, Raju correction exchange with hint ladder and “why?”, spaced re-teaching, placement test-out and progress ladder, conversation scenes", "complete", "module tests; no learners yet"],
["4.1 · Teacher console", "Native review (two distinct native approvals, exact version, history); unsure-answer queue settled by signed teacher resolutions", "complete", "tests"],
["4.2 · Rule review", "Rule review form, promotion as immutable versions, variant review, rater agreement (Cohen's κ)", "implemented, docs pending", "tests"],
["4 · Agents", "Model client (local or hosted, opt-in), Raju generation loop (tool-assisted / resampling / prompt-only), coach, friend; logging of model, latency, tokens, rejections", "complete", "real calls verified; baseline comparison pending (§5.4)"],
["UI redesign", "One recommended lesson on the home screen, focused lesson shell, Raju/coach/friend personas, 4-item navigation, new design system", "complete", "checked in a real browser, desktop and mobile"],
["Research", "Simulator sim-0.1 and sim-0.2 (A/B/C + ablations), generation-baseline harness", "complete", "run (§5.2–5.3)"],
["5 · Speech, extended red team", "—", "deferred", "—"],
["6 · Human pilot", "—", "deferred", "—"]])}
<h3>1.2 Architecture</h3>
<figure class="arch"><pre>
learner text ─► normaliser ─► checker ─► verdict (correct | partial | wrong | unsure) ─► OutcomeWriter ─► learning state
                              (no model)                                    unsure ─► teacher queue      (only DB writer)
                                                                                                          + hash-chained log
hosted / local model ─► proposal ─► leak filter / approved-line check ─► shown to learner   (else: approved fallback)
   Raju: one sentence with exactly the planned error · Coach: Hindi hint without the answer · Friend: picks an approved line
</pre><figcaption>Figure 1. Trust boundaries. The model can only propose text; it cannot grade, change mastery, change
Raju's memory, write the log or change schedules (enforced by imports, database roles and tests).</figcaption></figure>
<h3>1.3 The application</h3>
{"".join(shot(n, c, i + 2) for i, (n, c) in enumerate(shots[:3]))}
{"".join(shot(n, c, i + 5) for i, (n, c) in enumerate(shots[3:]))}
<p class="note">Screenshots come from an isolated demo database in which content was approved by demo reviewer
accounts (a banner says so on every page). Real learners see only content approved by two native Telugu speakers;
none has been reviewed yet.</p>

<h2>2. Datasets</h2>
{table(["Dataset", "Use in this project now", "Size (counted here)", "Licence"], [
["Team rule bank (paper's error bank, two repositories)", "Rules and items for Raju and the checker", "25 rules / 49 items; all draft, all with open validation issues", "team-owned; model-drafted, unreviewed"],
["Script and vocabulary content", "Ladder L0–L3 and scenes", "48 letters, 489 aksharas, 28 words, 32 phrases, 5 scenes, 4 scene scripts (12 lines)", "team-owned; unreviewed"],
["Stage-A test suite", "Checker, leak filter and attack tests; scorecard", "663 generated cases; 30% held-out split frozen", "team-owned"],
["Teacher label sheet", "Checker–teacher agreement (M-16)", "145 rows, unlabelled", "team-owned"],
["Synthetic learner profiles", "Simulator", "20 profiles × 5 seeds per condition", "generated"],
["IndicCorp v2", "Planned: Telugu word frequencies for word order", "not downloaded", "to check"],
["IndicGEC (Telugu)", "Planned: checker robustness", "not downloaded", "to check"],
["LTRC Hindi–Telugu parallel corpus", "Planned: how contrasts appear in translation", "not obtained", "commercial use to confirm"],
["Aksharantar / IndicXlit", "Romanised input (adapter only; romanised answers go to the teacher)", "model not wired in", "to check"],
["Kanojia et al. 2020 cognates/false friends", "Planned: shared words; 4 false friends drafted by the team", "not obtained", "to check"],
["Tenepalukulu / Vennela textbooks", "Planned: topic order only, no copying", "—", "permission needed"]])}
<p>No dataset size is reported unless it was counted in this repository; licences marked “to check” are not yet
confirmed. Details: <code>docs/submission/dataset_register.md</code>.</p>

<h2>3. Baseline experiments</h2>
<h3>3.1 Learning conditions (simulated learners)</h3>
{table(["Condition", "What the learner does", "Matched on"], [
[esc(NAMES["A"]), "Corrects Raju's planted errors (real planner: planted, no-error and ≥ 2 own-sentence turns); “why?” after every third fix", "same rules, order, profiles, feedback, forgetting"],
[esc(NAMES["B"]), "Sees the same erroneous sentence, its correction and explanation, then types the correction; same own-sentence turns", "as A"],
[esc(NAMES["C"]), "Writes the sentence for the Hindi meaning; the tutor corrects the learner's own errors", "as A"]])}
<p>Three comparisons: A vs B isolates reverse learning; A vs C compares SETU with conventional tutoring; B vs C the
remainder. 20 matched profiles × 5 seeds = 100 simulated learners per condition, practice on days 0–2, tests on days
0, 1, 2 and 7 (virtual time). Outcomes: cue-free recall, production, transfer to unseen meanings, error detection,
vocabulary, hints, wrong corrections, false alarms, time and expected model calls.</p>
<h3>3.2 Raju generation baselines (real model)</h3>
<p>Prompt-only (one draft), blind resampling (≤ 3 drafts) and tool-assisted generation (≤ 3 drafts; the filter's reasons
are fed back) on the same 29 planting cases; metrics: valid rate, planting precision, leak rate, vocabulary violations,
fallback rate, calls, latency, tokens. The same harness evaluates the coach (leak, Hindi-only) and the friend (approved
pick, prompt injection, outage).</p>
<h3>3.3 Deterministic modules (Stage A)</h3>
<p>The frozen held-out split of the Stage-A suite ({card['cases']} cases: {esc(', '.join(f'{v} {k}' for k, v in card['groups'].items()))}) against thresholds fixed
in advance (results in §5.1).</p>

<h2>4. Ablations</h2>
{table(["Ablation", "Hypothesis", "Configuration", "Status"], [
["Raju forgetting on/off", "Re-planting forgotten rules adds spaced retrieval", "forgetting off", "run (both simulators)"],
["Progressive hints vs direct answers", "Hints before the answer improve retention", "answer shown after a miss", "run"],
["No-error turn share", "No-error turns trade practice for detection", "0 / 0.2 / 0.4", "run"],
["Own sentences retained vs removed", "Own sentences carry production practice", "own_sentences_min 2 vs 0", "run"],
["A-only assumed effects", "How much of A's result is assumed (self-explanation, noticing)", "on vs off", "run"],
["Memory sensitivity", "Floor effects / memory model", "half-life 4 d (v0.1); FSRS stability ×0.5 / ×2 (v0.2)", "run"],
["Testing effect removed (v0.2)", "Does A–B depend on retrieval > restudy?", "all gains equal", "run"],
["Matched time (v0.2)", "Unequal time on task", "300 s per session", "run"],
["Generation method (real model)", "Tool loop beats resampling and prompt-only", "§3.2", "<b>pending</b> (quota)"]])}

<h2>5. Results</h2>
<h3>5.1 Deterministic modules — held-out Stage A</h3>
{table(["Metric", "What", "Value", "n", "Target", "Status"], score_rows, "small")}
<p>Five gate metrics pass; the checker's unsure rate (M-09) fails and is not relaxed; the rest need model output or
learners. These cases were generated from the team's own content and are optimistic.</p>

<h3>5.2 Original simulation (sim-0.1)</h3>
{table(["Condition", "Recall d0", "Recall d7", "Transfer d7", "Detection d7"], sim_rows(sim1["runs"]["main"], ["recall_day0", "recall_day7", "transfer_day7", "detection_day7"]))}
{table(["Paired difference", "Recall d7 (95% CI)", "Transfer d7", "Detection d7"], diff_rows(sim1["runs"]["main"], ["recall_day7", "transfer_day7", "detection_day7"]))}
<p>Ablations (day-7 recall):</p>
{table(["Run", "A", "B", "C", "A − B", "A − C"], ablation_rows(sim1, abl1, "main"), "small")}

<h3>5.3 Improved simulation (sim-0.2)</h3>
<p>A validity review of sim-0.1 found (i) an ad-hoc 1.5-day memory half-life that drove day-7 recall to ≈ 0.05,
(ii) two A-only effects switched on by default, (iii) unequal time on task (A 920 s vs B 765 s). sim-0.2 uses the
project's own FSRS scheduler as the memory model with the app's rating rules, switches the A-only effects off, and
reports matched-exchange and matched-time designs. Parameters were fixed before running.</p>
{table(["Condition (matched exchanges)", "Recall d0", "Recall d7", "Production d7", "Transfer d7", "Vocabulary d7"], sim_rows(sim2["runs"]["main_matched_exchanges"], ["recall_day0", "recall_day7", "production_day7", "transfer_day7", "vocabulary_day7"]))}
{table(["Paired difference", "Recall d7 (95% CI)", "Production d7", "Transfer d7"], diff_rows(sim2["runs"]["main_matched_exchanges"], ["recall_day7", "production_day7", "transfer_day7"]))}
{recall_chart(sim1, sim2)}
<p>All runs (day-7 recall):</p>
{table(["Run", "A", "B", "C", "A − B", "A − C"], ablation_rows(sim2, abl2, "main_matched_exchanges"), "small")}

<h3>5.4 Real-model measurements</h3>
{table(["Call", "Result"], [
["Smoke test", "200 OK · gemini-3.5-flash · 2.6 s with reasoning_effort=none (without it, reasoning tokens truncated the JSON)"],
["Requested model gemini-3.8-flash", "503 “high demand” (3 attempts); gemini-3.7-flash: 429"],
["Raju in the live app", "200 OK · 13.7 s · 146 + 14 tokens · proposed <span lang=te>నేను నహీ వెళ్తాను</span> · passed the leak filter · shown"],
["Coach in the live app", "200 OK; no answer leaked, but unseen Telugu words were mixed into the Hindi → new rule: model hints may contain no Telugu"],
["Coach and friend under quota exhaustion", "429 → generic hint and approved line shown (fallback works)"],
["Outage test (invalid key)", "Raju → bank sentence; coach → generic hint; friend → approved line"],
["29-case baseline, run 1", f"rate-limited: tool-assisted {round(tool['valid_rate'] * 29)}/29 passed the filter (planting precision {tool['planting_precision']:.2f}; drafts with answer leaks in {round(tool['leak_rate'] * 29)} cases were blocked); resampling, prompt-only, coach and friend received no model replies. <b>Not used as a comparison.</b>"]])}

<h3>5.5 What the results show</h3>
<ul>
<li><b>The deterministic layer works as specified</b> on held-out cases (no false acceptances of planted errors, no
rejection of correct fixes, no successful attack), except that it is too often unsure.</li>
<li><b>The simulations do not support a claim that reverse learning helps.</b> sim-0.1: A beats B (+0.027) but is slightly
below C (−0.005). sim-0.2 (better memory model, nothing assumed in A's favour): A is lowest (A−B −0.076, A−C −0.053),
in every sensitivity run. The mechanism: correcting a sentence that is mostly visible is cued, and missed planted errors
are failed retrievals. The two versions disagree because they model memory differently; neither is evidence about people.</li>
<li><b>Design implications for the final phase:</b> make Raju turns demand more cue-free production (own sentences after
each correction; correction from the Hindi meaning, not only from Raju's sentence), and test this in the pilot.</li>
<li><b>Real model:</b> integration works and the filters catch real failure modes (answer-leaking drafts, unseen Telugu in
hints); the method comparison still has to be run.</li>
</ul>

<h2>6. Challenges</h2>
{table(["Challenge", "Evidence"], [
["Telugu content validation and native reviewers", "0 of 25 rules, 49 items, 48 letters, 489 aksharas, 28 words, 32 phrases, 12 scene lines reviewed; all rules have open validation issues"],
["Model access", "Requested model overloaded (503); free-tier quota exhausted during the baseline run (429); local GPU host not available"],
["Hallucinated or mixed-language output", "Real coach hint mixed unseen Telugu into Hindi; Raju drafts leaked the answer in 2 of 29 cases"],
["Checker uncertainty", "M-09 unsure rate 0.182 > 0.15"],
["Simulator validity", "Results depend on the memory model; one modelling bug was found and rejected (kept on file)"],
["Reverse learning may reduce production", "Both simulations: A is not better than C; Raju corrections are partly cued"],
["Integration", "Many steps before Raju appears for a new learner; demo needed a lower start threshold"]])}

<h2>7. Mitigation plans</h2>
{table(["Challenge", "Mitigation", "When"], [
["Native review", "Recruit 2 native Telugu reviewers + 1 tie-breaker; batch review in the built console; fix rule explanations and answer-revealing titles first (25 rules)", "days 1–6"],
["Model access", "Enable billing or a second key; rerun the 29-case baseline throttled (harness records every error, counts only answered cases)", "days 1–3"],
["Model output quality", "Keep deterministic filters as the gate; add the no-Telugu-hint rule (done); report leak and fallback rates from the rerun", "days 2–4"],
["Checker uncertainty", "Teacher labels on the 145-row sheet; decide the “incomplete → wrong” rule from those labels, not from the held-out set", "days 4–8"],
["Simulator validity", "Calibrate learning parameters against literature ranges; keep both versions and all rejected runs; report as exploratory", "days 7–10"],
["Production in reverse learning", "Add an own-sentence step after each correction and a correction mode from the Hindi meaning; run them as ablations and in the pilot", "days 5–9"],
["Integration", "Session composer that mixes review, new items, Raju and own sentences in one daily lesson", "days 6–10"]])}

<h2>8. Timeline to the final submission (15 days)</h2>
{table(["Days", "Dates", "Work", "Output"], [
["1–3", "1–3 Nov", "Rerun real-model baselines (Raju 3 methods, coach, friend) with a working quota; finish slice 4.2 docs", "baseline tables with real measurements"],
["1–6", "1–6 Nov", "Native review of rules and core content in the teacher console; fix rule explanations", "first approved rules visible to real learners"],
["4–8", "4–8 Nov", "Teacher labels → checker agreement κ (M-16) and the M-09 decision; red-team prompts on live output", "updated scorecard"],
["5–10", "5–10 Nov", "Raju production changes (own sentence after correction; correction from meaning) + session composer; simulator calibration and rerun", "new ablations"],
["8–12", "8–12 Nov", "Pilot with 3–5 adult learners (consent in person; pre-test, sessions, post-test; one-week delayed test only if time allows)", "descriptive pilot results"],
["12–14", "12–14 Nov", "Analysis, final report, demo video, documentation", "final report"],
["15", "15 Nov", "Final submission", "report + GitHub"]])}
<p><b>Deferred beyond the final submission:</b> Phase 5 (speech input and output, extended safety evaluation) and the
full Phase 6 study (Latin square, blind marking, one-week delayed and transfer tests at scale). They are not marked complete.</p>

<h2>9. Limitations</h2>
<ul>
<li>Simulation results are not evidence that SETU or reverse learning helps human learners; simulated learners are not participants.</li>
<li>No Telugu content has native-speaker review; real learners see nothing outside the demo database.</li>
<li>The real-model method comparison is incomplete; individual real calls only.</li>
<li>Stage-A cases were generated from the team's own content and are optimistic.</li>
<li>Hosted inference sends content (rule titles, Hindi meanings, permitted words, Raju's sentence, approved lines) to the
provider; no learner answer, identity or free text is sent.</li>
</ul>

<h2>10. Reproducibility</h2>
<pre>git clone {REPO} &amp;&amp; git checkout {BRANCH}
docker compose up -d db                      # PostgreSQL
.venv/bin/python -m pytest                   # 1,096 tests (real PostgreSQL)
scripts/run_demo.sh                          # app at http://127.0.0.1:8000 (isolated demo DB)
python -m setu.research.scorecard --split heldout
python -m setu.research.simulator            # sim-0.1  → reports/simulation/results.json
python -m setu.research.simulator_v2         # sim-0.2  → reports/simulation_v2/results.json
SETU_LLM_URL=… SETU_LLM_MODEL=… SETU_LLM_API_KEY=… SETU_LLM_ALLOW_HOSTED=1 SETU_LLM_REASONING=none \\
  python -m setu.research.generation_baselines
python -m scripts.build_report               # this report</pre>

<h2>Appendix A. Commits</h2>
{table(["Commit", "Date", "Message"], commits_rows, "small")}
"""
    css = """
@page { size: A4; margin: 16mm 14mm; }
:root { --ink:#1f1c18; --muted:#5e574d; --line:#e6dfd3; --primary:#1d6b62; }
body { font: 10.5pt/1.5 "Noto Sans", "Noto Sans Devanagari", "Noto Sans Telugu", -apple-system, sans-serif; color: var(--ink); max-width: 820px; margin: 24px auto; padding: 0 16px; }
h1 { font-size: 21pt; line-height: 1.25; margin: .2em 0 .3em; }
h2 { font-size: 14pt; color: var(--primary); margin: 1.6em 0 .5em; border-bottom: 1.5px solid var(--line); padding-bottom: .2em; }
h3 { font-size: 11.5pt; margin: 1.2em 0 .4em; }
.kicker { color: var(--primary); font-weight: 700; font-size: 9.5pt; margin: 0; }
.sub { font-size: 11.5pt; color: var(--muted); }
.meta { font-size: 9pt; color: var(--muted); }
.summary { background: #f7f3ec; border-radius: 10px; padding: .4em 1.2em .6em; }
.summary h2 { border: 0; margin-top: .6em; }
table { border-collapse: collapse; width: 100%; margin: .5em 0 1em; font-size: 9pt; page-break-inside: auto; }
tr { page-break-inside: avoid; }
th, td { text-align: left; vertical-align: top; padding: 4px 6px; border-bottom: 1px solid var(--line); }
th { background: #f7f3ec; font-weight: 700; }
table.small { font-size: 8pt; }
code, pre { font-family: "SFMono-Regular", Menlo, monospace; font-size: 8.5pt; }
pre { background: #f7f3ec; padding: 8px 10px; border-radius: 6px; white-space: pre-wrap; }
figure { margin: .8em 0 1.2em; page-break-inside: avoid; }
figcaption { font-size: 8.5pt; color: var(--muted); margin-top: .3em; }
.shot { display: grid; grid-template-columns: 3fr 1fr; gap: 8px; align-items: start; }
.shot img { width: 100%; border: 1px solid var(--line); border-radius: 6px; }
.shot figcaption { grid-column: 1 / -1; }
svg { width: 100%; height: auto; font-family: inherit; }
svg .ax { font-size: 10px; fill: #5e574d; } svg .val { font-size: 10px; fill: #1f1c18; font-weight: 700; }
svg .grp { font-size: 11px; fill: #1f1c18; }
.legend { display: flex; gap: 14px; flex-wrap: wrap; margin-bottom: 4px; color: var(--ink); }
.key i { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 5px; vertical-align: -1px; }
.note { font-size: 9pt; color: var(--muted); }
a { color: var(--primary); }
"""
    OUT.mkdir(parents=True, exist_ok=True)
    page = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" '
            f'content="width=device-width, initial-scale=1"><title>SETU mid-submission report</title>'
            f'<style>{css}</style></head><body>{body}</body></html>')
    html_path = OUT / "SETU_mid_submission_report.html"
    html_path.write_text(page, encoding="utf-8")
    pdf_path = OUT / "SETU_mid_submission_report.pdf"
    subprocess.run([CHROME, "--headless=new", "--no-pdf-header-footer", f"--print-to-pdf={pdf_path}",
                    html_path.as_uri()], check=True, capture_output=True, timeout=120)
    return html_path, pdf_path


if __name__ == "__main__":
    for p in build():
        print(p)
