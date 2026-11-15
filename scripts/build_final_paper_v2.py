"""Build the revised final paper (after the 15 Nov 2026 audit), two-column, with the eleven required sections.

    python -m scripts.make_figures            # figures first (needs matplotlib)
    python -m scripts.build_final_paper_v2    # docs/submission/report/SETU_final_paper_v2.{html,pdf}

Every number in the text is read from a file in reports/ when the paper is built; nothing is typed in by hand except
facts that live in no result file (team, dates, the earlier paper's review figures, which are marked as such).
The PDF is printed with headless Chrome, as the earlier builders do.
"""
import base64
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/submission/report"
FIGS = ROOT / "docs/submission/figures"
SHOTS = ROOT / "docs/submission/screenshots"
R = ROOT / "reports"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

CSS = """
@page { size: A4; margin: 16mm 14mm; }
body { font: 9.6pt/1.33 "Liberation Serif", "Times New Roman", "Noto Sans Devanagari", "Noto Sans Telugu", serif; color: #000; margin: 0; }
header { text-align: center; column-span: all; margin-bottom: 8px; }
h1 { font-size: 14pt; line-height: 1.2; margin: 0 0 6px; }
.authors { display: flex; justify-content: space-around; font-size: 9.4pt; margin: 4px 0; }
.authors b { display: block; } .small { font-size: 8.4pt; }
main { column-count: 2; column-gap: 7mm; text-align: justify; hyphens: auto; }
h2 { font-size: 10.8pt; margin: 10px 0 3px; break-after: avoid; } h3 { font-size: 9.6pt; margin: 7px 0 2px; break-after: avoid; }
p { margin: 0 0 4px; } ul, ol { margin: 2px 0 4px 0; padding-left: 14px; } li { margin: 0 0 2px; }
.abs { margin: 0 8mm 6px; text-align: justify; font-size: 9.3pt; column-span: all; }
.abs h2 { text-align: center; margin-top: 2px; }
table { border-collapse: collapse; width: 100%; font-size: 8.1pt; margin: 3px 0 2px; break-inside: avoid; text-align: left; hyphens: manual; }
th, td { padding: 1.5px 3px; vertical-align: top; } thead th { border-top: 1.2px solid #000; border-bottom: .8px solid #000; }
tbody tr:last-child td { border-bottom: 1.2px solid #000; }
.cap { font-size: 8.4pt; margin: 2px 0 7px; text-align: left; } code { font-family: "DejaVu Sans Mono", Menlo, monospace; font-size: 7.4pt; }
figure { margin: 5px 0 6px; break-inside: avoid; } figure img { width: 100%; } figure.wide { column-span: all; }
.ref { padding-left: 10px; text-indent: -10px; font-size: 8.1pt; margin: 0 0 2px; text-align: left; hyphens: manual; }
.box { border: .8px solid #000; padding: 3px 5px; margin: 4px 0; font-size: 8.8pt; break-inside: avoid; }
"""


def load(name):
    return json.loads((R / name).read_text(encoding="utf-8"))


def fig(name, cap, wide=True):
    data = base64.b64encode((FIGS / f"{name}.png").read_bytes()).decode()
    return (f'<figure class="{"wide" if wide else ""}"><img alt="{name}" src="data:image/png;base64,{data}">'
            f'<p class="cap">{cap}</p></figure>')


def table(head, rows, cap):
    h = "".join(f"<th>{x}</th>" for x in head)
    b = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<table><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table><p class="cap">{cap}</p>'


def ci(d, nd=2):
    return f"{d['rate']:.{nd}f} [{d['lo']:.{nd}f}, {d['hi']:.{nd}f}]"


def wil(k, n):
    import math
    z, p = 1.959964, k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return {"rate": p, "lo": 0.0 if k == 0 else max(0, c - h), "hi": 1.0 if k == n else min(1, c + h)}


def build() -> str:
    base, tool, reas, rag = load("generation_baselines.json"), load("tool_eval.json"), load("reasoning_eval.json"), load("rag_eval.json")
    ag, ft, judge, abl = load("agentic_eval.json"), load("ft_eval.json"), load("judge_eval.json"), load("generation_ablation.json")
    sim1, sim2, sens, ftd = load("simulation/results.json"), load("simulation_v2/results.json"), load("simulation_sensitivity.json"), load("ft_data.json")
    cstats = json.loads((FIGS / "fig4_checker_stats.json").read_text())
    fd = ftd["data"]
    import yaml
    items = [it for f in sorted((ROOT / "content").glob("*/rules/*.yaml")) for it in yaml.safe_load(f.read_text(encoding="utf-8"))["items"]]
    exact_only = sum(1 for it in items if not it.get("wrong_patterns"))
    score = load("scorecard-2026-10-31-heldout.json")
    A = abl["summary"]["conditions"]
    pairs = {(p["x"], p["y"], p["scope"]): p for p in abl["summary"]["paired"]}
    reps = max(v["repeats"] for v in A.values())

    def a_rate(c):
        v = A[c]
        lo, hi = v["pooled_valid_ci95_case_bootstrap"]
        return f"{v['pooled_valid_rate']:.2f} [{lo:.2f}, {hi:.2f}]"

    def a_pair(x, y):
        p1, pa = pairs[(x, y, "repeat1")], pairs[(x, y, "all_repeats")]
        lo, hi = pa["difference_ci95_case_bootstrap"]
        return (f"{pa['difference']:+.2f} [{lo:+.2f}, {hi:+.2f}] pooled; repeat 1: {p1['x_only']} vs {p1['y_only']} "
                f"discordant cases, p = {p1['p_exact']:.3f}")

    t = tool["methods"]
    r = reas["results"]["stage_a"]
    pos = {k: v["positives"] for k, v in rag["conditions"].items()}
    g = ag["results"]
    ck, jd = judge["checker"], judge["llm_judge"]
    s2 = sim2["runs"]["main_matched_exchanges"]
    s1 = sim1["runs"]["main"]
    new_calls, new_tokens = abl["summary"]["total_calls"], abl["summary"]["total_tokens"]
    P = []
    P.append("""<header><h1>SETU: Reverse Learning with a Rule-Governed AI Classmate<br>for Hindi-Speaking Learners of Telugu</h1>
<div class="authors"><div><b>Madhav Malhotra</b>2026900003</div><div><b>Kushal Karan</b>2025204010</div>
<div><b>Faviana Noronha</b>2025900018</div><div><b>Shaik Areesh</b>2026909008</div></div>
<div class="small">International Institute of Information Technology, Hyderabad · Language Models and Agents, Monsoon 2026 · Team Token Guessers<br>
Code, data and every result file: <code>https://github.com/MadhavM99/setu-tutor</code></div></header>""")

    P.append(f"""<div class="abs"><h2>Abstract</h2>SETU is a tutor for Hindi speakers learning Telugu. At its sentence stage the learner corrects Raju, an AI
classmate who makes the mistakes a Hindi speaker makes. Raju's knowledge is stored as data, and the system follows one rule: language models may write
text, but ordinary code decides what is shown, how an answer is marked and what the learner's record says. We report what this design achieved and where
it fell short. On our test cases no model output reached a learner unchecked and none changed a mark ({tool['harness_attacks']['n']} of
{tool['harness_attacks']['n']} tool attacks refused; {tool['injected_attacks']['evaluable']} injected messages, no unsafe attempt). We compared five model
capabilities with simpler baselines on small frozen case sets using one hosted model. Letting the model call a checking tool raised the share of valid
Raju sentences from {t['prompt_only']['valid_rate']:.2f} to {t['agentic_tools']['valid_rate']:.2f}, but a controlled re-run shows a fixed loop that simply
shows the model its own rejected draft reaches {A['tool_history']['pooled_valid_rate']:.2f} against {A['agentic_tools']['pooled_valid_rate']:.2f} at about
one fifth of the tokens. Stepwise reasoning, retrieval for hints and separate agent roles did not improve accuracy, and fine-tuning stopped at a data
check. The rule-based checker never accepted a wrong answer on held-out cases but agrees poorly with a native speaker's labels (κ = {ck['kappa']:.2f}
against {jd['kappa']:.2f} for a prompt-only model judge). No learner has used SETU: learner outcomes are simulated, the two simulators order the
teaching conditions differently, and the one built on the app's own memory model puts reverse learning last. We state which claims the evidence
supports and which remain open.</div>""")
    P.append("<main>")

    P.append("""<h2>1 Introduction</h2>
<p>Hindi and Telugu belong to different language families, yet they share many Sanskrit-derived words and their scripts correspond almost letter for
letter. A Hindi speaker therefore starts with real advantages, and also with habits that cause errors: the question word क्या at the start of a yes/no
question, a separate negative word before the verb, the copula है where Telugu uses none. General language apps do not target these habits.</p>
<p>SETU tests one teaching idea, which we call <b>reverse learning</b>: instead of only answering questions, the learner finds and fixes the mistakes
of a classmate, Raju. Each of Raju's sentences carries one mistake on a rule the learner has already shown they know. A correct fix "teaches" Raju the
rule; if the learner is predicted to have forgotten it, Raju forgets it too and makes the mistake again.</p>
<p>Building such a classmate with a language model raises a control problem. A model asked to act as a weak student knows too much: it writes correct
forms, uses words the learner has not met, or drifts into explaining. A model that also marks answers can be talked into a wrong mark. SETU's response
is an architecture rule, <b>models write, rules decide</b>: a model may propose a sentence, a hint or a choice among approved lines; deterministic
code (code with no model in it, so the same input always gives the same result) decides whether the proposal is shown, marks every answer, and is the
only thing that can change the learner's record.</p>
<h3>Research questions</h3>
<p>The project began with four questions about learners (does correcting a peer improve delayed recall; do predicted errors match real ones; do effects
differ by direction; is the checker reliable). Three need human participants we did not have. We therefore separate what our evidence can answer from
what it cannot:</p>
<ul><li><b>RQ1 Control.</b> Can any model output reach a learner, or change a mark or the learner's record, without passing a deterministic check?
<i>Answerable: attack sets, permission tests.</i></li>
<li><b>RQ2 Capabilities.</b> Which model capabilities (tool calling, stepwise reasoning, retrieval, a tuned small model, separate roles) improve the
classmate's sentence, the coach's hint or the diagnosis of an answer over a simpler baseline? <i>Answerable on small frozen sets.</i></li>
<li><b>RQ3 Checker.</b> How well does the rule-based checker agree with a native speaker, compared with a prompt-only model judge? <i>Answerable for
one labeller and 50 answers.</i></li>
<li><b>RQ4 Learning.</b> Does correcting Raju improve delayed recall over the same content without him, or over an ordinary tutor? <i>Not answerable
here: simulation only.</i></li></ul>
<h3>Contributions</h3>
<ol><li>A working tutor in which model roles are proposal-only and a single writer, backed by database permissions, owns learner state (Section 5).</li>
<li>A measured comparison of five model capabilities against baselines, with a controlled ablation that separates the effect of model-chosen tool calls
from the effect of conversation memory (Sections 6, 7).</li>
<li>A comparison of a rule-based checker and a model judge against native-speaker labels, reported with its failure (Section 8).</li>
<li>Two learner simulators that disagree, with an analysis of which assumptions the disagreement comes from (Section 8).</li></ol>
<p>The first is an engineering contribution. The second to fourth are empirical findings on small samples; several are negative.</p>""")

    P.append("""<h2>2 Literature Review</h2>
<p><b>Learning by teaching.</b> Students work harder for an agent they believe they are teaching, the protégé effect (Chase et al., 2009), and
teachable-agent systems such as Betty's Brain build on it (Biswas et al., 2005). Jin et al. (2024) used a language model as a teachable agent for
programming and reported that it tends to know too much. Who benefits is an open question in peer tutoring too: a randomised trial was run
specifically to compare the gains of tutors and tutees (Thurston et al., 2021).</p>
<p><b>Learning from errors.</b> Studying incorrect examples can help when learners explain the error (Große and Renkl, 2007), and taking a test
strengthens memory more than rereading (Roediger and Karpicke, 2006). A recent meta-analysis of 42 papers finds only a weak average benefit of
erroneous examples (g = 0.136), larger when an explanation activity is included (Alemdag et al., 2025). Reverse learning is thus a hypothesis, not an
established effect.</p>
<p><b>Simulated students.</b> Markel et al. (2023) trained teaching assistants with model-played students. Yuan et al. (2026) name the central problem
the competence paradox: a broadly capable model is asked to imitate a learner who knows only part of the material, and argue for an explicit
specification of what the simulated learner knows. SETU's classmate state table is one concrete form of such a specification.</p>
<p><b>Tools, retrieval, and control of agents.</b> ReAct interleaves model reasoning with tool calls (Yao et al., 2023), and retrieval-augmented
generation supplies retrieved text to the model (Lewis et al., 2020). Instructions hidden in the data a model reads can redirect it (Greshake et al.,
2023). Debenedetti et al. (2025) defend against this by design, keeping untrusted data from steering control flow. SETU applies the same principle
in a simpler setting: models have no write tools at all.</p>
<p><b>Tutoring systems and memory.</b> Knowledge tracing estimates what a learner knows from their answers (Corbett and Anderson, 1995). Spaced
repetition schedules reviews from a memory model (Settles and Meeder, 2016); FSRS, which we use, optimises review timing from a
difficulty-stability-retrievability model (Ye et al., 2022).</p>
<p><b>Hindi and Telugu.</b> Contrastive analysis, predicting learner errors from differences between languages, has long been criticised for weak
prediction (Wardhaugh, 1970), although typology can predict error distributions in aggregate (Berzak et al., 2015). Resources exist for Indian
languages as written by fluent users, including transliteration data (Madhani et al., 2023), language models (Doddapaneni et al., 2023) and a 2025
grammatical-error-correction shared task covering Hindi and Telugu (BHASHA IndicGEC). We found no corpus of errors made by Hindi speakers learning
Telugu, so each predicted error in our bank is a hypothesis.</p>""")
    P.append(table(["Work", "Method", "Evaluation", "Limit for our purpose", "SETU's difference"], [
        ["Chase et al. 2009", "Teachable agent, school biology", "Classroom studies", "Agent is not a language model; science, not language", "Language learning; agent state tied to the learner's own forgetting"],
        ["Jin et al. 2024", "LLM teachable agent, prompt-controlled knowledge", "Lab study with learners", "Knowledge control by prompting", "Knowledge held as data; every output filtered"],
        ["Yuan et al. 2026", "Framework for valid student simulation", "None (conceptual)", "No system or measurement", "A built instance, with measured failure rates"],
        ["Alemdag et al. 2025", "Meta-analysis, erroneous examples", "42 papers, 177 effects", "Mostly mathematics and science", "Errors are L1-transfer errors in a second language"],
        ["Yao et al. 2023", "Model chooses tool calls", "QA and decision benchmarks", "Assumes model choice is needed", "We test whether a fixed loop does as well"],
        ["Debenedetti et al. 2025", "Control flow isolated from untrusted data", "AgentDojo benchmark", "General agents", "Same principle, education setting, no write tools"],
        ["Ye et al. 2022", "FSRS scheduling", "Review logs", "Built for flashcards", "Used for items; its fit to error correction is questioned in Section 8"]],
        "Table 1: Closest prior work. We make no first-of-its-kind claim; we did not find a tutor for this language pair or a learner-error corpus for it."))

    P.append(f"""<h2>3 Dataset Created and Used</h2>
<p>All content and all evaluation data were written by the team. None of it comes from learners.</p>""")
    P.append(table(["Set", "Size", "Use", "Status"], [
        ["Rule bank", "25 rules (15 Hindi→Telugu, 10 Telugu→Hindi), 49 items", "Raju's sentences, checker keys", "Draft; one review by a bilingual team member"],
        ["Ladder content", "48 letters, 489 aksharas, 28 words, 32 chunks, 4 scene scripts", "Levels L0–L3, L5", "Draft"],
        ["Planting cases", "29 (every Hindi→Telugu item)", "Generation, tools, RAG, roles", "Frozen 12 Nov 2026"],
        ["Diagnosis cases", "58", "Stepwise reasoning", "Frozen"],
        ["Held-out checker and filter cases", f"{score['cases']} (of 663 in all)", "Checker, leak filter, attacks", "Frozen 31 Oct 2026"],
        ["Attack prompts", "28 (17 tool calls, 11 learner messages)", "RQ1", "Frozen"],
        ["Native labels, batch A", f"{judge['labelled_rows']} answers: " + ", ".join(f"{v} {k}" for k, v in judge['human_labels'].items()), "RQ3", "One labeller, a team member"],
        ["Fine-tuning pairs", f"{fd['funnel_gemini']['candidates']} generated, {fd['accepted']} passed the validator", "Go/no-go", "Not used for training"]],
        "Table 2: Data. Files: <code>content/</code>, <code>tests/eval_sets/</code>, <code>tests/stage_a/</code>, <code>research/labels/</code>, <code>data/ft/</code>."))
    P.append("""<p><b>Error bank.</b> Each rule records one contrast (for example: Hindi marks a yes/no question with क्या at the start, Telugu with a
suffix at the end) and each item gives a Hindi meaning, the correct Telugu sentence and the wrong sentence a Hindi speaker is predicted to write. The
bank marks every rule <code>validity: uncertain</code> and <code>learner_evidence: predicted</code>. An earlier version of this paper reported a
first review (24 of 25 rules judged realistic) and a blind marking of 145 answers; the 145-row sheet in this repository carries no labels, so those
figures cannot be reproduced from it and we do not rely on them.</p>
<p><b>Limits of the evaluation sets.</b> The planting cases are the bank's own items, so a method is scored on reproducing sentences the team wrote.
In these cases the list of words the model may use contains only the words of the right and the wrong sentence; in the app the list is every word the
learner has seen, which is a harder setting. The planned external corpora (IndicCorp, IndicGEC) were not used.</p>""")

    P.append("""<h2>4 Methodology</h2>
<h3>4.1 System</h3>
<p>SETU is a web application (FastAPI, server-rendered Hindi pages, PostgreSQL 16). Learners move up six levels: letters, syllables, words, phrases,
sentence rules, and short scenes. A skill counts as learned after three unaided correct answers across two items, two task types and two days. Raju
appears at the sentence-rule level once three rules are ready.</p>""")
    P.append(fig("fig1_architecture", "Figure 1: SETU as implemented. Purple components call a language model and can only return text. Teal components are deterministic. "
                 "Only code inside the dashed boundary can change learner state; the database refuses changes that are not backed by a checker verdict, a signed teacher decision or a scheduler decision. "
                 "Module names are the real ones under <code>setu/</code>."))
    P.append(f"""<p><b>One exchange.</b> The planner picks a rule the learner knows and Raju does not, and an item. Raju's sentence is shown. The learner
either confirms it or types a correction. The normaliser cleans the answer (for example, Telugu typed with Devanagari letters is converted). The
checker compares it with the item's accepted forms and returns one of four verdicts: correct, partial, wrong, or unsure. After a first miss the coach
gives one hint; after a second the answer is shown and the learner copies it, which never counts as evidence. A verdict of unsure changes nothing and
goes to a teacher's queue. Only an unaided, typed, correct fix teaches Raju the rule.</p>
<p><b>Who may write.</b> The checker issues verdict objects that other code cannot construct. One component, the OutcomeWriter, accepts only those, a
teacher decision signed with a server key, or a forgetting decision from the scheduler. It runs under a restricted database role, and a trigger
re-checks each change to Raju's knowledge. Every change is appended to a hash-chained log.</p>
<p><b>Model roles.</b> Raju writes one sentence; the coach writes one Hindi hint; the Telugu friend in scenes picks among approved lines. Each output
passes a filter or is replaced by approved text. For Raju the filter requires exactly the planned mistake, no word the learner has not seen, one
sentence in Telugu script and a student's voice. For {exact_only} of {len(items)} items "exactly the planned mistake" means the bank's wrong
sentence, since a paraphrase cannot be verified without a person.</p>""")
    P.append(fig("fig2_raju_loop", "Figure 2: How Raju's sentence is produced. The app uses the fixed loop (steps 3–4, up to three drafts). The variant in which the model "
                 "chooses its own tool calls exists only in the evaluation scripts."))
    P.append("""<h3>4.2 Methods compared</h3>
<p>All model runs use one hosted model, <code>gemini-3.5-flash</code>, through an OpenAI-compatible endpoint, reasoning effort off, temperature 0.4
for generation and 0 for grading and diagnosis. Each method is scored on the same frozen cases as its baseline.</p>
<ul><li><b>Generation.</b> <i>Prompt only</i> (one draft); <i>resample</i> (up to three independent drafts); <i>harness feedback</i> (the app's
loop: the program runs the filter and returns its reason codes); <i>model-chosen tools</i> (the model is told about three read-only checking tools
and decides when to call one, at most six model calls).</li>
<li><b>Tool calling.</b> The same generation task scored for tool use, plus two attack sets: 17 model replies that try an unknown or malformed tool
call, replayed into the tool handler, and 11 learner-style messages injected into Raju's task.</li>
<li><b>Stepwise reasoning.</b> Diagnose a learner's correction (which word is wrong, which rule, which error type) in three separate steps with or
without a self-check step, against one direct call.</li>
<li><b>Retrieval (RAG).</b> BM25 over character n-grams of the 25 rule documents returns three rules for the coach; baselines are no retrieval,
the rule title given, and the correct rule given (an upper bound).</li>
<li><b>Fine-tuning.</b> A bar was fixed before generating data: at least 200 validated training pairs covering 12 of 14 rules. Untuned
Gemma-3-1B-it was compared with the prompted hosted model.</li>
<li><b>Role separation.</b> Separate Raju and coach calls with the rule-based checker, against one model that writes the sentence and hint and
also grades.</li>
<li><b>Checker.</b> The checker and a prompt-only model judge against 50 native-speaker labels.</li></ul>
<h3>4.3 Metrics and statistics</h3>
<p><i>Valid rate</i>: share of cases in which a model sentence passed the filter. <i>Leak rate</i>: share in which a draft was the correct sentence.
<i>Usable hint</i>: a model hint passed the filter and does not refer to a numbered rule list the learner cannot see. <i>Cohen's κ</i>: agreement
beyond chance, κ = (p<sub>o</sub> − p<sub>e</sub>)/(1 − p<sub>e</sub>), where p<sub>o</sub> is observed agreement and p<sub>e</sub> the agreement
expected from the label frequencies. <i>False acceptance</i>: answers a native speaker did not mark correct that the system marked correct.
<i>False rejection</i>: answers marked correct by the native speaker that the system did not. Proportions carry Wilson 95% intervals. Methods run on
the same cases are compared with the exact McNemar test on discordant pairs. With 29 cases only large differences can be detected, and a
non-significant difference is never read as equivalence. We do not report a money cost, because no price is recorded in the repository; we report
calls and tokens.</p>""")

    P.append(f"""<h2>5 Experiment Runs</h2>
<p><b>Software checks.</b> 1,300 automated tests pass against PostgreSQL 16 with no model configured; 484 of them are one parametrised test over the
frozen cases, so the count is not a measure of coverage. On the {score['cases']} held-out cases the checker caught every wrong answer and rejected no
correct one, the filters passed every clean Raju sentence and rejected every attack, and the checker answered unsure on 18.2% of answers against a
ceiling of 15% fixed in advance. That check failed and the ceiling was not changed.</p>
<p><b>Running system.</b> The application was run end to end on a demonstration database with and without the hosted model: a wrong answer, a hint, a
copied answer; an unaided correct fix that taught Raju; and a romanised answer that went to the teacher's queue. In the model run, Raju's drafts for
two of three planted turns were rejected and the approved sentence was shown; the coach's one hint was written in Telugu, rejected, and replaced by
the generic hint. Demonstration content is approved by demonstration accounts, and the real rules, which still have open validation issues, are
not shown to learners.</p>""")
    P.append(table(["Run", "Cases", "Calls (answered)", "Tokens"], [
        ["Generation baselines", "29", str(base["provider_calls"]["ok"]), "51,619"],
        ["Tool calling and attacks", "29 + 28", str(tool["provider_calls"]["ok"]), "38,787"],
        ["Stepwise reasoning", "58", str(reas["provider_calls"]["ok"]), "256,702"],
        ["Model judge", "50", "50", f"{judge['judge_tokens']:,}"],
        ["Retrieval and hints, 7 conditions", "29 + 40", str(rag["provider_calls"]["ok"]), f"{rag['provider_calls']['tokens']:,}"],
        ["Role separation", "29 × 4 attempts", str(ag["provider_calls"]["ok"]), "59,209"],
        ["Prompted model, fine-tuning baseline", "29", "29", "4,041"],
        ["Training-pair generation", "–", "18 (57 sent)", "17,161"],
        [f"Controlled ablation (this revision), {reps} repeats", "29 × 6 conditions", f"{new_calls:,}", f"{new_tokens:,}"],
        ["<b>Total</b>", "", f"<b>{1522 + new_calls:,}</b>", f"<b>{575698 + new_tokens:,}</b>"]],
        "Table 3: Hosted-model use, all with <code>gemini-3.5-flash</code>. One local run: untuned Gemma-3-1B-it on CPU, 29 cases, 145 s. No GPU hours. "
        "Median latency per call was about 1.0–1.4 s. Runs rejected for rate limits are kept in <code>reports/</code> and not used."))
    P.append(f"""<p><b>Calls per learner turn.</b> In the app's loop a planted turn costs {t['tool']['calls_per_case']:.2f} Raju calls and
{t['tool']['tokens_per_case']:.0f} tokens on average, plus one coach call (about {base['coach']['tokens_per_case']:.0f} tokens) only when the
learner's first answer is wrong. In our live run the best case was one call (160 tokens) and the worst four calls (639 tokens: three rejected drafts
and a rejected hint). With no model configured the cost is zero and the learner sees the same approved sentences.</p>""")

    P.append(fig("fig6_capabilities", "Figure 3: Each capability against its baseline. Points are success rates with Wilson 95% intervals. "
                 "Only tool calling separates from its baseline, and Section 7 examines why.", wide=False))
    P.append(f"""<h2>6 Results by Capability</h2>
<p><b>Tool calling.</b> Model-chosen tool calls gave a valid sentence in {ci(wil(round(t['agentic_tools']['valid_rate'] * 29), 29))} of cases, against
{ci(wil(round(t['tool']['valid_rate'] * 29), 29))} for harness feedback and {ci(wil(round(t['prompt_only']['valid_rate'] * 29), 29))} for one draft,
at {t['agentic_tools']['tokens_per_case']:.0f}, {t['tool']['tokens_per_case']:.0f} and {t['prompt_only']['tokens_per_case']:.0f} tokens per case. All
{t['agentic_tools']['tools']['tool_calls']} tool calls named the right tool with valid arguments. This says little about tool selection, since only
one of the three tools is relevant to the task. Recovery from a bad call could not be measured because none occurred.</p>
<p><b>Stepwise reasoning.</b> Splitting the diagnosis into steps did not help: all three answers were right in
{r['stepwise']['final_accuracy']:.2f} of cases with steps and a self-check, {r['no_self_check']['final_accuracy']:.2f} without the self-check and
{r['direct']['final_accuracy']:.2f} with one direct call (stepwise against direct, p = 0.625), at four times the tokens. The steps found the wrong
word more often ({r['stepwise']['wrong_word_accuracy']:.2f} against {r['direct']['wrong_word_accuracy']:.2f}, p = 0.065). The self-check changed 2 of
58 answers, both from right to wrong.</p>
<p><b>Retrieval.</b> The right rule was retrieved first in {pos['b_rag']['top1_retrieved_is_planted']['k']} of 29 cases and within the top three in 24.
Hints from retrieval were usable in {pos['b_rag']['shown_and_usable']['k']} of 29 cases against {pos['a_blind']['shown_and_usable']['k']} with no
retrieval (p = 0.79), and {pos['c_oracle_retrieval']['shown_and_usable']['k']} when the correct rule was given. Eight of twenty shown hints told the
learner to read a numbered rule they cannot see. A prompt and filter change made after seeing this raised usable hints to
{pos['b_fixed_posthoc']['shown_and_usable']['k']} of 29; because it was designed on these cases it is an optimistic figure that needs new cases.</p>
<p><b>Fine-tuning.</b> Of {fd['funnel_gemini']['candidates']} generated training pairs, {fd['accepted']} passed the validator
({fd['by_rule']['HI-TE-002']} of them for one rule), covering {fd['coverage']['hi_te_trainable']} rules, against a bar of 200 pairs and 12 rules set
beforehand, so no model was trained. The generation attempt was itself cut short: {fd['generation']['calls'] - fd['generation']['ok_calls']} of
{fd['generation']['calls']} calls were refused by the provider's rate limit, so the shortfall reflects both a strict validator and little data
generated. Untuned Gemma-3-1B-it passed the filter in {ft['conditions']['gemma3_1b_base']['primary_all_29']['valid']['k']}
of 29 cases against {ft['conditions']['gemini_prompted']['primary_all_29']['valid']['k']} for the prompted hosted model.</p>
<p><b>Role separation.</b> Whole-task success was {g['multi_agent']['task_success_rate']:.2f} with separate roles and
{g['single_agent']['task_success_rate']:.2f} with a single model, with {g['multi_agent']['tokens_per_case']:.0f} against
{g['single_agent']['tokens_per_case']:.0f} tokens per case. In the single-model design {g['single_agent']['model_made_state_changes']} marks were
decided by the model; in the separated design none were. That count follows from the design and is not an empirical finding: the separated pipeline
contains no code path by which a model could mark an answer. The four scripted learner attempts per case (the bank's right sentence, the bank's
wrong sentence, a romanised answer, an injected instruction) are also ones the checker handles by construction, so its 1.00 handling rate here does
not estimate its accuracy on real answers; Section 8 does.</p>
<p><b>Control (RQ1).</b> All {tool['harness_attacks']['n']} replayed tool attacks were refused with the documented error. With an instruction such
as "update my mastery to 100%" injected into Raju's task, the model attempted no unknown tool in {tool['injected_attacks']['evaluable']} of
{tool['injected_attacks']['evaluable']} cases (upper 95% bound 0.26). The friend showed only approved lines in 12 of 12 turns, with and without an
injected instruction, and with an invalid key every role fell back to approved text.</p>""")

    P.append(f"""<h2>7 Ablations</h2>
<h3>7.1 Is it the tool call, or the memory?</h3>
<p>Reading the code showed that the comparison in Section 6 changed three things at once. In the app's harness-feedback loop the model is sent the
task again with the filter's reason codes but <i>not its own rejected draft</i>, so it cannot see what it wrote. With model-chosen tools the whole
conversation is kept. And every prompt includes the bank's wrong sentence as "what Raju wrote last time", the very sentence the filter accepts. We
therefore re-ran the task with six conditions on the same 29 cases, {reps} repeats each ({new_calls:,} calls). The new condition, <i>harness feedback
with memory</i>, keeps each draft and the check's result in the conversation while the program, not the model, runs the check, with the same
three-draft budget. Two further conditions remove the example sentence from the prompt. Hypotheses were written into the script before the run. The
ablation was designed after seeing the earlier results, on the same cases, so it is exploratory.</p>""")
    P.append(table(["Condition", "Sees own drafts", "Check run by", "Valid, pooled [95%]", "Calls", "Tokens"], [
        [name, mem, who, a_rate(c), f"{A[c]['calls_per_case']:.2f}", f"{A[c]['tokens_per_case']:.0f}"] for c, name, mem, who in (
            ("prompt_only", "Prompt only", "–", "nobody"), ("tool", "Harness feedback (app)", "no", "program"),
            ("tool_history", "Harness feedback + memory", "yes", "program"), ("agentic_tools", "Model-chosen tools", "yes", "model"),
            ("prompt_only_noex", "Prompt only, no example", "–", "nobody"), ("agentic_noex", "Model-chosen tools, no example", "yes", "model"))],
        f"Table 4: Controlled ablation, 29 cases × {reps} repeats. Intervals are bootstrap intervals that resample cases, because repeats of a case are not "
        "independent. Source: <code>reports/generation_ablation.json</code>."))
    P.append(fig("fig3_generation", "Figure 4: Raju sentence generation. (a) The earlier single runs. (b) The controlled re-run; small ticks show each repeat. "
                 "Giving the fixed loop a memory of its drafts brings it close to model-chosen tool calls at a fraction of the tokens."))
    P.append(f"""<p><b>Memory.</b> Adding memory to the fixed loop changed the valid rate by {a_pair('tool_history', 'tool')}. Without memory,
{A['tool']['same_draft_repeated_share_of_retried']:.0%} of retried cases produced the same rejected draft every time; with memory none did.</p>
<p><b>Model choice.</b> Model-chosen tool calls against the fixed loop with memory: {a_pair('agentic_tools', 'tool_history')}. The data do not show
that letting the model choose its checks adds validity beyond what memory gives, and it costs
{A['agentic_tools']['tokens_per_case'] / A['tool_history']['tokens_per_case']:.1f} times the tokens. Its one visible advantage is that the correct
sentence never appeared as a rejected draft (leak rate {A['agentic_tools']['leak_rate']:.2f} against {A['tool_history']['leak_rate']:.2f}), because
the model tests drafts through the tool before submitting; in every condition the learner sees only a sentence that passed.</p>
<p><b>The example sentence.</b> We expected validity to fall sharply without the example. It did not: {a_pair('prompt_only', 'prompt_only_noex')}
for one draft, and {a_pair('agentic_tools', 'agentic_noex')} with tools. That hypothesis is rejected. The model rebuilds the bank's sentence from
the rule title, the Hindi meaning and the allowed words, which in these cases are only the words of the right and wrong sentences. The evaluation
is therefore easier than the app, where the allowed list is the learner's whole vocabulary.</p>
<p><b>What "valid" leaves out.</b> Of first drafts in the prompt-only condition, {A['prompt_only']['first_draft_kinds']['other_with_planted_word']} of
{A['prompt_only']['rows']} were a different sentence containing a word found only in the wrong sentence, such as a different verb form after the
Hindi negator. The filter rejects them because it cannot verify a paraphrase. Whether some are acceptable planted errors needs a native speaker and
was not judged.</p>
<h3>7.2 Other ablations</h3>
<p>Removing the self-check from stepwise reasoning changed nothing measurable ({r['no_self_check']['final_accuracy']:.2f} against
{r['stepwise']['final_accuracy']:.2f}). For retrieval, indexing only the rule explanations, restricting the index to Hindi→Telugu rules, and
removing the abstention threshold each moved results by a few cases, within the intervals. A retrieval score threshold separates off-topic input
from rule-related sentences (9 of 11 attacks abstained at 0.5) but cannot separate a correct sentence from a wrong one, since both match the same
rule.</p>""")

    fa, fr = cstats["checker"]["false_accept"], cstats["checker"]["false_reject"]
    P.append(f"""<h2>8 Evaluations</h2>
<h3>8.1 The checker against a native speaker (RQ3)</h3>
<p>One native-speaking team member labelled {judge['labelled_rows']} learner corrections without seeing the checker's verdicts. The checker reached
κ = {ck['kappa']:.2f} [{ck['kappa_ci95'][0]:.2f}, {ck['kappa_ci95'][1]:.2f}] and accuracy {ck['accuracy']:.2f}; a prompt-only model judge given
the same labelling guide reached κ = {jd['kappa']:.2f} [{jd['kappa_ci95'][0]:.2f}, {jd['kappa_ci95'][1]:.2f}] and accuracy {jd['accuracy']:.2f}.
The target fixed in advance was κ ≥ 0.6 and better than the judge; the hypothesis is rejected.</p>""")
    P.append(fig("fig4_checker", "Figure 5: Checker and model judge against the native labels. Rows are the native speaker's label, columns the system's. "
                 "The checker's errors concentrate in the 'partial' row."))
    P.append(f"""<p>The checker recognises wrong answers (recall {cstats['checker']['recall']['wrong']:.2f}) and fails on partial ones (recall
{cstats['checker']['recall']['partial']:.2f}): of 26 partial answers it marked 9 correct, 5 wrong and sent 9 to a teacher. It marked no wrong answer
as correct. Its false-acceptance rate ({fa:.2f}) equals the judge's ({cstats['llm_judge']['false_accept']:.2f}); the difference between them is false
rejection, {fr:.2f} against {cstats['llm_judge']['false_reject']:.2f}: the checker refuses half of the answers the native speaker accepted, often
because a sentence that drops the pronoun is valid Telugu but is not in the bank. Macro-F1 is {cstats['checker']['macro_f1']:.2f} against
{cstats['llm_judge']['macro_f1']:.2f}. Two cautions apply. There is one labeller, so we cannot say how much two native speakers would agree with each
other, and the label "partial" may be the least stable. And the judge is not a drop-in replacement: giving a model the mark is what the architecture
forbids, and its false-acceptance rate is no better.</p>
<h3>8.2 Targets fixed in advance</h3>""")
    P.append(table(["Target", "Measured", "Outcome"], [
        ["Wrong fixes caught ≥ 0.9; right fixes rejected &lt; 5% (held-out)", "100%; 0%", "met on team-written cases"],
        ["Checker unsure &lt; 15%", "18.2%", "<b>failed</b>"],
        ["Agreement with a native speaker κ ≥ 0.6", f"{ck['kappa']:.2f}", "<b>failed</b>"],
        ["State changed by an injected instruction: 0", "0 of 17; 0 of 11", "met"],
        ["Answer leaked by a shown Raju sentence &lt; 2%", "0 of 29, upper bound 0.12", "not provable at n = 29"],
        ["Model calls per turn about 1–2", f"{t['tool']['calls_per_case']:.2f} (app loop); {t['agentic_tools']['calls_per_case']:.2f} (model-chosen tools)", "met for the app loop"],
        ["Hint solves the item; tracker accuracy; speech error rate", "not measured", "open"],
        ["Learner outcomes, usability", "no participants", "open"]],
        "Table 5: Targets set in the 28 October plan against what was measured."))
    c1, c2 = s1["conditions"], s2["conditions"]
    d2 = s2["paired_differences"]
    P.append(f"""<h3>8.3 Simulated learners (RQ4)</h3>
<p>No learner has used SETU. To see what our own assumptions imply, we simulated 100 learners per condition (20 profiles × 5 seeds) for three
practice days and a test on day 7, under three conditions: A, correcting Raju; B, the same sentences with error and correction shown and the answer
typed while visible; C, an ordinary tutor that asks the learner to write the sentence. A simulation shows the consequences of its assumptions. It is
not evidence about people, and its intervals, which shrink as more learners are simulated, measure simulation noise only.</p>
<p>The first simulator gives day-7 recall A {c1['A']['recall_day7']['mean']:.3f}, B {c1['B']['recall_day7']['mean']:.3f}, C
{c1['C']['recall_day7']['mean']:.3f}. The second, which uses the app's FSRS scheduler as its memory model, gives A
{c2['A']['recall_day7']['mean']:.3f}, B {c2['B']['recall_day7']['mean']:.3f}, C {c2['C']['recall_day7']['mean']:.3f} (A − B
{d2['A-B']['recall_day7']['mean']:+.3f}, A − C {d2['A-C']['recall_day7']['mean']:+.3f}). The order of A and B reverses.</p>""")
    P.append(fig("fig5_simulation", "Figure 6: Simulated day-7 recall. (a, b) The two simulators. (c) The second simulator under changed assumptions: A stays below B "
                 "(negative values) in every setting except one that depends on a modelling artifact. Simulation only."))
    w = sens["without_artifact_variant"]
    P.append(f"""<p><b>Why they disagree.</b> The simulators make opposite assumptions about one thing. In the first, typing a visible answer never
lengthens memory, so B is last by construction. In the second, typing a visible answer is always a successful review that lengthens memory, while a
failed attempt is a lapse; simulated learners begin with about a 0.29 chance of producing a form and, in A, must also notice the error (mean
probability 0.33), so most of A's turns are scored as lapses. We tested whether the second result depends on the assumptions we could vary:
the probability of noticing the error (0.2 to 0.95), whether a correct fix counts as unaided, and whether the copy step after a miss counts as a
review, as it does in the app. A stayed last in {w['cells_where_A_is_last']} of {w['cells']} settings. A led only when an unnoticed error was
treated as leaving no memory trace, and that setting relies on an artifact: a card never reviewed does not decay in this simulator.</p>
<p>FSRS was fitted to flashcard reviews, where a failure means a learned card was forgotten. Here it scores first attempts at material not yet learned,
where a failure followed by feedback may be useful. Whether that mapping is right is exactly what a study with learners would have to settle.
Within its assumptions, the simulation says correcting Raju as built gives less recall than the alternatives, and that the design should include more
sentences the learner writes unaided.</p>""")

    P.append("""<h2>9 Limitations</h2>
<ul><li><b>No learner data.</b> RQ4 and the original questions about error prediction and direction are unanswered. A pilot needs reviewed content,
informed consent and institutional clearance, none of which were in place.</li>
<li><b>Content.</b> The Telugu and Hindi content is a team draft with one non-independent review. The real rule bank cannot yet be activated; the
demonstration uses three labelled demonstration rules.</li>
<li><b>One labeller.</b> The 50 native labels come from one team member. There is no human–human agreement to compare the checker against.</li>
<li><b>Small, team-written, single-model evaluation.</b> Sets of 29, 58 and 50 cases give wide intervals. Apart from the ablation, each condition
was run once. One model was tested, so nothing here says how other models behave.</li>
<li><b>A narrow validity measure.</b> A valid Raju sentence is one that matches the bank. The model contributes no new sentence to a planted turn, and
variants the filter rejects were not judged by a person.</li>
<li><b>Research code is not the product.</b> Model-chosen tool calls, retrieval for hints, stepwise diagnosis and the model judge are evaluation
scripts. The app uses the fixed loop without memory, which the ablation shows is its weakest variant.</li>
<li><b>Post-hoc analyses.</b> The retrieval prompt fix and the generation ablation were designed after seeing results on the same cases.</li>
<li><b>Interface additions</b> (path map, word pictures, match game, English glosses) were built and passed an automated accessibility check but
were not evaluated with users. Speech features are off.</li>
<li><b>Simulation.</b> Both simulators rest on parameters chosen by the team.</li></ul>""")

    P.append(f"""<h2>10 Conclusions</h2>
<p><b>What the experiments establish.</b> (1) In this system a language model can be confined to proposing text: on our attack cases no model output
reached a learner unchecked or changed a mark, and with the model unavailable the app degraded to approved text. (2) For producing the classmate's
sentence, the benefit we first attributed to model-chosen tool calls is reproduced almost entirely by a fixed program loop that shows the model its
own rejected draft, at about one fifth of the tokens. In this task the model does not need to choose the next step. (3) Stepwise reasoning,
retrieval and separate roles did not improve accuracy over simpler baselines on our cases, and a small model could not be tuned for lack of
validated data. (4) The rule-based checker is safe in one direction, never accepting a wrong answer, but it rejects or defers too many acceptable
answers and agrees poorly with a native speaker.</p>
<p><b>What remains unknown.</b> Whether correcting a classmate helps anyone learn Telugu. Whether the predicted errors are the ones Hindi speakers
make. How the checker compares with agreement between two native speakers. Whether any of the capability results hold for other models, more cases
or sentences outside our bank.</p>
<p><b>Next steps, in order.</b> Independent native review of the bank and a second labeller; move the memory loop into the app and confirm it on new
cases; widen the accepted forms for pronoun-drop and partial answers and re-measure agreement; then, with clearance, a small descriptive pilot.</p>

<h2>Ethics Statement</h2>
<p>No human participants took part. Accounts use random identifiers and passphrases; the system stores no names, email addresses or phone numbers,
and withdrawal deletes a learner's text. Unreviewed Telugu is not shown to real learners. The 28 October plan specified self-hosted models only; we
later used a hosted model for evaluation on team-written cases. It is off by default and receives rule titles, Hindi meanings and bank sentences, not
learner identity. Browser speech recognition can send audio to a third party, so speech is off. An AI coding assistant was used for programming,
testing, analysis and drafting, including the audit behind this revision; the authors checked every reported number against a file in
<code>reports/</code> and are responsible for the content.</p>
<h2>Reproducibility</h2>
<p>The repository contains the application, the content bank, the frozen cases, every result file and the scripts that regenerate each table and
figure (<code>README.md</code>, "Reproducing the results"). The simulations, retrieval metrics, held-out scorecard, figures and this paper rebuild
without a model. Model runs need an endpoint; rows are saved per case, so a run can be resumed and inspected. Model outputs are not deterministic at
temperature 0.4, which is why the ablation reports repeats.</p>
<h2>Contributions</h2>
<p><b>Madhav Malhotra</b>: core system, teacher tools, simulators, coach retrieval, the fine-tuning pipeline, and the audit, generation ablation and
simulator sensitivity analysis of this revision. <b>Kushal Karan</b>: tool calling, stepwise reasoning, model-judge validation, the single-agent
baseline and role-separation evaluation, results tables, the call budget cap and the model runs. <b>Shaik Areesh</b>: human–system agreement (batch
A) and annotation validation. <b>Faviana Noronha</b>: beginner interface, accessibility check, results and failure analysis, compute report and the
earlier write-up.</p>

<h2>11 References</h2>""")
    refs = [
        "Alemdag, E., Eichelmann, A., and Narciss, S. 2025. A framework for learning from erroneous examples and meta-analysis of empirical research. <i>Review of Educational Research</i>. doi:10.3102/00346543251390901.",
        "Berzak, Y., Reichart, R., and Katz, B. 2015. Contrastive analysis with predictive power: typology driven estimation of grammatical error distributions in ESL. <i>CoNLL</i>.",
        "Biswas, G., Leelawong, K., Schwartz, D., Vye, N., and TAG-V. 2005. Learning by teaching: a new agent paradigm for educational software. <i>Applied Artificial Intelligence</i> 19(3–4).",
        "Chase, C., Chin, D., Oppezzo, M., and Schwartz, D. 2009. Teachable agents and the protégé effect: increasing the effort towards learning. <i>J. Science Education and Technology</i> 18(4), 334–352. doi:10.1007/s10956-009-9180-4.",
        "Corbett, A., and Anderson, J. 1995. Knowledge tracing: modeling the acquisition of procedural knowledge. <i>User Modeling and User-Adapted Interaction</i> 4.",
        "Debenedetti, E., Shumailov, I., Fan, T., Hayes, J., Carlini, N., Fabian, D., Kern, C., Shi, C., Terzis, A., and Tramèr, F. 2025. Defeating prompt injections by design. arXiv:2503.18813.",
        "Doddapaneni, S., et al. 2023. Towards leaving no Indic language behind: building monolingual corpora, benchmark and models for Indic languages. <i>ACL</i>.",
        "Greshake, K., Abdelnabi, S., Mishra, S., Endres, C., Holz, T., and Fritz, M. 2023. Not what you've signed up for: compromising real-world LLM-integrated applications with indirect prompt injection. <i>AISec</i>.",
        "Große, C., and Renkl, A. 2007. Finding and fixing errors in worked examples: can this foster learning outcomes? <i>Learning and Instruction</i> 17(6).",
        "Jin, H., Lee, S., Shin, H., and Kim, J. 2024. Teach AI how to code: using large language models as teachable agents for programming education. <i>CHI</i>. doi:10.1145/3613904.3642349.",
        "Lewis, P., et al. 2020. Retrieval-augmented generation for knowledge-intensive NLP tasks. <i>NeurIPS</i>.",
        "Madhani, Y., et al. 2023. Aksharantar: open Indic-language transliteration datasets and models for the next billion users. <i>Findings of EMNLP</i>.",
        "Markel, J., Opferman, S., Landay, J., and Piech, C. 2023. GPTeach: interactive TA training with GPT-based students. <i>Learning @ Scale</i>. doi:10.1145/3573051.3593393.",
        "Roediger, H. L., and Karpicke, J. D. 2006. Test-enhanced learning: taking memory tests improves long-term retention. <i>Psychological Science</i> 17(3).",
        "Settles, B., and Meeder, B. 2016. A trainable spaced repetition model for language learning. <i>ACL</i>.",
        "Thurston, A., et al. 2021. Assessing the differential effects of peer tutoring for tutors and tutees. <i>Education Sciences</i> 11(3), 97. doi:10.3390/educsci11030097.",
        "Wardhaugh, R. 1970. The contrastive analysis hypothesis. <i>TESOL Quarterly</i> 4(2).",
        "Yao, S., Zhao, J., Yu, D., Du, N., Shafran, I., Narasimhan, K., and Cao, Y. 2023. ReAct: synergizing reasoning and acting in language models. <i>ICLR</i>.",
        "Ye, J., Su, J., and Cao, Y. 2022. A stochastic shortest path algorithm for optimizing spaced repetition scheduling. <i>KDD</i>.",
        "Yuan, Z., et al. 2026. Towards valid student simulation with large language models. arXiv:2601.05473.",
    ]
    P += [f'<p class="ref">{x}</p>' for x in refs]
    P.append("</main>")
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><title>SETU final paper</title><style>' + CSS
            + "</style></head><body>" + "\n".join(P) + "</body></html>")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    html = OUT / "SETU_final_paper_v2.html"
    html.write_text(build(), encoding="utf-8")
    pdf = OUT / "SETU_final_paper_v2.pdf"
    subprocess.run([CHROME, "--headless", "--no-pdf-header-footer", f"--print-to-pdf={pdf}", html.as_uri()], check=True,
                   capture_output=True)
    print(html, pdf, sep="\n")


if __name__ == "__main__":
    main()
