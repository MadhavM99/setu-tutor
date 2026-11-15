# Demo video: script and shots (task 27), about 5 minutes

Setup: `SETU_TTS_SYNTHETIC=1 scripts/run_demo.sh`, open http://127.0.0.1:8000 on a phone-width window (about 390 px),
learner login printed by the script. Record at 1080p. Optional: set `SETU_LLM_*` for a live Raju sentence (see
`demo_guide.md`); otherwise Raju uses the approved fallback and the card says so.

| # | Time | Screen | Say |
|---|---|---|---|
| 1 | 0:00 | Title card | "SETU teaches Hindi speakers Telugu by having them correct an AI classmate, Raju. Models write, rules decide." |
| 2 | 0:20 | Home page | "One recommended lesson, chosen from the learner's real state. The path map shows where they are. Raju is introduced from day one, but he only appears after three ready rules." |
| 3 | 0:50 | Word intro card | "A new word comes with its Hindi twin, a picture and the English under it. Listen is optional and off by default until its speech gate passes." |
| 4 | 1:20 | Question, then feedback | "The question never shows the picture or English of the same word, so it can't give the answer away. Feedback shows both." |
| 5 | 1:50 | Match game (meanings, then pictures) | "Matching is checked by the same rule-based checker. It updates the review schedule only, never a skill record." |
| 6 | 2:20 | Raju exchange | "Raju writes one sentence with a planted Hindi habit. The learner corrects it. The model wrote it, a filter allowed it, a rule decides if the correction is right." |
| 7 | 3:10 | Coach hint | "If the learner is stuck, the coach hints in Hindi. A hint can't contain Telugu or the answer." |
| 8 | 3:30 | Progress page | "Here is what Raju learned from you and what he forgot. This is what the learner is teaching." |
| 9 | 3:55 | Teacher unsure queue | "When the checker is unsure, nothing changes the learner's record. A teacher decides." |
| 10 | 4:15 | Results slide (`reports/results_tables.md`) | "Results: tool use gives valid Raju sentences 0.93 to 0.97 of the time against 0.72 for prompting alone. RAG and stepwise reasoning did not help. Fine-tuning was a no-go. The checker agrees with native labels less than a prompt-only judge, κ 0.15 against 0.46, and our unsure-rate check failed at 0.18." |
| 11 | 4:45 | Limits slide | "Honest limits: no learner has used it yet, the two simulations disagree on whether correcting Raju helps, and native speakers haven't reviewed the Telugu. The interface additions are built but not evaluated." |

Checks before recording: every shot works on the branch you are recording; Hindi strings read naturally (they are drafts);
close other tabs; mute notifications. If Raju's live model is off, say "approved sentence" rather than "the model wrote it".
Screens 3–5 are on branch `faviana-noronha`, so record from that branch, not from `main`.
