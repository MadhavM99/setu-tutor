# Research paper (version 8, draft of 28 Oct) against the final paper: what is missing, what conflicts, what to add

The paper in this chat is headed "version 8, draft of 28 October 2026, results pending" ("v9" in conversation). It is a
proposal and design paper. The final paper is a results paper, so the two overlap on the idea and the evaluation plan, and
differ in everything measured since. Page and section references are to the 28 Oct draft.

## 1. Things in the 28 Oct paper that were missing from the final paper (now added to it)

| Missing item | Where in the 28 Oct paper | Added to the final paper as |
|---|---|---|
| Prior work and motivation: competence paradox, protégé effect, cross-age tutoring (tutors +0.24, tutees −0.07), learning from errors (g = 0.136), contrastive analysis criticised | §1–2 | a related-work paragraph in the introduction, plus references |
| No Hindi↔Telugu learner-error data; only a 1978 thesis (78% of 262 teachers: gender is hard for Telugu speakers) | §1 | same paragraph |
| Typological check: WALS κ = 0.442 (Telugu 38th of 691 most like Hindi), Grambank κ = −0.025 (796th of 2,245) | §6.4, Table 5 | new section 4, "Error bank and typology" |
| Contrast table (negation, polar questions, copula, relative clauses, "we", possession, gender, ergative ने) | Table 6 | condensed table in section 4 |
| Research questions RQ1–RQ4 and what each can answer today | §8.3 | new table in section 5 |
| Evaluation metrics with targets fixed in advance (Table 10), and which are measured | §8.4 | scorecard table in section 6: each target against what we measured |
| First native review by a bilingual team member: 24 of 25 rules realistic; blind marking of 145 answers, κ = 0.32 (checker v0.1), κ = 0.599 after one rule, fitted to the same answers | §8.5 | section 6.2 and the limitations |
| Third simulator (the LMA one): A 0.50 vs C 0.67 delayed recall, A below C in every assumption set | §8.2, Table 9 | section 6.4 now says three simulators, none has A above C |
| Risks table, prompt-injection path analysis | §9, Table 11 | two lines in section 8 and the ethics statement |
| Checker failure modes from the 145 answers: tag particle కదా added to a correct sentence (29 cases), missing final vowel sign (29 mixed verdicts) | §8.5 | limitations |
| Spoken Hyderabad forms, Devanagari-to-Telugu converter 12/14 | §9 | limitations |

## 2. Statements that conflict, and which way we resolved them

1. **"No native review."** My drafts and the first version of the final paper said no Telugu content had native review. The
   28 Oct paper records one review by a bilingual team member: 24 of 25 rules realistic, HI-TE-012 "partly". She is a team
   member, so it is not independent. All drafts and the paper now say that. The in-app teacher console still has no reviewed items.
2. **Speech.** The 28 Oct paper promises "basic speech input and native voices". The final system keeps speech off by default. The
   final paper says so.
3. **Hosted models.** The 28 Oct paper says "self-hosted models only; no commercial API sees learner text", and that the hosted run
   "contradicts the team's decision, so it is a development run". We have since used a hosted model (gemini-3.5-flash) for all the
   evaluations. The final paper says hosted use was for evaluation and never sees learner data, and names it as a change of plan.
4. **Local baseline.** The plan was Gemma 3 12B. What ran locally was Gemma-3-1B-it on CPU. The final paper reports the 1B run.
5. **Checker agreement.** Two measurements exist: κ = 0.32 on 145 answers (earlier checker, bilingual team member), and κ = 0.15 on 50
   answers (current checker, Batch A). Both are below the 0.6 target. The 0.599 figure was fitted to the answers that suggested the
   rule, so it is not quoted as a result.
6. **Direction.** The 28 Oct abstract covers both directions; the final system and all learner-facing tests are Hindi→Telugu.
7. **Abstract sentence on simulation.** The 28 Oct abstract says teaching beat matched examples but not a normal tutor. That is the first
   simulator only; the final paper leads with the second.

## 3. Targets in the 28 Oct paper (Table 10) against what we measured

| Metric | Target | Measured | Outcome |
|---|---|---|---|
| Leak rate | < 2% and below prompt-only | tool-assisted 0.00 [0.00, 0.12]; prompt-only 0.10 | below prompt-only; "< 2%" cannot be shown at n = 29 |
| Planting precision | ≥ 0.8 | 1.00 for every method | met |
| Wrong fixes caught / right fixes rejected | ≥ 0.9 / < 5% | 100% (n = 34) / 0% (n = 32) | met |
| Checker unsure | < 15% | 18.2% (n = 66) | **failed** |
| Checker agreement with teachers | κ ≥ 0.6 | 0.15 (50 answers); 0.32 earlier (145) | **failed** |
| Agents: first-draft pass, tool loop vs blind vs prompt-only | reported; lowest fallback with tools | valid 0.93 vs 0.76 vs 0.72 | reported |
| Model calls per turn | ≈ 1–2, ≤ 48 per session | 2.6 per case (tool-assisted); session maximum not measured | slightly above |
| Prompt injection changing a verdict, memory or state | 0 | 0 of 17 harness attacks, 0 of 11 injected messages | met |
| Coach hints giving the answer | < 2% | 0 of shown hints (upper bound 12%) | not demonstrable at this n |
| Coach: solved after one hint ≥ 50%, teacher rating ≥ 4/5 | | not measured | open |
| Native friend: words outside band < 5% | | model picked approved line 12/12 plain, 12/12 under injection; band words not measured | partial |
| Tracker (AUC vs BKT/SM-2), speech WER, error-bank κ and predicted-vs-observed | | not measured | open |
| Simulation: cue-free recall by condition | reported | A last in sim-0.2; A below C in all three simulators | reported |
| Learners: primary, secondary, copy rate, SUS | | no pilot data in the repository | open |

## 4. Still not in the final paper (decide whether to add)

- **Selective flip score, controllability, RMSE, responsiveness** (28 Oct §8.4): the paper computed 1.0, 1.0, 0.0, 1.0 over 720 turns, but only with a mock model, "by construction". Not rerun with a real model, so it was left out.
- **Mirror mode, forgetting-vs-remembering classmate, predict-then-check:** exploratory conditions that never ran.
- **Startup validation interviews** (5–8 planned) and the Sarvam-M bake-off: no results anywhere in the repo.
- **Full future-work section** (larger trial, error-collection at scale, validated Telugu leveler). The final paper only has "what is left". The sentence leveler result (exact 0.694 vs 0.633, 49 items) is in `faviana_ui_notes.md` if you want to cite it.
- **Ask the team:** was the five-learner pilot run? Was Sarvam-M compared? Did the outside native rater review anything? Each would change the Limitations and Table 1.
