# Goals and problem statement, aligned with the app and the results

Sources compared: the research paper (draft of 28 Oct, "version 8"), the mid-submission report, `docs/product/PRD.md`,
the app on branch `faviana-noronha`, and `reports/`. Paste-ready text first, then what has to change elsewhere.

## Problem statement (paste-ready)

Hindi speakers learning Telugu bring knowledge that helps (shared Sanskrit words, letters that line up almost one to
one) and habits that hurt (the Hindi question word at the start of a yes/no question, Hindi-style negation, carried-over
gender agreement). Most language apps ignore both. Two things block a tutor for this pair. First, a beginner cannot
correct anyone until they know enough Telugu, so a "teach the classmate" tutor needs an on-ramp. Second, a language
model asked to play a weak classmate knows too much: it leaks correct forms and words the learner has not met. We
build SETU around one rule, *models write, rules decide*. The classmate Raju keeps his knowledge as data, every
sentence he writes passes a deterministic filter, and only a rule-based checker decides what counts as learning. We
ask whether correcting such a classmate improves recall, and which language-model capabilities (tool calling,
reasoning steps, retrieval, fine-tuning, one agent or several) can be used around him without giving up that control.

## Goals

| # | Goal | Evidence we have | Status |
|---|---|---|---|
| G1 | Control: no model decides a grade or changes memory | 0 verdicts decided by a model in the multi-agent setup (65 in single-agent, task 18); checker never fooled by 25 tricks; held-out checks, M-09 failed | **met, with one failed check (M-09 = 0.18 vs 0.15)** |
| G2 | Beginner on-ramp: letters, words, phrases with Hindi twins, pictures, a path map, match game, Raju introduced on day one | built and tested (1,287 tests, accessibility check) | **built, not evaluated** |
| G3 | Reverse learning improves delayed recall | two simulations that disagree; in the one that shares the app's memory model, correcting Raju finished last in every run | **not supported in simulation; pilot needed** |
| G4 | Use model capabilities safely: tool calling, reasoning, RAG, fine-tuning, single vs multi-agent | tool calling 0.97 valid and 0 unsafe; stepwise reasoning no better than direct; RAG no better than blind on usable hints; fine-tuning no-go; multi-agent matches single-agent accuracy with 0 model-decided verdicts | **evaluated, mostly negative or neutral, reported as such** |
| G5 | Honest evaluation: failures reported, rejected runs kept | M-09 fail, Table 6 spoiled run, sim-0.1 retired | **met** |

## Research questions, and what we can answer today

| RQ | Question | Can we answer it? |
|---|---|---|
| RQ1 | Does correcting the peer beat matched examples and a normal tutor on delayed and transfer tests? | **Only in simulation, and there it does not.** Real answer needs the pilot (descriptive at 5 learners). |
| RQ2 | Do the contrast-based predictions match the errors learners make? | **No.** There is no learner error data yet. |
| RQ3 | Do effects differ by direction? | **No.** Only Hindi→Telugu is built and tested first; Telugu→Hindi stays in the bank. |
| RQ4 | Does the checker judge corrections reliably compared with a prompt-only agent? | **Yes, on 50 native labels:** checker κ = 0.15 [−0.03, 0.31], prompt-only judge κ = 0.46 [0.29, 0.64]; H6 rejected. |

## What has to change so everything says the same thing

1. **Speech.** The paper says "text-first tutor, with basic speech input and native voices". The mid report says speech
   is out of scope. The app has listen and say-it behind flags that are off. Say: *text-first; pictures and browser
   voice are optional aids, built but not evaluated; speech stays off until its gate (WER, speaker review) passes.*
2. **Simulation claim in the abstract.** The paper says teaching beat matched examples but not a normal tutor. That is
   the first simulation (sim-0.1). In sim-0.2 correcting Raju was last in every run (day-7 recall .253 vs .329 and
   .306). Replace the sentence with the sim-0.2 result and say the two disagree because they model memory differently.
3. **Central question.** Keep it, but label it a hypothesis tested in simulation, with the pilot pending. Do not write
   "we show that correcting a peer improves recall".
4. **Contributions.** Add a fourth: *an evaluation of five model capabilities against baselines on the same 29 frozen
   cases, with intervals, including the negative results.* That is what the course asks for and what we actually
   measured.
5. **The on-ramp is part of the problem.** Add one sentence to the paper's introduction that Raju only uses words the
   learner has met and appears after three ready rules, so the early levels exist to get a beginner there. That is why
   the app now introduces Raju on the home page from day one and shows "what Raju learned from you" on the progress page.
6. **Direction and scope.** Hindi speakers learning Telugu first (the UI is Hindi only); Telugu→Hindi rules exist but
   are not tested on learners.
7. **Numbers that moved.** Tests: 1,039 → 1,287. Hosted-model use: 1,561 calls, 575,698 tokens, 0 GPU hours.

## What we can and cannot claim

| Can claim | Cannot claim |
|---|---|
| The control design holds on our test cases; no model changed a grade | That learners learn more from correcting Raju |
| Agentic tool use gave valid Raju sentences 0.93–0.97 of the time vs 0.72 prompt-only, at about 7.5x the tokens | That the pictures, voice or match game help learning |
| The checker agrees with native labels less than a prompt-only judge does (κ 0.15 vs 0.46) | That our Telugu content is correct (no native review yet) |
| RAG and stepwise reasoning did not help on our 29 and 58 cases | That the error bank predicts real learner errors |
