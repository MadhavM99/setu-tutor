"""Build the final-submission paper (two-column, same layout as the mid-submission paper).

    python -m scripts.build_final_paper     # docs/submission/report/SETU_final_paper.{html,pdf}

Numbers come from reports/ (see docs/submission/drafts/faviana_analysis_20_23.md for the file behind each one).
The recall chart is reused from the mid-submission report; screenshots are in docs/submission/screenshots/.
"""
import base64
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/submission/report"
SHOTS = ROOT / "docs/submission/screenshots"

CSS = """
@page { size: Letter; margin: 17mm 15mm; }
body { font: 10.4pt/1.32 "Liberation Serif", "Times New Roman", "Noto Sans Devanagari", "Noto Sans Telugu", serif; color: #000; margin: 0; }
header { text-align: center; column-span: all; margin-bottom: 8px; }
h1 { font-size: 13.5pt; line-height: 1.2; margin: 0 0 6px; }
.authors { display: flex; justify-content: space-around; font-size: 9.5pt; margin: 4px 0; }
.authors b { display: block; } .small { font-size: 8.6pt; }
main { column-count: 2; column-gap: 7mm; text-align: justify; hyphens: auto; }
h2 { font-size: 10.6pt; margin: 9px 0 3px; break-after: avoid; } h3 { font-size: 9.6pt; margin: 6px 0 2px; break-after: avoid; }
p { margin: 0 0 4px; } ul { margin: 2px 0 4px 0; padding-left: 14px; } li { margin: 0 0 2px; }
.abs { margin: 0 8mm 6px; text-align: justify; font-size: 9.6pt; column-span: all; }
.abs h2 { text-align: center; margin-top: 2px; }
table { border-collapse: collapse; width: 100%; font-size: 8.6pt; margin: 3px 0 2px; break-inside: avoid; text-align: left; hyphens: manual; }
th, td { padding: 1.5px 3px; vertical-align: top; } thead th { border-top: 1.2px solid #000; border-bottom: .8px solid #000; }
tbody tr:last-child td { border-bottom: 1.2px solid #000; }
.cap { font-size: 8.8pt; margin: 0 0 6px; } code { font-family: "DejaVu Sans Mono", monospace; font-size: 7.6pt; }
figure { margin: 4px 0 6px; break-inside: avoid; } figure img { width: 100%; } figure.wide { column-span: all; }
.shots { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; } .shots img { border: .5px solid #999; }
svg { width: 100%; height: auto; } svg .ax { font-size: 10px; fill: #333; } svg .val { font-size: 10px; fill: #000; font-weight: 700; } svg .grp { font-size: 11px; }
.legend { display: flex; gap: 8px; flex-wrap: wrap; font-size: 7.5pt; } .key i { display: inline-block; width: 8px; height: 8px; margin-right: 3px; }
.ref { padding-left: 10px; text-indent: -10px; font-size: 8.3pt; margin: 0 0 2px; text-align: left; }
"""


def img(name, alt):
    p = SHOTS / name
    return f'<img alt="{alt}" src="data:image/png;base64,{base64.b64encode(p.read_bytes()).decode()}">'


def table(head, rows, cap):
    h = "".join(f"<th>{x}</th>" for x in head)
    b = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<table><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table><p class="cap">{cap}</p>'


def build() -> str:
    mid = (OUT / "SETU_mid_submission_report.html").read_text(encoding="utf-8")
    chart = (re.search(r'<div class="legend">.*?</div>', mid, re.DOTALL).group(0)
             + re.search(r'<svg viewBox="0 0 760 300".*?</svg>', mid, re.DOTALL).group(0))
    P = []
    P.append("""<header><h1>SETU: Reverse Learning with a Rule-Governed AI Classmate<br>for Hindi-Speaking Learners of Telugu — Final Report</h1>
<div class="authors"><div><b>Madhav Malhotra</b>2026900003</div><div><b>Kushal Karan</b>2025204010</div>
<div><b>Faviana Noronha</b>2025900018</div><div><b>Shaik Areesh</b>2026909008</div></div>
<div class="small">International Institute of Information Technology, Hyderabad · Language Models and Agents, Monsoon 2026 · Team Token Guessers<br>
Code: <code>https://github.com/MadhavM99/setu-tutor</code> (branch <code>faviana-noronha</code>; setup and reproduction steps in the README)</div></header>""")

    P.append("""<div class="abs"><h2>Abstract</h2>SETU is a tutor for Hindi speakers who want to learn Telugu. The learner climbs a ladder from letters to words,
phrases, sentences and short conversations. At the sentence stage the learner corrects Raju, an AI classmate who makes the mistakes a Hindi speaker
makes in Telugu. Raju's knowledge sits in a database, not inside a model: language models only write text, and fixed rules decide what is shown and what
counts as learning (<i>models write, rules decide</i>). Since the mid-submission we measured five model capabilities against baselines on the same frozen
cases: tool calling, stepwise reasoning, retrieval (RAG), fine-tuning, and one agent against several. Tool calling made Raju's sentences valid 0.93–0.97 of
the time against 0.72 for prompting alone, at about seven times the tokens. Reasoning steps, retrieval and multi-agent roles did not improve accuracy; a
fine-tune was a no-go for lack of checked training data. No model decided a grade in the multi-agent setup (0 verdicts, against 65 in a single agent). The
checker agrees with native-speaker labels less than a prompt-only judge does (κ 0.15 against 0.46), and one of our own checks failed. We also built a
beginner on-ramp (path map, word pictures, a match game, an early introduction of Raju) and report it as built but not evaluated. Every learner result
is simulated, and the two simulations disagree. Code and reproduction steps: <code>github.com/MadhavM99/setu-tutor</code> (README).</div>""")

    P.append("<main>")

    P.append("""<h2>1 Introduction</h2>
<p>Hindi and Telugu come from different language families, but they share many Sanskrit words and their scripts line up almost letter for letter. A Hindi
speaker already knows a lot that helps. They also bring habits that hurt: a Hindi question word such as क्या at the start of a yes/no question, a
Hindi-style negative, carried-over gender agreement. Most language apps ignore both.</p>
<p>Our idea is reverse learning: people often learn better when they have to teach. The learner spots and fixes Raju's mistakes. Raju is always one step
behind: he uses only words the learner has seen, each sentence has exactly one mistake, and it is on a rule the learner has shown they know but Raju has
not learned yet. When the learner fixes it, Raju learns the rule; when the learner forgets a rule, Raju forgets it too.</p>
<p>Two problems stand in the way. A beginner cannot correct anyone until they know enough Telugu, so the tutor needs an on-ramp. And a language model asked
to play a weak classmate knows too much, so it leaks correct forms and words the learner has not met. We therefore keep Raju's knowledge as data and let
the model only phrase sentences that a set of checks accepts or rejects. We ask whether correcting such a classmate improves recall, and which model
capabilities can be used around him without giving up that control.</p>
""")

    P.append("""<h2>2 Literature Review</h2>
<p><b>AI students and learning by teaching.</b> Prompted language-model "students" know too much and drift back to expert behaviour (the competence paradox; Jin et al., 2024; Yuan et al.,
2026). Students work harder for an agent they believe they are teaching (Chase et al., 2009), but in a randomised cross-age tutoring trial the tutors gained
(+0.24) and the tutees did not (−0.07; Thurston et al., 2021), and learning from others' errors helps only weakly on average (g = 0.136; Alemdag et al.,
2025). Contrastive analysis has long been criticised for weak prediction (Wardhaugh, 1970; Berzak et al., 2015), so every predicted error is a hypothesis.
We found no Hindi↔Telugu learner-error corpus; the only study we located is a 1978 thesis, which reports difficulty, not errors: 78% of 262 Hindi teachers
said gender is hard for Telugu speakers (Chinnappa, 1978).</p>
<p><b>Teachable agents.</b> In Betty's Brain students teach an agent a concept map and then question it (Biswas et al., 2005); language-model versions let
novices debug an agent's buggy code (Ma et al., 2023; Jin et al., 2024). We differ in keeping the agent's knowledge outside the model, so a filter and a
checker, not the model, control what it knows.</p>
<p><b>Contrast and transfer.</b> Typology-based prediction of L1 error shares (Berzak et al., 2015) and parallel contrastive models that test contrasts on
learner corpora in both directions (Hasselgård and Ebeling, 2018) motivate our error bank, but transfer can be asymmetric and the predictions are
hypotheses. The subcontinent is a linguistic area where contact brought language families closer (Kunchukuttan and Bhattacharyya, 2020), which is why we
check, and do not assume, that Hindi and Telugu differ in the predicted ways.</p>
<p><b>Memory and scheduling.</b> Spaced repetition and knowledge tracing are standard (Corbett and Anderson, 1994; Ye et al., 2022); testing beats restudy
(Roediger and Karpicke, 2006). SETU uses FSRS, and its simulators use the same memory model.</p>
<p><b>Model capabilities.</b> We evaluate tool use, step-by-step reasoning, retrieval, fine-tuning and multi-agent roles as ways to build Raju and the coach,
each against a plain baseline on the same frozen cases.</p>""")

    P.append("""<h2>3 Datasets Created and Used</h2><p>Content is still our own draft bank: 25 rules (15 HI→TE, 10 TE→HI), 48 letters, 489 aksharas, 28 words, 32 chunks, 4 scene scripts, none independently reviewed (one bilingual team member checked the rules). Evaluation sets are small and frozen: 29 planting cases (58 for the reasoning set), 185 held-out checker cases, and a 145-row teacher
label sheet of which 50 answers carry native labels. IndicCorp, IndicGEC and the other planned corpora remain unused.</p>
<h3>3.1 Error bank and typology</h3>
<p>Before writing rules we asked whether overall similarity could replace a contrast table. It cannot, and the two databases disagree: in WALS Hindi and
Telugu agree on 32 of 47 shared features (κ = 0.442; Telugu is 38th of 691 languages most like Hindi, but 15 of the 32 agreements are word order); in Grambank
they agree on 82 of 124 (κ = −0.025, no better than chance; 796th of 2,245). So rules are derived feature by feature and treated as hypotheses.</p>""")

    P.append(table(["Contrast", "Hindi", "Telugu", "Expected error"], [
        ["Polar question", "क्या at the start", "marker at the end", "HI→TE: initial particle"],
        ["Negation", "separate नहीं before the verb", "affix after the stem", "HI→TE: negator as a word"],
        ["Copula", "है required", "can be omitted", "TE→HI: है dropped"],
        ["Gender", "agrees on adjectives, verbs", "no agreement on adjectives", "TE→HI: wrong gender"],
        ["We", "हम (one form)", "మనం / మేము", "HI→TE: one form for both"],
        ["Ergative ने", "perfective transitive subject", "none", "TE→HI: ने dropped (hard for 76% of teachers, 1978)"],
    ], "Table 1: Examples from the contrast table (13 areas in all). These are predictions; no rule is yet observed in learner data."))

    P.append("""<h2>4 Methodology</h2>
<h3>4.1 The main rule: models write, rules decide</h3>
<p>Every answer goes through a normaliser (which, for example, converts Telugu typed on a Hindi keyboard) and a checker that uses no model. It gives one of
four verdicts: correct, partial, wrong or unsure. Only one component, the OutcomeWriter, may change what the system believes the learner knows, and it
accepts only the checker's verdicts or a signed teacher decision. This is enforced by database permissions, by tests that fail if model code imports the
writer, and by triggers that block illegal changes to Raju's knowledge. Every change goes into an append-only, hash-chained log.</p>
<p>Anything a model produces is a suggestion. Raju's sentence is shown only if it passes a leak filter (exactly the planned mistake, no answer given, only
words the learner has seen, reads like a student). If it fails, Raju says a pre-written sentence from our bank. The coach (दीदी) gives one Hindi hint
that may contain neither the answer nor any Telugu. The Telugu friend in scenes may only pick approved lines.</p>
<h3>4.2 The learning ladder and stack</h3>
<p>Six levels: L0 letters, L1 syllables, L2 words (shared Sanskrit words first, look-alikes flagged), L3 phrases, L4 sentence rules where Raju appears
(after three ready rules), L5 conversations. A skill counts as learned only after correct answers on more than one item and day, without hints, including
one the learner produced. The app is FastAPI with server-rendered Hindi pages, PostgreSQL 16 and FSRS spaced repetition; a build check fails if any
English letter appears in learner text.</p>
<h3>4.3 Beginner on-ramp and interface additions</h3>
<p>Because Raju appears only after three ready rules, the early levels exist to get a beginner there. We added a learning-path map (L0–L5, "you are here"),
small word pictures (27 of 28 words, Hindi alt text, never on a question about the same word), a match-the-pairs game, a "meet Raju" card from day one and a
"what Raju learned from you" section, and, at the learner's request, English text under the Telugu word on intro, feedback and result cards (never on
questions). Voice buttons exist but are off by default until their gate passes. The match game uses the recognition checker and writes review schedules
only, so it cannot teach Raju or move a level. An automated accessibility check (axe-core, WCAG 2.0–2.2 A and AA, 8 pages, phone and desktop width) left
one demo-only finding. <b>None of these additions is evaluated:</b> the simulators do not model them and no learner has used them.</p>""")

    P.append(f"""<figure class="wide"><div class="shots">{img('final-home.png','Home')}{img('final-ladder.png','Progress')}{img('final-en-word.png','English under the word')}{img('final-match.png','Match game')}</div>
<p class="cap">Figure 1: Interface additions (running app, demo database): (a) home with path map and Raju card; (b) progress page with what Raju learned; (c) feedback with English under the Telugu word; (d) match game.</p></figure>""")

    P.append("""<h3>4.4 Methods compared</h3><p>On the same 29 frozen cases we compared, with Wilson 95% intervals and exact McNemar tests: <b>generation</b> (prompt-only, blind
resampling, tool-assisted); <b>tool calling</b> (model-chosen read-only tools with a step cap, against prompt-only and tools off, plus 17 harness attacks and
11 injected messages); <b>stepwise reasoning</b> against a direct answer (58 cases) with a self-check ablation; <b>RAG</b> (BM25 over character n-grams on the
25 rule documents) against blind, given-the-rule-title and oracle retrieval; <b>fine-tuning</b> Gemma-3-1B-it against prompted Gemini, with a go/no-go bar set
before generating data; <b>multi-agent</b> roles against a single agent; and a <b>checker/judge</b> comparison on 50 native labels. All hosted calls use
gemini-3.5-flash with reasoning off. The research questions were: (RQ1) does correcting the peer beat matched error examples and a normal tutor on delayed
and transfer tests; (RQ2) do contrast-based predictions match learners' errors; (RQ3) do effects differ by direction; (RQ4) does the checker judge corrections
reliably compared with a prompt-only agent. Today: RQ1 is answered only in simulation (and there it does not); RQ2 and RQ3 are open (no learner data; only
Hindi→Telugu is built); RQ4 is answered (checker κ 0.15, judge 0.46).</p>""")

    P.append("""<h3>4.5 Agent intake questions</h3><p>The course's four intake questions, answered for SETU in one line each.
<b>(1) Which single part genuinely needs the model to choose the next step?</b> None of the control flow: the planner, checker, scheduler and level moves are rules. The one model-chosen output is Raju's sentence (and which read-only tool to call while writing it); every verdict about it is deterministic.
<b>(2) What does one full episode cost in model calls?</b> About 1.3 calls per exchange: 2.6 per tool-assisted Raju turn, 27.7 for a full 21-exchange simulated run, and 0 when the model is off, because every agent has an approved fallback.
<b>(3) One tool the design assumes and we do not yet have?</b> A Telugu speech gate (word-error-rate measurement plus native-speaker voice review); voice is built but off behind flags until it exists. A validated Telugu sentence leveler is the second.
<b>(4) Worst action and who would notice?</b> Raju writing a wrong Telugu form that the checker accepts, so the learner learns the error. The teacher's unsure queue and the append-only ledger expose it only if the learner's correction falls in the unsure band; a confident wrong verdict is seen only at native review, which is why checker agreement (κ 0.15 against a 0.6 target) is the main open risk in Section 8.</p>""")

    P.append("<h2>5 Experiment Runs</h2><p>Everything below was run on the frozen sets and is saved under <code>reports/</code>.</p><h3>5.1 What was built and run</h3>")

    P.append("<p>All eight learner slices, the teacher console, the agents and two simulators were complete at mid-submission. Since then:</p>")

    P.append(table(["Part", "Done since mid-submission", "Status"], [
        ["Model evaluations", "Tasks 6, 13–18: generation, tool calling, reasoning, judge, RAG, fine-tuning, multi-agent; real-model runs (1,561 hosted calls)", "done"],
        ["Checker agreement", "50 native-labelled answers compared with checker and judge", "done, below target"],
        ["Interface", "Path map, pictures, match game, early Raju card, English glosses, speech behind flags", "built, not evaluated"],
        ["Tests", "1,287 passing (1,039 at mid-submission)", "done"],
        ["Native review; learner pilot", "One bilingual team member reviewed the rules (24 of 25 realistic; not independent); no independent review; no pilot data in the repository", "partly / not done"],
    ], "Table 2: Progress at final submission."))

    P.append("""<h3>5.2 Runs</h3><ul>
<li><b>Generation (task 6):</b> 29 planting cases, three Raju methods; 250 calls.</li>
<li><b>Judge vs checker (13):</b> 50 native-labelled answers; 50 calls. <b>Tool calling (14):</b> 29 cases plus 17 harness attacks and 11 injected messages; 166 calls.</li>
<li><b>Reasoning (15):</b> 58 cases, stepwise vs direct and self-check; 464 calls. <b>Multi-agent vs single agent (18):</b> 191 calls.</li>
<li><b>RAG hints (16):</b> six pre-planned conditions and one post-hoc fix; 354 calls. <b>Fine-tuning (10, 17):</b> pair generation (18 calls answered of 57), a prompted-Gemini baseline (29), and untuned Gemma-3-1B on CPU (29, 145 s).</li>
<li><b>Simulators:</b> sim-0.1 and sim-0.2 (100 simulated learners per condition, many variations) plus the earlier parametric one.</li></ul>
<p><b>Compute.</b> Hosted calls: 1,561 sent (1,522 answered), 575,698 tokens, all gemini-3.5-flash with reasoning off. <b>GPU hours: 0</b> (no fine-tune ran). Hosted models are
off by default and no learner data is sent to them. A cost figure is not computed because the price is not in the repository.</p>""")

    P.append("""<h3>5.3 Simulated learners</h3>
<p>The first simulator (sim-0.1) had A (correct Raju) beating B (same content, no classmate) but not C (conventional tutor). The improved one (sim-0.2), which
shares the app's FSRS memory model, reverses it: day-7 recall A .253, B .329, C .306 (A−B −.076 [−.081, −.071]; A−C −.053 [−.060, −.047]), and A stayed last in
every variation. A third, parametric simulator (in the team's earlier repository) also had A below C in all five assumption sets (delayed recall 0.50 vs 0.67 under the defaults). The simulations disagree because they model memory differently; neither is evidence about people. We report the second because it uses the
app's own memory model.</p>""")

    P.append(f'<figure>{chart}<p class="cap">Figure 2: Day-7 recall by condition. The ordering of A, B and C flips between the simulators.</p></figure>')

    P.append("<h3>5.4 Virtual cohort in place of a learner pilot</h3>")
    P.append("""<p>We did not run a human study. The protocol's measures were computed on a virtual cohort instead: 100 simulated students per condition (20 profiles × 5 seeds), the
same profiles in every condition, practising on days 0–2 and tested on days 0, 1, 2 and 7, with the app's own planner, checker, filter and FSRS memory model.
<b>This is a software simulation, not evidence about learners</b>; its learning effects are assumptions, and a real study stays future work.</p>""")
    P.append(table(["Measure (sim-0.2, matched exchanges)", "A teach Raju", "B examples", "C tutor", "A−B (d<sub>z</sub>)", "A−C (d<sub>z</sub>)"], [
        ["Primary: production, day 7", ".239", ".313", ".286", "−.074 (−2.95)", "−.046 (−1.61)"],
        ["Secondary: transfer, day 7", ".192", ".252", ".226", "−.060 (−3.08)", "−.034 (−1.58)"],
        ["False alarms on correct sentences", ".24", "0", "0", "", ""],
        ["Hints used (per run)", "16.3", "3.8", "13.2", "", ""],
        ["Time on task (s)", "909", "765", "840", "", ""],
        ["Own sentences written", "6", "6", "21", "", ""],
        ["Expected model calls per run", "27.7", "0", "0", "", ""],
    ], "Table 3: Protocol measures on the virtual cohort (reports/simulation_v2/results.json). Intervals for A−B and A−C are in section 5.3; all intervals exclude zero and every difference is negative for A."))
    P.append("""<h2>6 Ablations</h2><p>Each ablation switches off or changes one thing and keeps the same cases, model and filter.</p><ul>
<li><b>Tools off (Raju):</b> valid 0.76 [0.58, 0.88] without tools against 0.97 with them; prompt-only 0.69. The gain comes from letting the model check its own draft.</li>
<li><b>Resampling:</b> asking again without saying why gave valid 0.76 against 0.72 for one call, and a higher draft leak rate (0.17 vs 0.10).</li>
<li><b>Reasoning self-check:</b> revised 3.4% of answers, fixed none and broke two; stepwise 0.36 vs direct 0.40 (p = 0.625).</li>
<li><b>RAG variants:</b> blind 10/29, given the rule title 16/29, RAG 12/29, oracle retrieval 19/29 shown-and-usable; explanations only and no threshold did not differ detectably from RAG. A prompt fix (never name a rule by number) reached 25/29 but was designed on the same cases.</li>
<li><b>Role separation (multi-agent):</b> same task success (0.31) with 0 model-decided verdicts against 65, at 359 vs 1,682 tokens per case.</li>
<li><b>Fine-tuning:</b> untuned Gemma-3-1B passed the filter on 7/29, prompted Gemini on 21/29; the fine-tune itself was not run (no-go on data).</li>
<li><b>Simulator (sim-0.1 and sim-0.2):</b> Raju never forgets, answer shown at once instead of a hint, no own sentences, teaching benefits switched on or off, no testing effect, memory half-life changed, matched time instead of matched exchanges. A stayed below B and C in every sim-0.2 variation; removing the learner's own sentences hurt every condition; showing the answer at once lowered recall in all three.</li></ul>""")

    P.append("<h2>7 Evaluations</h2><h3>7.1 Checker and filters (held-out, 185 cases)</h3>")

    P.append(table(["Check", "Result", "Target", ""], [
        ["Correct Raju sentences clean (n=14)", "100%", "100%", "pass"], ["Wrong answers caught (n=34)", "100%", "≥90%", "pass"],
        ["Correct answers wrongly rejected (n=32)", "0%", "≤5%", "pass"], ["Checker says unsure (n=66)", "18.2%", "≤15%", "<b>fail</b>"],
        ["Trick inputs accepted (n=25)", "0", "0", "pass"], ["English letters in Hindi UI", "0", "0", "pass"],
    ], "Table 4: Held-out results (unchanged since mid-submission). The unsure ceiling was not loosened."))

    P.append("""<p>An "unsure" answer never changes the learner's record; it goes to a teacher. Our cases are team-written, so real input is probably harder.</p>
<h3>7.2 Does the checker agree with native speakers?</h3>
<p>On 50 answers labelled by native speakers (16 correct, 26 partial, 8 wrong) the checker reached κ = 0.15 [−0.03, 0.31] (accuracy 0.36) against a target of
0.60, and a prompt-only LLM judge κ = 0.46 [0.29, 0.64] (accuracy 0.62). The checker is good at "wrong" (recall 0.88) and weak on "partial" (recall 0.12): of 26
partial answers it called 9 correct, 5 wrong and sent 9 to unsure. Our hypothesis H6 (the checker beats a prompt-only judge) is rejected. An earlier blind marking of 145 answers by a bilingual team member gave κ = 0.32 for
the earlier checker; one added rule (a correct sentence followed by the tag particle కదా is wrong) raised it to 0.599, but that rule was fitted to the answers
that suggested it, so we do not count it. Both measurements fall below the 0.6 target.</p>
<h3>7.3 Model capabilities against baselines</h3>""")

    P.append(table(["Capability", "Method vs baseline", "Result"], [
        ["Generation", "tool-assisted vs prompt-only", "valid 0.93 [0.78, 0.98] vs 0.72 [0.54, 0.85]; 1,054 vs 140 tokens/case"],
        ["Tool calling", "tools vs prompt-only vs tools off", "valid 0.97 vs 0.69 vs 0.76; 44 calls all correct; 0 unsafe actions (17/17 attacks refused; 0/11 injections)"],
        ["Reasoning", "stepwise vs direct (58)", "0.36 vs 0.40, McNemar p = 0.625; 2,290 vs 567 tokens/case"],
        ["RAG hints", "RAG vs blind", "shown and usable 12/29 vs 10/29, p = 0.79; right rule first 16/29, top 3 24/29"],
        ["Fine-tuning", "Gemma-3-1B vs prompted Gemini", "7/29 vs 21/29 pass; <b>no-go</b>: 23 usable pairs vs 200 needed"],
        ["Multi-agent", "multi vs single agent", "success 0.31 vs 0.31; model-decided verdicts 0 vs 65; 359 vs 1,682 tokens/case"],
    ], "Table 5: Headline results on the frozen sets. Intervals are wide at n = 29."))

    P.append("""<p>Only tool use improved Raju, and it cost about seven times the tokens. Resampling alone did not beat one call (0.76 vs 0.72). The multi-agent setup is
no more accurate; its gain is structural: no model decides a verdict. RAG found the right rule first in 55% of cases; a prompt fix that stopped hints from
naming numbered rules raised shown-and-usable hints to 25/29, but it was designed on the same 29 cases, so treat it as optimistic. Fine-tuning failed on
data, not compute: of 144 generated pairs, 23 passed our validator (2 of 14 rules).</p>""")

    P.append("<h3>7.4 Targets fixed in advance</h3>")

    P.append(table(["Metric (target)", "Measured", "Outcome"], [
        ["Leak rate (&lt; 2%, below prompt-only)", "tools 0.00 [0.00, 0.12]; prompt-only 0.10", "below prompt-only; &lt; 2% not provable at n = 29"],
        ["Planting precision (≥ 0.8)", "1.00, every method", "met"],
        ["Wrong fixes caught (≥ 0.9) / right fixes rejected (&lt; 5%)", "100% / 0%", "met"],
        ["Checker unsure (&lt; 15%)", "18.2%", "<b>failed</b>"],
        ["Agreement with teachers (κ ≥ 0.6)", "0.15 (50); 0.32 earlier (145)", "<b>failed</b>"],
        ["Prompt injection changing state (0)", "0 of 17 attacks; 0 of 11 injections", "met"],
        ["Model calls per turn (≈ 1–2); ≤ 48 per 12-exchange session", "2.6 per case, tool-assisted; 27.7 per 21-exchange simulated run (about 1.3 per exchange)", "met in simulation"],
        ["Coach answer leaks (&lt; 2%)", "0 shown (upper bound 12%)", "not provable at n = 29"],
        ["Coach solved after a hint; tracker AUC; speech WER; error-bank κ", "not measured", "open"],
        ["Learner outcomes (primary, transfer, false alarms)", "virtual cohort only (Table 5); human study is future work", "simulated"],
        ["Copy rate, usability (SUS)", "needs real learners", "future work"],
    ], "Table 6: The metrics table from the 28 October paper against what we measured."))

    P.append("""<h3>7.5 Interface checks (our additions)</h3>
<p>We checked the interface, not its effect on learning. An automated accessibility audit (axe-core 4.10, WCAG 2.0–2.2 A and AA plus best practice) on 8 pages at
390 px and 1280 px left one finding, the demo banner outside a page landmark (demo-only, present before our additions); it also found and we fixed low
contrast on "not yet open" path stages. The whole match round can be answered with Tab, Space and Enter, there is no horizontal scroll at 320 px, nothing
animates under reduced-motion, base text is 18 px with self-hosted fonts, the Hindi lint reports 0 violations, and the audit exposed one crash (the progress
page for a learner whose next step was a Telugu word group), now fixed with a regression test. We make no claim that pictures, English glosses, voice or the
match game improve learning: no simulator models them and no learner has used them.</p>""")
    P.append("""<h3>7.6 Failures worth showing</h3><ul>
<li><b>Success:</b> the live model wrote "నేను నహీ వెళ్తా ను" (Hindi नहीं for the Telugu negative): exactly the planted mistake, passed the filter.</li>
<li><b>Retrieval miss:</b> for "క్యా నువ్వు వస్తావు" the right rule came second (0.78) behind a TE→HI rule (0.82); 8 of 13 top-1 misses went to such rules.</li>
<li><b>Unusable hint:</b> 8 of 20 RAG hints said to read a numbered rule the learner never sees.</li>
<li><b>Small model:</b> untuned Gemma-3-1B added a Devanagari word; the filter rejected it and the app showed the bank sentence.</li>
<li><b>Not one error:</b> prompted Gemini added a negation to an already-negative verb.</li></ul>
<p>In every case the filters or the checker handled the failure, so the learner never saw a failing sentence.</p>
""")

    P.append("""<h3>7.7 How we checked our own work</h3><p>1,287 tests pass, against real PostgreSQL 16, with model keys removed in CI. Every number in this report comes from a
file in <code>reports/</code>, and the tables regenerate from the saved JSON. We kept the runs we rejected (a rate-limited and a quota-exhausted baseline) and
did not use them. Several results here are negative (reasoning, RAG, multi-agent accuracy, fine-tuning, checker κ), and we report them as measured.</p>""")

    P.append("<h2>8 Limitations</h2>")

    P.append("""<p>Every learner result is simulated. Telugu content has had one review, by a bilingual team member, who is not independent; no outside rater has reviewed it. The checker agrees with native labels poorly (κ 0.15) and failed its unsure
ceiling. Evaluation sets are small and team-made. The interface additions are unevaluated, and the English words and new Hindi strings are drafts. Spoken Hyderabad forms differ from textbook Telugu, the checker mishandled a tag particle (29 of 53 disagreements) and a missing final vowel sign, and the Devanagari-to-Telugu converter passed 12 of 14 native checks. A pilot of five or fewer learners could only describe, not prove, an effect.</p>""")

    P.append("<h3>Open issues</h3>")

    P.append(table(["Challenge", "Status / plan"], [
        ["Only one non-independent review of Telugu; none of the new Hindi strings", "outside reviewers needed before any learner sees content"],
        ["Checker unsure 18.2% and κ 0.15", "teachers settle unsure answers; count partial answers as wrong only if teacher labels support it"],
        ["Small frozen sets (29, 58, 50)", "intervals wide; confirm on new cases"],
        ["Simulators disagree", "calibrate on pilot data; report every variation"],
        ["Pictures lack teacher review and Hindi audio description", "fold into the memory-aid subsystem or label demo-only"],
        ["Speech", "off by default; needs word-error-rate and speaker-review gates (Chrome sends speech audio to Google)"],
    ], "Table 7: Open issues."))

    P.append("""<h2>9 Conclusions</h2><p>Three findings are solid enough to defend. First, the control design holds on our cases: no model changed a grade, and every model output either
passed the checks or was replaced by approved text. Second, among model capabilities, only giving the model tools to check its own draft clearly helped, and the
others did not beat simple baselines on small frozen sets. Third, honest simulation says correcting Raju, as built, does not give more recall than a normal tutor,
so learners need more sentences they write from memory. Whether correcting Raju works as real recall for real learners is the question only a pilot can answer.</p>
<h3>Future work</h3><p>Items we chose not to attempt in the time available, none of which our results can stand in for:
<ul><li><b>A study with real adult learners</b> (pre-test, delayed and transfer tests, blind marking) and its measures: delayed production, copy rate, usability.</li>
<li><b>Independent native-speaker review</b> of the rules, words, chunks and the new Hindi strings, with agreement between raters, and a larger blind-marked set for the checker (target κ ≥ 0.6).</li>
<li><b>A language-model student</b> whose Telugu knowledge sits in an explicit store, to replace the parametric simulators; and the selective-flip, controllability and responsiveness metrics with a real model.</li>
<li><b>Error-bank validation</b> against a learner corpus (predicted vs observed errors, RQ2, RQ3), and the Telugu→Hindi direction.</li>
<li><b>Coach with learners</b> (solved after one hint, teacher rating), the knowledge tracker against BKT and SM-2, and speech (word error rate, speaker review).</li>
<li><b>More fine-tuning data</b> (200 checked pairs over 12 rules) before any training, and larger frozen sets for every evaluation.</li></ul></p>
<p>We also learned that a test has to be able to fail, and that real model output fails in ways our cases did not predict.</p>""")

    P.append("""<h2>Ethics Statement</h2><p>Pilot learners would be consenting adults. Accounts use random IDs and passphrases; we store no names, emails, phone numbers or IP addresses, and withdrawal
deletes the learner's text. Unreviewed Telugu is never shown to real learners. The 28 October plan was self-hosted models only; we later used a hosted model (gemini-3.5-flash) for evaluation on team-written cases. It is off by default and receives no learner data. Browser speech
recognition can send audio to a third party, so speech is off. We used an AI assistant for coding, testing and drafting; its commits carry a co-author line,
and every number was checked against a file in <code>reports/</code>.</p>
<h2>Contributions</h2><p><b>Madhav Malhotra:</b> core system, teacher tools, simulators, coach RAG and the fine-tuning pipeline. <b>Kushal Karan:</b> tool-calling, reasoning, judge and
agent evaluations, results tables, real-model runs. <b>Shaik Areesh:</b> human-system agreement (Batch A) and annotation validation. <b>Faviana Noronha:</b> beginner
interface, accessibility check, results analysis, failure analysis, compute report and this write-up. (Roles are from the commit history; each author should confirm.)</p>
<h2>References</h2>
<p class="ref">Alemdag, E., et al. 2025. Learning from erroneous examples: a meta-analysis.</p>
<p class="ref">Berzak, Y., Reichart, R., and Katz, B. 2015. Contrastive analysis with predictive power: typology driven estimation of grammatical error distributions in ESL. CoNLL.</p>
<p class="ref">Chinnappa. 1978. Difficulties of Telugu-speaking students in learning Hindi (thesis, Andhra).</p>
<p class="ref">Chase, C., Chin, D., Oppezzo, M., and Schwartz, D. 2009. Teachable agents and the protégé effect. J. Science Education and Technology 18(4).</p>
<p class="ref">Doddapaneni, S., et al. 2023. Towards leaving no Indic language behind. ACL.</p>
<p class="ref">Jin, H., et al. 2024. Teach AI how to code: using LLMs as teachable agents for programming education. CHI.</p>
<p class="ref">Kanojia, D., et al. 2020. Harnessing cross-lingual features to improve cognate detection for low-resource languages. COLING.</p>
<p class="ref">Madhani, Y., et al. 2023. Aksharantar: Open Indic-language transliteration datasets and models. Findings of EMNLP.</p>
<p class="ref">Roediger, H. L., and Karpicke, J. D. 2006. Test-enhanced learning. Psychological Science 17(3).</p>
<p class="ref">Thurston, A., et al. 2021. Cross-age reading tutoring: a class-randomised trial.</p>
<p class="ref">Wardhaugh, R. 1970. The contrastive analysis hypothesis. TESOL Quarterly 4(2).</p>
<p class="ref">Yuan, et al. 2026. The competence paradox in simulated learners.</p>
<p class="ref">Ye, J., Su, J., and Cao, Y. 2022. A stochastic shortest path algorithm for optimizing spaced repetition scheduling. KDD.</p></main>""")
    return f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>SETU final report</title><style>{CSS}</style></head><body>{"".join(P)}</body></html>'


def main():
    (OUT / "SETU_final_paper.html").write_text(build(), encoding="utf-8")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        pg.goto((OUT / "SETU_final_paper.html").as_uri())
        pg.pdf(path=str(OUT / "SETU_final_paper.pdf"), format="Letter", print_background=True,
               margin={"top": "17mm", "bottom": "17mm", "left": "15mm", "right": "15mm"})
        b.close()


if __name__ == "__main__":
    main()
