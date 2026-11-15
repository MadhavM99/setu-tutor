# Final report: sections written by Faviana (paste-ready)

Numbers are from `reports/` (see `faviana_analysis_20_23.md` for sources). Everything about learners is a statement about
the machinery or a simulation; no real learner has used the system, and no Telugu content has had native review.

## A. The beginner on-ramp and interface (UI work)

**Why it exists.** SETU's central idea is that a learner corrects a weak classmate, Raju. A true beginner cannot correct
anyone, and Raju only uses words the learner has met and appears after three ready rules. So the early levels have to
get a Hindi speaker to that point. We built the path to it as six levels (L0 letters, L1 syllables, L2 words,
L3 phrases, L4 correcting Raju, L5 conversations) and made it visible.

**What we built on top of the existing app** (branch `faviana-noronha`; the tests grew from 1,039 to 1,287):

| Feature | What the learner sees |
|---|---|
| Learning-path map | L0–L5 with "you are here" on the home and progress pages; stages not yet open are dashed, not faded |
| Word pictures | a small drawing beside 27 of the 28 words, with Hindi alt text; never shown on a question about the same word |
| Match-the-pairs game | match Telugu words to meanings or to pictures; scored by the same rule-based checker, and it changes only the review schedule, never a skill record |
| Raju introduced early | a "meet Raju" card on the home page from day one; after he starts, a card with counts of what he learned from, or forgot because of, the learner |
| English under each word | small English text under the Telugu word on intro, feedback and match-result cards, never on questions |
| Optional browser voice | listen and say-it buttons, **off by default** |

**How it follows the specification.**
- *Models write, rules decide.* None of the additions grades anything. The match game uses the recognition checker and
  writes review schedules only, so it cannot teach Raju or move a level.
- *Recognition is not recall.* The picture version records its aids (`choices`, `illustration`) as assistance.
- *Speech is behind flags* (`speech_input`, `tts_synthetic`), off until the word-error-rate and speaker-review gates
  pass. Browser speech recognition in Chrome sends audio to Google, so it is off and the report says so.
- *Accessibility (E-15).* 18 px base text, self-hosted fonts, keyboard-only flow, reduced-motion respected. An
  automated check (axe-core 4.10, WCAG 2.0–2.2 A and AA) on 8 pages at phone and desktop width left one finding: the
  demo banner outside a page landmark, which is demo-only.
- *Language.* The interface is Hindi. The English words are the one exception, kept in a separate list and marked
  `lang="en"`; they can be turned off with `SETU_ENGLISH_GLOSS=0`.

**What we found and fixed.** The progress page crashed for a learner whose next step was a Telugu word group. The catalog
treated an HTML tag name as Latin text. We added a rich-text catalog call that checks only visible text, and a test
that fails without the fix.

**What we cannot claim.** None of these features is evaluated: the simulators do not model them and no learner has used
them, so we make no claim that pictures, voice, English glosses or the match game improve learning. The pictures are a
separate hand-drawn set; the specification's memory-aid subsystem requires teacher review and a Hindi audio
description for every aid, which these do not have yet. The new Hindi strings are drafts awaiting teacher review. The
English words are mine and unreviewed.

## B. Problem statement and goals

Use the text and tables in `faviana_goals_alignment.md` (problem statement, goals G1–G5 with status, research
questions RQ1–RQ4 and what each can currently answer, and the can/cannot-claim table).

## C. Results, examples, failures, compute (tasks 20–23)

Use `faviana_analysis_20_23.md`: summary table per capability, six qualitative examples (three failures), failure
analysis per capability, and the compute report (1,561 hosted calls, 575,698 tokens, 0 GPU hours). Full tables with
intervals are in `reports/results_tables.md`.

## D. Limitations to state plainly

1. No real learner data: RQ1–RQ3 are unanswered outside simulation, and in the simulator that shares the app's memory
   model, correcting Raju finished last (day-7 recall .253 vs .329 and .306). The two simulators disagree.
2. The checker agrees with native labels less than a prompt-only judge (κ 0.15 vs 0.46, 50 labels), and M-09 failed
   (0.18 vs a ceiling of 0.15).
3. Small frozen sets (29, 58, 50 cases): intervals are wide.
4. All Telugu content, Hindi strings and the English words await review.
5. RAG and stepwise reasoning did not help; fine-tuning was a no-go for lack of data (23 pairs vs 200).
