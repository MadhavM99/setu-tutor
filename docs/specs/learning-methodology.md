# Learning methodology: principles, mechanics and evidence

Each principle is listed with the mechanic that makes it visible, the data that proves it is happening, and its evidence status. These are established findings delivered through a new mechanism. The **tested claim** is only that delivering them through a peer the learner corrects helps more than the matched alternatives. [P §5 p.8]

Tags: [P] paper · [P8b] newer paper copy · [X] prompt extension · [E] engineering recommendation.

| # | Principle | Mechanic | Proof in data | Source |
|---|---|---|---|---|
| 1 | **Cue-free recall** | Answers are typed (Telugu keyboard or Devanagari conversion). No options, word banks, pre-filled boxes or answer-bearing hints. The LMA hosted app's word tiles, pre-filled box and Yes/No-only choice are removed | `attempt.cue_level = none` on every scored attempt; UI test asserts there are no options | P-LSP-01, Bastani 2025 |
| 2 | **Self-explanation** | "पर ऐसा क्यों?" every 3rd checked fix (P8b-02), plus explanation tasks at L4. Scored deterministically on the rule's concept key: each required idea is a set of Hindi/Telugu tokens **with the required relation** (e.g. "क्या" + {नहीं लगता, हटाना} and "-ఆ / आ" + {अंत, आख़िर}). Keyword salad that names both ideas without the relation scores unsure → teacher | `verdict.kind = explanation`; concept-hit log | P-LSP-02, Alemdag 2025 (explained errors help more) |
| 3 | **Spacing** | FSRS for words and chunks; the mastery tracker for rules and skills. The classmate forgets a rule when the learner's predicted recall falls below 0.5, so review becomes re-teaching **days later, never seconds later** | `due_at`; re-plant events with `days_since_last` | P-LSP-03, Ye 2022, Hunziker 2019 |
| 4 | **Reverse re-teaching** | Due rule → classmate `forgotten` → the classmate plants that error again → the learner re-teaches | Classmate state transitions in the ledger | P core, P8b-01 |
| 5 | **Desirable difficulty** | Items at band b or b+1, TMR = 0 outside the target words | `item.band` vs `learner.band` | P-LSP-04 |
| 6 | **Interleaving** | Due rules mixed; no more than 2 consecutive turns on one rule | Session sequence log | P-LSP-05 |
| 7 | **Production** | ≥ 2 own-sentence tasks every session; unlocking L2+ needs a production success. Rationale: Shintani et al. 2013 (production-based instruction is more effective for productive knowledge on delayed tests) | `attempt.modality = PR` | P-SESS-04, P8b-08, R-17 |
| 8 | **Transfer** | Test items come from a held-out pool never seen in practice; own sentences in new scenes | Item-pool tags | P-EVAL-17 |
| 9 | **Written form with care** | Telugu script always shown. The Devanagari reading aid fades per rule after 3 correct answers. Misleading L1 letter habits are taught explicitly (short e/o, ళ, final vowel). Evidence: Escudero 2008 and Cerni 2019 (written forms help), Hayes-Harb 2021 (misleading L1 habits hurt). Audio is added for pronunciation; reading while listening alone gives no vocabulary advantage (TwiLex 2024) | Aid-visible flag per attempt; Hindi-typed counts | P8b-04/05/08 |
| 10 | **Scene and task context** | Scenes (auto stand, mess, landlord, everyday) carry the goals; new items capped at 5 per session | `session.new_items ≤ cap` | P-LSP-06, X-BEG-03/04 |
| 11 | **Hint before answer** | The hint ladder never reveals the answer in hint 1 (validated by `check_hint_has_no_answer`, incl. transliteration); the answer comes only after the 2nd miss | M-18 | P-SESS-10, Coyne 2025 |
| 12 | **Error exposure safety** | Every planted error ends shown corrected next to the error; copy rate measured per rule | M-37 | R-13 |
| 13 | **No "always an error" cue** | About 20% no-error turns, but only when a plantable rule exists (otherwise a production task); false alarms measured | M-36 | P-SESS-07, R-14, R-17 |

## Known risk the methodology must report: teaching may reduce production (R-17)

The newer paper copy's v0 simulation found condition A (teach Raju) < C (normal tutor) on delayed production under every assumption set. Once a rule is taught, Raju stops making the error until he forgets, so 83% of A turns became no-error, recognition-only turns. That result follows from the simulator's assumptions, not from people. The design responds without hiding it:
1. own sentences in every session;
2. the no-error share is capped, with production substituted when nothing is plantable;
3. the start threshold and forgetting are experimental parameters;
4. the pilot measures it.

## What is not claimed

- That the L0–L5 ladder or leveler is validated. [X-LEV-03]
- That simulated learners behave like people. [X-SIM-05]
- That contrast predictions match real learner errors (no rule is observed yet). [P-ETH-10]
- That teaching the classmate beats matched examples or a normal tutor. This is the open research question.
