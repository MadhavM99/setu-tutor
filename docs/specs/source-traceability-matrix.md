# Source-traceability matrix

Every requirement from the paper, every extension requested in the master prompt, and every engineering recommendation has one row here, under a stable ID. IDs are never reused. A retired row is marked `withdrawn` and stays in the table.

## Legend

**Kind**

| Code | Meaning |
|---|---|
| **P** | Requirement stated in the paper. Primary copy: `Downloads/…Paper_v8.pdf` (21 pp., uploaded). |
| **P8b** | Stated only in the newer team copy (`LMA/docs/paper/…v8.pdf`, 24 pp., 30 Oct). |
| **X** | Product extension requested in the master prompt. |
| **E** | Our own engineering recommendation. |

**Source** is a paper section, table or figure, or a prompt section. Page numbers refer to the uploaded copy.

**Status**: `V` verified · `P` partial · `M` missing · `B` broken · `NA` not applicable. Shown separately for **setu** (the product being rebuilt) and **LMA** (the reuse source). Evidence is in [`../audit/current-product-audit.md`](../audit/current-product-audit.md).

**Phase**: 0 = this package · 1 = foundations · 2 = deterministic core · 3 = learner slices · 4 = agents and consoles · 5 = speech and gates · 6 = pilot · R = roadmap, gated.

**Tests**: test-suite IDs defined in [`../quality/test-plan.md`](../quality/test-plan.md).

**Lifecycle**: `missing → built → tested → evaluated`. This column is updated as each row moves through implementation; at Phase 0 every row is at its audit status.

The acceptance criteria below are short forms of Given/When/Then. Full G/W/T statements are in each feature spec.

---

## 1. Architecture — P-ARCH (§4, Fig. 1, Table 8, pp. 6–7, 12)

| ID | Kind | Source | Requirement | setu | LMA | Ph | Deps | Acceptance (G/W/T) | Tests |
|---|---|---|---|---|---|---|---|---|---|
| P-ARCH-01 | P | §4 p.6 | Components that write (LLM: classmate, coach, friend) are separate from components that decide (planner, filter, checker) | P | V | 2 | — | G any model output, W processed, T no code path lets it change a verdict or state | TS-AUTH-01..05 |
| P-ARCH-02 | P | Fig.1, §5.1 | Deterministic planner: due rules plus mode, band b or b+1 | P | P | 2 | P-BANK-05, X-PERS-* | G learner state, W plan, T rule due and band ∈ {b, b+1}, deterministic for a fixed seed | TS-PLAN-01..08 |
| P-ARCH-03 | P | Fig.1 | Classmate agent writes 1 error, or none (~20%); ≤3 drafts with tool | P | V(mock) | 4 | P-TOOL-01 | G a planned item, W the agent runs, T ≤3 model calls, then a bank fallback | TS-AGT-01..06 |
| P-ARCH-04 | P | Fig.1 | Leak filter: seen words only (TMR = 0); exactly 1 error, or 0 | P | P | 2 | P-CLS-03..08 | See P-CLS rows | TS-LEAK-* |
| P-ARCH-05 | P | Fig.1, Table 8 | Normaliser: NFC + IndicXlit; script fading | P | P | 2 | P-DATA-07 | G romanised, Devanagari or Telugu input, W normalised, T canonical Telugu or flagged unsure | TS-NORM-01..10 |
| P-ARCH-06 | P | Fig.1 | Checker: rules + analyser, 4 verdicts, no LLM | P(3, loose) | P(3) | 2 | P-ARCH-05 | G an answer, W checked, T exactly one of correct/partial/wrong/unsure, with no model call | TS-CHK-* |
| P-ARCH-07 | P | Fig.1, Table 8 | Coach: hint in L1, 3 types, rule-checked before display | P | P | 3/4 | P-TOOL-03 | G a wrong fix, W hint 1, T no correct form, validated | TS-COACH-* |
| P-ARCH-08 | P | §4, Table 8 | Native friend agent with scene, word and level tools | P(unchecked) | M | 4 | P-TOOL-02 | G a scene, W the friend speaks, T every line passes check_level, else an approved scene line | TS-FRND-* |
| P-ARCH-09 | P | Fig.1 | Rule registry: versioned, both directions, reviewer and source | P | P | 1 | — | G a rule edit, W saved, T a new immutable version; the old one is kept | TS-BANK-01..06 |
| P-ARCH-10 | P | Fig.1 | Teacher queue: unsure → no update; rule sign-off | P | P | 4 | P-ARCH-11 | G an unsure verdict, W queued, T mastery and classmate state unchanged until resolved | TS-TQ-* |
| P-ARCH-11 | P | Fig.1, Table 8 | Memory: Postgres, learner×rule, FSRS, classmate notebook; checker is the only writer | M | M | 1/2 | E-01 | G any learning update, T written only by OutcomeWriter from a verdict or resolution | TS-AUTH-*, TS-DB-* |
| P-ARCH-12 | P | Table 8 | Scheduler: FSRS for words, mastery tracker for rules | P(stand-in) | P(stand-in) | 2 | E-04, E-05 | G review history, W scheduled, T FSRS due dates; tracker mean and uncertainty | TS-SCHED-* |
| P-ARCH-13 | P | Table 8, §4 | Speech: IndicConformer ASR, native recordings / Indic Parler-TTS; external services, not model tools | M | P(browser TTS) | 5 | X-SPEECH | G speech enabled, W used, T only called by the app; flag off until gate | TS-SPCH-* |
| P-ARCH-14 | P | Table 8 | Display checks: script, glossary, length, no leak | P | P | 2 | — | G any learner-visible model text, T it passes display checks or is replaced | TS-DISP-* |
| P-ARCH-15 | P | Table 8 | Contrast pipeline produces candidates only | M | M | R/6 | P-BANK-12..15 | G a pipeline output, T saved as `draft`, `model_predicted` or `predicted`, never active | TS-BANK-07 |
| P-ARCH-16 | P | Fig.1 | Optional "predict first" step | M | M | 4 | P-OPT-01 | See P-OPT-01 | TS-EXP-PRED |

## 2. Tools — P-TOOL (§4 p.6, Table 8)

| ID | Kind | Source | Requirement | setu | LMA | Ph | Deps | Acceptance | Tests |
|---|---|---|---|---|---|---|---|---|---|
| P-TOOL-01 | P | §4 p.6 | `check_classmate_sentence(item_id, sentence)`: pattern `(HI-TE\|TE-HI)-NNN-x`; a rule-id gets a specific error; one Telugu-script sentence of at most 120 chars; returns `{ok, reasons}`; re-checked on submit | M | V | 2 | P-ARCH-04 | G "HI-TE-002", T `ERROR invalid_argument item_id: "HI-TE-002" is a rule id; pass an item id like "HI-TE-002-a".`; G a valid sentence, T `{ok:true, reasons:[]}`; G submit, T re-validated | TS-TOOL-01..14 |
| P-TOOL-02 | P | Table 8 | `check_level` | M | M | 2 | X-LEV-01 | G content plus learner, T ok or fixed reasons (OOV, band, script, structure) | TS-TOOL-20..26 |
| P-TOOL-03 | P | Table 8 | `check_hint_has_no_answer` | M | M | 2 | P-ARCH-05 | G a hint containing the correct form in any script, T rejected | TS-TOOL-30..36 |
| P-TOOL-04 | P | Table 8, §4 | Read-only rule-bank lookup | M | P | 2 | E-01 | G a lookup, T read-only DB role, no write possible | TS-TOOL-40 |
| P-TOOL-05 | P | Table 8, §4 | Read-only learner-record lookups (seen words, band, accepted variants) | M | M | 2 | E-01 | as above | TS-TOOL-41..43 |
| P-TOOL-06 | P | §4 p.6 | JSON-envelope fallback when native tool calling is absent; the harness executes it | M | V | 4 | — | G a model without tool calling, T the envelope is parsed; malformed input gets a fixed error | TS-TOOL-50..55 |
| P-TOOL-07 | P | §4 | Fixed error strings that guide correction (wrong script, gloss, multiple sentences, malformed JSON, oversize) | P | V | 2 | — | G each invalid argument class, T the exact documented string | TS-TOOL-01..14 |
| P-TOOL-08 | P | §4, §9 | Agents can call only read-only tools | NA | V | 2 | E-01 | G any tool registry, T no write-capable tool registered | TS-AUTH-03 |

## 3. Model use and cost — P-COST (§4–5, p.7)

| ID | Kind | Source | Requirement | setu | LMA | Ph | Deps | Acceptance | Tests |
|---|---|---|---|---|---|---|---|---|---|
| P-COST-01 | P | §4 p.7 | The model chooses only: revise/submit, the friend's next line, the hint type | P | V | 4 | — | G the agent code, T no model output selects a verdict, item or schedule | TS-AUTH-* |
| P-COST-02 | P | §4 p.7 | Classmate turn ≈1 call, ≤3 | P | V | 4 | — | M-12 | TS-AGT-03 |
| P-COST-03 | P | §4 p.7 | ≈2 calls per exchange; 12–24 per session, ≤48 | M | P | 4 | — | M-13 | TS-AGT-07 |
| P-COST-04 | P | §4 p.7 | Calls per turn logged with model, prompt and rule versions | P | P | 1 | E-02 | G any model call, T a `model_call` row with all versions | TS-LOG-01 |

## 4. Session and exchange — P-SESS (§5, Table 3, p.7)

| ID | Kind | Source | Requirement | setu | LMA | Ph | Deps | Acceptance | Tests |
|---|---|---|---|---|---|---|---|---|---|
| P-SESS-01 | P | §5, Table 3 | About 12 exchanges in three parts, so every learner corrects and also produces | P | P | 3 | X-SESS-01 | G a learner session, T the configured mix is recorded; production occurs | TS-SESS-01 |
| P-SESS-02 | P | Table 3 | Same-direction correction (core) | P | V | 3 | P-CLS-* | G a HI speaker, T the classmate writes Telugu with HI→TE errors | TS-SESS-02 |
| P-SESS-03 | P | Table 3, §1 | Mirror mode: the classmate writes the learner's L1 using the other direction's rules; exploratory, reported separately | M | M | 4 | TE→HI bank | G mirror enabled, T Hindi sentence with a TE→HI error, tagged `mode=mirror` | TS-SESS-03 |
| P-SESS-04 | P | Table 3 | Own sentence: the learner writes Telugu | M | M | 3 | P-ARCH-06 | G an own-sentence task, T the checker judges it; unseen forms → unsure | TS-SESS-04 |
| P-SESS-05 | P | §5 step 1 | Plan: read memory, pick a due rule at b/b+1, choose mode | P | V | 2 | P-ARCH-02 | P-ARCH-02 | TS-PLAN-* |
| P-SESS-06 | P | §5 step 2 | Write: fill a rule template into a natural sentence and ask why | P | V | 4 | P-TOOL-01 | G a plan, T one sentence plus a Hindi question | TS-AGT-* |
| P-SESS-07 | P | §5 step 2 | No-error turns ≈1 in 5; zero errors; same filter | P | B(83%) | 2/3 | R-17 | G 100 eligible turns, T 15–25 no-error; each passes the zero-error check | TS-PLAN-05, TS-LEAK-NE |
| P-SESS-08 | P | §5 step 3 | Fix: correct and explain in either language | P | P | 3 | — | G a fix in Telugu or Devanagari script, T accepted for checking | TS-NORM-* |
| P-SESS-09 | P | §5 step 4 | Check: NFC + IndicXlit, bank forms and variants, targeted analyser | P | P | 2 | P-ARCH-05/06 | P-ARCH-06 | TS-CHK-* |
| P-SESS-10 | P | §5 step 5 | Respond: correct → classmate learns (k=1); partial/wrong → L1 hint, answer after 2nd miss; unsure → queue | B(hint leaks) | P | 3 | P-ARCH-07 | G 1st miss, T hint without the answer; G 2nd miss, T answer; G correct, T classmate taught | TS-EXCH-* |
| P-SESS-11 | P | §5 step 6 | Update: the checker writes learner×rule memory and classmate state | P | V | 2 | E-01 | P-ARCH-11 | TS-AUTH-* |
| P-SESS-12 | P | §5 | "Both sides ask questions": the classmate asks why; the learner explains | P | P | 3 | P8b-02 | G an exchange, T the classmate asks why; the learner's explanation is scored | TS-EXCH-WHY |
| P-SESS-13 | P | §5 | ≈6 s and 2 calls per exchange | M | M | 5 | — | M-27, M-12 | TS-PERF-01 |

## 5. Classmate — P-CLS (§5 pp.7–8)

| ID | Kind | Source | Requirement | setu | LMA | Ph | Deps | Acceptance | Tests |
|---|---|---|---|---|---|---|---|---|---|
| P-CLS-01 | P | §5 p.7 | Explicit per-learner state: VL, rule states unknown/taught/forgotten, currently planted rule; stored in the DB, not the prompt | P | P | 2 | P-ARCH-11 | G a learner, T `classmate_rule_state` rows; the VL view derives from the learner's seen forms | TS-CLS-01..05 |
| P-CLS-02 | P | §5 p.7 | Guided JSON output naming the planted rule and the words used | M | P | 4 | — | G a model reply, T the JSON schema is validated; words used are logged | TS-AGT-04 |
| P-CLS-03 | P | §5 (a), Eq.1 | Reject if TMR > 0 outside the target words of the planted rule | P(char-level) | P(OOV, no TMR) | 2 | P-DIFF-03 | G a sentence with an unseen word, T reason `OOV`; TMR is stored with the tokenizer version | TS-LEAK-01..06 |
| P-CLS-04 | P | §5 (b) | Reject unless exactly one error, of the planted rule | P | V | 2 | — | G 0 or 2 errors, or the wrong rule, T `NOT_ONE_ERROR` | TS-LEAK-10..14 |
| P-CLS-05 | P | §5 (c) | Reject if it correctly applies a rule it doesn't know (bank patterns) | M | V | 2 | — | T `UNKNOWN_RULE_CORRECT` | TS-LEAK-20..22 |
| P-CLS-06 | P | §5 (d) | Reject an answer leak (correct form or its explanation) | P(no translit) | V | 2 | — | G the correct form in Telugu or Devanagari, T `ANSWER_LEAK` | TS-LEAK-30..35 |
| P-CLS-07 | P | §5 (e) | Reject grammar explanations (teacher role) | P | V | 2 | — | T `EXPLANATION` | TS-LEAK-40..43 |
| P-CLS-08 | P | §5 | Replies after a fix pass the same filter; only the just-taught form may be used | P | P | 2 | — | G a reply using another rule's correct form, T rejected | TS-LEAK-50..52 |
| P-CLS-09 | P | §5 p.7 | One personal classmate per learner, derived from that learner's record | V | V | 2 | — | G two learners, T independent states | TS-CLS-06 |
| P-CLS-10 | P | §5 pp.7–8 | Rule reaches the classmate only after the learner was taught it and got it right once; beginners learn first; teaching starts after a few rules; a pre-test-known rule is teachable at once; never knows more than the learner; forgets on the learner's tracker | P | P | 2/3 | X-CLS-START | G an untaught rule, T never `taught`; G learner p<0.5, T `forgotten`; G pre-test correct, T teachable | TS-CLS-07..14 |

## 6. Learning-science principles — P-LSP (§5 p.8)

| ID | Kind | Source | Requirement | setu | LMA | Ph | Deps | Acceptance | Tests |
|---|---|---|---|---|---|---|---|---|---|
| P-LSP-01 | P | §5 | Cue-free recall: typed correction, no options or word banks | P(hint leaks) | B(hosted word tiles, Yes/No) | 3 | — | G any scored item, T no options, word bank or answer-bearing hint on screen | TS-UI-CUE-01..04 |
| P-LSP-02 | P | §5 | Self-explanation: the reason is scored on the rule's key idea, deterministically | B(gameable) | P | 2 | X-BANK-03 | G keyword salad, T not correct; G a valid paraphrase, T correct or unsure | TS-WHY-01..12 |
| P-LSP-03 | P | §5 | Spacing: the classmate forgets when due, so review is re-teaching days later | P | P(never fired) | 3 | P-ARCH-12 | G a rule due on day d, T re-planted on day ≥ d, never in the same session | TS-SCHED-10 |
| P-LSP-04 | P | §5 | Desirable difficulty: band b or b+1 | M | P | 2 | X-LEV | P-ARCH-02 | TS-PLAN-03 |
| P-LSP-05 | P | §5 | Interleaving: due rules mixed within a session | M | P | 2 | — | G ≥2 due rules, T no more than 2 consecutive turns on the same rule | TS-PLAN-06 |
| P-LSP-06 | P | §5 | Scenes (auto stand, mess, landlord) with a capped number of new items | P | M | 3 | X-BEG-04 | G a session, T new items ≤ cap | TS-SESS-05 |
| P-LSP-07 | P | §5 | Hindi head start: letter twins, पुस्तक/పుస్తకం, अवसर/అవసరం false friend | P | P | 3 | X-BEG-01/02 | G an L0 learner, T twins first; false friends flagged | TS-CONT-01 |

## 7. Options under test — P-OPT (§5 p.8)

| ID | Kind | Source | Requirement | setu | LMA | Ph | Deps | Acceptance | Tests |
|---|---|---|---|---|---|---|---|---|---|
| P-OPT-01 | P | §5 (i) | Predict-then-check: the learner commits a prediction; both prediction and fix are scored | M | M | 4 | — | G the flag is on, T the prediction is captured before the sentence; both are scored | TS-EXP-PRED |
| P-OPT-02 | P | §5 (ii) | Script fading as the band rises | P | P | 3 | P8b-05 | G 3 correct answers on a rule, T the aid is hidden for that rule | TS-UI-FADE |
| P-OPT-03 | P | §5 (iii) | Hint type (recast, L1 rule, contrast) as separate conditions | M | M | 4 | P-ARCH-07 | G a hint-type arm, T only that type is served | TS-EXP-HINT |
| P-OPT-04 | P | §5 (iv) | Forgetting classmate on/off | M | P | 4 | — | G forgetting off, T the classmate never forgets; equal practice | TS-EXP-FORGET |

## 8. Difficulty — P-DIFF (§6.1 p.8)

| ID | Kind | Source | Requirement | setu | LMA | Ph | Deps | Acceptance | Tests |
|---|---|---|---|---|---|---|---|---|---|
| P-DIFF-01 | P | §6.1 | Leveler v0 = the hardest of script, TMR, word forms, structure; unvalidated; labels items and picks the next band | M | M | 2 | X-LEV-01 | G an item, T band plus the dimension that set it | TS-LEV-01..05 |
| P-DIFF-02 | P | §6.1 | Each item's band (L0–L2) agreed by two native speakers | M | M | 6 | Reviewers | G an active item, T two speaker band labels recorded | TS-BANK-08 |
| P-DIFF-03 | P | Eq.1 | TMR(s) = \|{w∈s : w∉VL}\| / \|s\|, where VL = words the learner has met | M | M | 2 | E-tokenizer | G a sentence and VL, T exact TMR, with tokenizer version stored | TS-TMR-01..06 |

## 9. Error bank and contrast table — P-BANK (§6.2–6.3, Tables 4 and 6, Fig. 2)

| ID | Kind | Source | Requirement | setu | LMA | Ph | Deps | Acceptance | Tests |
|---|---|---|---|---|---|---|---|---|---|
| P-BANK-01 | P | §6.2 | One contrast table feeds both directions' rule books | M | P | 1 | — | G a contrast, T linked rules per direction | TS-BANK-01 |
| P-BANK-02 | P | §6.2 | Rule holds template, wrong and correct forms, L1 explanation, band | P | P | 1 | — | Schema validation | TS-BANK-02 |
| P-BANK-03 | P | Table 4 | Validity: verified / uncertain / rejected | M | M | 1 | — | Schema enum | TS-BANK-03 |
| P-BANK-04 | P | Table 4 | Learner evidence: model_predicted / predicted / proxy / observed / replicated; **never merged** with validity | M | P(merged with status) | 1 | — | Separate columns; no derived merge | TS-BANK-03 |
| P-BANK-05 | P | §6.2 | Only verified rules are planted; learner evidence sets priority | M(no gate) | M | 2 | P-BANK-03 | G a non-verified rule, T never planted in learner mode | TS-PLAN-07 |
| P-BANK-06 | P | §6.2 | Version, reviewer, review date, source; a correction creates a new version | P | P | 1 | — | G an edit, T new `rule_version`; old row immutable | TS-BANK-04 |
| P-BANK-07 | P | §6.2 | Every logged turn records rule, model and prompt versions | P | B(not persisted) | 1 | E-02 | G a turn, T versions are in the `exchange` and `model_call` rows | TS-LOG-02 |
| P-BANK-08 | P | §6.2 | Error rates per opportunity, never raw counts | M | M | 4 | — | G the analytics view, T k/n shown | TS-TCH-AN-01 |
| P-BANK-09 | P | §6.2 p.8 | TH-GEN-01 (TE→HI) and TH-CLU-01 (HI→TE) stay `uncertain/draft` | NA | NA | 1 | — | G import, T both present as uncertain/draft; band 3 vs L0–L2 discrepancy logged | TS-BANK-09 |
| P-BANK-10 | P | §6.2 | Shared-word layer (Kanojia): look-alikes, loans, false friends; lexical errors; cognates scaffold | P(6 false friends) | M | 3 | P-DATA-06 | G the lexeme table, T cognate and false-friend flags with source | TS-CONT-02 |
| P-BANK-11 | P | §6.2 | Rules observed in the pilot feed mirror mode for the other group | M | M | R | P-SESS-03 | G an observed TE→HI rule, T available to mirror | TS-SESS-03 |
| P-BANK-12 | P | §6.3 | Layer 1: WALS/Grambank differences are leads only | NA | NA | R | — | G a lead, T stored as a candidate, not a rule | TS-BANK-07 |
| P-BANK-13 | P | §6.3 | Layer 2: reference grammars + 2 speakers per language; MT-divergence checklist | M | P(book examples) | 6 | Reviewers | G promotion, T 2 speaker approvals per language | TS-BANK-10 |
| P-BANK-14 | P | §6.3 | Layer 3: LTRC parallel corpus shows how each contrast is realised; licence check | M | M | R | P-DATA-05 | G corpus use, T licence status recorded | TS-DSR-01 |
| P-BANK-15 | P | §6.3 | LLM-proposed errors stay `model_predicted` until a teacher approves | P | P | 1 | — | G an LLM proposal, T evidence = model_predicted, lifecycle = draft | TS-BANK-11 |
| P-BANK-16 | P | Table 6 | Contrast: gender on adjectives, possessives, verbs (TE→HI) | NA | P(TE-HI draft) | 1 | — | Rule family present, uncertain | TS-BANK-12 |
| P-BANK-17 | P | Table 6 | Contrast: 3rd-person pronoun gender అతను/ఆమె/అది (HI→TE) | P | P | 1 | — | as above | TS-BANK-12 |
| P-BANK-18 | P | Table 6 | Contrast: negation (separate particle vs verbal affix), both directions | P | P | 1 | — | as above | TS-BANK-12 |
| P-BANK-19 | P | Table 6 | Contrast: polar questions (initial क्या vs final -ā) | P | P | 1 | — | as above; fix the HI-TE-001 planted form (Hindi word in Telugu script) | TS-BANK-12 |
| P-BANK-20 | P | Table 6 | Contrasts: copula; relative clauses (जो…वो); "we" incl./excl.; possession | P | P | 1 | — | as above; fix HI-TE-010-a (multiple errors) | TS-BANK-12 |
| P-BANK-21 | P | Table 6 | Contrast: ergative ने (from learner evidence only; Chinnappa 1978) | P | P | 1 | — | as above | TS-BANK-12 |
| P-BANK-22 | P | Table 6 | Contrasts: adverbial clauses; respect agreement (మీరు) | M/P | P | 1 | — | as above | TS-BANK-12 |
| P-BANK-23 | P | Table 6 | Contrast: "she"/"it" (ఇది for a woman) | M | M | 1 | — | as above | TS-BANK-12 |
| P-BANK-24 | P | Table 6 | Contrast: new sounds ళ, short ఎ/ఒ (కళ్ళు vs కల్లు) | P(letters) | P(script) | 1/3 | — | as above | TS-BANK-12 |

## 10. Typology check — P-TYP (§6.4, Table 5, pp. 9–10)

| ID | Kind | Source | Requirement | setu | LMA | Ph | Deps | Acceptance | Tests |
|---|---|---|---|---|---|---|---|---|---|
| P-TYP-01 | P | Table 5 | Record WALS κ = 0.442 (Telugu rank 38/691) and Grambank κ = −0.025 (rank 796/2,245); **don't assume similarity predicts errors** | NA | NA | 0 | — | Documented in content-and-error-bank.md; no feature uses global similarity | Doc review |
| P-TYP-02 | P | §6.4 | Family vs contact left open; caveats (noisy coding, correlated features, κ ignores dependence) | NA | NA | 0 | — | Documented | Doc review |
| P-TYP-03 | P | §6.4 | The ergative ने row comes from learner evidence, not the databases | NA | NA | 1 | — | The rule's source cites Chinnappa; evidence = proxy | TS-BANK-12 |

## 11. Data sources — P-DATA (Table 7, §6.5, pp. 10–11)

All rows: data-source register entry with licence, permitted use, provenance and limits. Detail in [`../research/data-source-register.md`](../research/data-source-register.md).

| ID | Kind | Source | Requirement | setu | LMA | Ph | Deps | Acceptance | Tests |
|---|---|---|---|---|---|---|---|---|---|
| P-DATA-01 | P | Table 7 | Native speakers, Krishnamurti & Gwynn 1985, Chinnappa 1978 for rules | P(Claude drafts) | P | 1/6 | — | Register entry; every rule cites a source | TS-DSR-01 |
| P-DATA-02 | P | Table 7, §6.5 | Telangana Tenepalukulu (I–V) and Vennela (VI–X): order only, no copying | M | M | 3 | — | Register entry; no copied sentences (provenance field) | TS-DSR-02 |
| P-DATA-03 | P | Table 7 | IndicCorp v2 frequencies → top 1,000–2,000 words | M | M | 3 | — | Lexeme frequency rank with source | TS-CONT-03 |
| P-DATA-04 | P | Table 7, §6.5 | IndicGEC Telugu (~1,000 native pairs): checker robustness only | M | M | 4 | — | Used only in TS-CHK-ROB; never as learner evidence | TS-CHK-ROB |
| P-DATA-05 | P | Table 7 | LTRC Hindi–Telugu parallel corpus (~700K pairs; a few hundred simple pairs); licence | M | M | R | — | Register, licence status | TS-DSR-01 |
| P-DATA-06 | P | Table 7 | Kanojia et al. cognates and false friends, ~150 words | P | M | 3 | — | 150 lexemes with flag and source | TS-CONT-02 |
| P-DATA-07 | P | Table 7 | IndicXlit / Aksharantar for romanised input | M | M | 2 | — | Adapter plus pinned model version | TS-NORM-05..08 |
| P-DATA-08 | P | Table 7 | LTRC Telugu analyser / Stanza, tested on 50 sentences first | M | M | 4 | — | 50-sentence evaluation report before use | TS-ANA-01 |
| P-DATA-09 | P | Table 7 | Test suite ~150 cases, 30% held out | P | P(63, rewritten split) | 2 | — | ≥150 cases; split frozen with a hash manifest | TS-SUITE-META |
| P-DATA-10 | P | Table 7 | Simulated learners, 20 per condition | NA | V(v0) | 4 | — | 60 baseline runs | TS-SIM-* |
| P-DATA-11 | P | Table 7 | 5 adult Hindi speakers learning Telugu in Hyderabad | NA | NA | 6 | Ethics | Pilot roster | — |

## 12. Models — P-MODEL (§7, p.11)

| ID | Kind | Source | Requirement | setu | LMA | Ph | Deps | Acceptance | Tests |
|---|---|---|---|---|---|---|---|---|---|
| P-MODEL-01 | P | §7 | Gemma 3 12B, 4-bit, on vLLM or Ollama, as released (baseline, not hard-coded) | B(Gemini/Gemma 4 cloud) | P(client only) | 4 | GPU host | Model id configurable; recorded per call | TS-LLM-01 |
| P-MODEL-02 | P | §7 | Sarvam-M as a per-direction comparison only | M | M | 4 | — | Bake-off report per direction | TS-BAKE-01 |
| P-MODEL-03 | P | §7, §14 prompt | No fine-tuning in this phase; teacher-approved logs become preference data later | V | V | — | — | No training code paths | Doc review |
| P-MODEL-04 | P | §7 | Hidden short plan before classmate output, as an ablation only | M | M | 4 | — | Flag; planting precision vs latency report | TS-EXP-PLAN |
| P-MODEL-05 | P | §7 | Worked examples retrieved from the approved bank, never self-generated | P | P | 4 | — | Prompts contain only bank content | TS-AGT-05 |
| P-MODEL-06 | P | §2 p.4 | A smaller model is not used as the weak classmate | V | V | — | — | Documented in ADR-0004 | Doc review |

## 13. Implementation status reconciliation — P-STAT (§7, p.12)

| ID | Kind | Source | Requirement | setu | LMA | Ph | Deps | Acceptance | Tests |
|---|---|---|---|---|---|---|---|---|---|
| P-STAT-01 | P | §7 p.12 | Paper status: 4 contracts, 15 HI→TE rules / 29 items, checker (3 verdicts), filter, classmate state, no-error turns, ledger, recall model, fixed hints, tool, client and mock, CLI, web page; 79 tests (112 in P8b) | — | — | 0 | — | Reconciled in the audit §6: LMA has 116 tests, the docs say 112 | Audit |
| P-STAT-02 | P | §7, §10 | Planned 15 + 10 rules × 10 items (250) vs 29 + 20 items existing: content-count discrepancy | — | — | 1 | — | Tracked as DQ-01 in content-and-error-bank.md | TS-BANK-13 |

## 14. Evaluation — P-EVAL (§8, pp. 12–13)

| ID | Kind | Source | Requirement | setu | LMA | Ph | Deps | Acceptance | Tests |
|---|---|---|---|---|---|---|---|---|---|
| P-EVAL-01 | P | §8.1 | Stage A suite of ~150 cases in 4 groups: leak, planting, checker, forgetting | P | P(63) | 2 | — | ≥150 cases, each tagged with a group | TS-SUITE-META |
| P-EVAL-02 | P | §8.1 | Suite runs on every change to prompts, rules or code | M | P | 1 | E-CI | A CI job runs on every PR | CI |
| P-EVAL-03 | P | §8.1 | 30% held out for final numbers | M | B | 2 | — | Frozen manifest; dev runs never read held-out labels | TS-SUITE-SPLIT |
| P-EVAL-04 | P | §8.1 | Prompt-only classmate baseline with the same model | M | P(script) | 4 | P-MODEL-01 | Baseline leak rate reported | TS-ABL-01 |
| P-EVAL-05 | P | §8.1 | 3-variant agent ablation: prompt-only / blind resampling / tool loop | M | P | 4 | — | Report with M-10/11/01/02/12 per variant | TS-ABL-02 |
| P-EVAL-06 | P | §8.1 | Red-team: learner-text injection and hijacked reply; target 0 state changes | P | P(4 mock) | 2/4 | — | M-14 = 0 on ≥30 attacks | TS-RED-* |
| P-EVAL-07 | P | §8.1 | TransferErrorBench: teacher-marked held-out planted errors and fixes, both directions | M | M | 4/6 | Teachers | Bench file plus a datasheet | TS-TEB |
| P-EVAL-08 | P | §8.1 | Annotation guidelines, splits, rule versions and scoring documented; test items kept apart from build data | M | P | 2 | — | Datasheet; leakage check | TS-SUITE-LEAK |
| P-EVAL-09 | P | §8.1 | Contrast validity à la Berzak: preregistered predictions; HiLearners L1 groups; permutation and average-of-others baselines; no Telugu claim without L1 labels | M | M | R | HiLearners labels | Prereg file; analysis script | TS-ANL-VAL |
| P-EVAL-10 | P | §8.1 | Adult learner writing: permission and consent, anonymised, wording kept; 2 reviewers + 3rd mark span, correction, category, transfer plausibility; not every error is transfer | M | M | R/6 | Ethics | Annotation protocol; κ reported | TS-ANN-01 |
| P-EVAL-11 | P | §8.1 | Teacher rule-review form (acceptable/natural, category, explanation, band, confidence) | M | P(reviewer pack) | 4 | — | The form in the teacher console stores all 5 answers | TS-TCH-REV |
| P-EVAL-12 | P | §8.2 | Stage A2: simulated learners with explicit memory, used only as tests of the machinery | NA | V(v0 parametric) | 4 | X-SIM | See X-SIM rows | TS-SIM-* |
| P-EVAL-13 | P | §8.3 | Stage B: 5 adults, descriptive only (effect sizes, CIs, no significance) | NA | NA | 6 | Gates | The report contains no p-value claims | Doc review |
| P-EVAL-14 | P | §8.3 | Latin square balances rules and learners | NA | B(rotation) | 4 | — | Balanced 3×3 square; each rule appears in each condition across learners | TS-STUDY-01 |
| P-EVAL-15 | P | §8.3 | Conditions A (teach peer), B (matched error examples), C (normal tutor), matched for items, time and feedback | NA | B(asymmetric aids) | 4 | — | Same aids, time box, hints and items per condition | TS-STUDY-02..05 |
| P-EVAL-16 | P | §8.3 | One mode per condition in the study (not the 3-part session) | NA | P | 4 | — | Study session config = a single mode | TS-STUDY-06 |
| P-EVAL-17 | P | §8.3 | Pre-test, immediate post-test, one-week unaided production test, unseen-sentence transfer test | NA | B(items not unseen) | 4 | — | Test items drawn from the held-out pool, never shown in practice | TS-STUDY-07 |
| P-EVAL-18 | P | §8.3 | Production marked blind to condition with a preregistered rubric, outcomes and analysis | NA | B(sheet not blind) | 4/6 | — | Shuffled, condition-free export with random ids | TS-STUDY-08 |
| P-EVAL-19 | P | §8.3 | RQ1 teach vs B/C; RQ2 predictions vs observed; RQ3 by direction; RQ4 checker reliability vs prompt-only agent | NA | NA | 6 | — | Each RQ has an analysis script | TS-ANL-* |
| P-EVAL-20 | P | §8.3 | Log copy of planted errors, time on task, effort, incorrect feedback | M | P | 3 | — | Fields in `attempt` and `session` | TS-LOG-03 |
| P-EVAL-21 | P | §8.3 | Exploratory arms: mirror, forgetting vs remembering, predict-then-check, hint type | M | M | 4 | — | Flags; reported separately | TS-EXP-* |
| P-EVAL-22 | P | §8.3 | Sample size by power analysis from Stage A and pilot; learners and rules as random effects | NA | NA | 6 | — | Power script; mixed-model script | TS-ANL-POW |

## 15. Metrics — M (Table 9, pp. 13–14, plus P8b and X)

The target is fixed before any data is seen. System metrics are computed on the held-out set, per direction. Full definitions are in [`../research/metrics-and-gates.md`](../research/metrics-and-gates.md).

| ID | Kind | Area | Metric | Target | setu | LMA | Ph |
|---|---|---|---|---|---|---|---|
| M-01 | P | Classmate | Leak rate (unseen word, unknown rule used correctly, answer or explanation given) | < 2% and below prompt-only | M | P(mock 0%) | 4 |
| M-02 | P | Classmate | Planting precision (exactly one error of the planted rule) | ≥ 0.8 | M | P(1.0 mock) | 4 |
| M-03 | P | Classmate | Persona breaks | ≤ 5% | M | M | 4 |
| M-04 | P | Classmate | Due rule planted again | ≥ 0.95 | M | P | 2 |
| M-05 | P | Classmate | No-error turns contain zero errors | 100% | M | P | 2 |
| M-06 | P | Classmate | State changes only after a checked correct fix (none after bare "wrong" or a wrong fix) | 100% | P | V | 2 |
| M-07 | P | Checker | Wrong fixes caught | ≥ 0.9 | M | P(n=8) | 2 |
| M-08 | P | Checker | Right fixes rejected | < 5% | M | P | 2 |
| M-09 | P | Checker | Unsure rate | < 15% | M | B(20%) | 2 |
| M-10 | P | Agents | First-draft pass rate, per variant | Reported | M | M | 4 |
| M-11 | P | Agents | Bank-fallback rate, per variant | Lowest with tools | M | M | 4 |
| M-12 | P | Cost | Model calls per turn (mean, max) | ≈ 1–2 | P | B(1.14 artefact) | 4 |
| M-13 | P | Cost | Model calls per 12-exchange session (mean, max) | ≤ 48 | M | M | 4 |
| M-14 | P | Security | Injection attacks that change verdict, memory or classmate state | 0 | P | P | 2/4 |
| M-15 | P | Security | Unsafe text shown | Reported | M | M | 4 |
| M-16 | P | Checker | Agreement with teacher verdicts | κ ≥ 0.6 | M | M(0 labels) | 6 |
| M-17 | P | Checker | Unsure verdicts that changed mastery | 0 | V | V | 2 |
| M-18 | P | Coach | Hints that give the answer | < 2% | B | B | 3 |
| M-19 | P | Coach | Learners solved after one hint | ≥ 50% | M | M | 6 |
| M-20 | P | Coach | Teacher hint-quality rating | ≥ 4/5 | M | M | 6 |
| M-21 | P | Friend | Words outside the learner's band | < 5% | M | M | 4 |
| M-22 | P | Friend | Hindi share per session | Reported | M | M | 4 |
| M-23 | P | Tracker | Next-attempt prediction AUC / log-loss | Beats BKT | M | M | 4 |
| M-24 | P | FSRS | Recall prediction | Beats SM-2 | M | M | 4 |
| M-25 | P | Speech | WER on Hindi-accented Telugu | Below Whisper | M | M | 5 |
| M-26 | P | Speech | Sound check vs teacher | κ ≥ 0.6 (when evaluated) | M | M | R |
| M-27 | P | Loop | p95 time per exchange | < 10 s | M | M | 5 |
| M-28 | P | Loop | Cost per session | Reported | M | M | 5 |
| M-29 | P | Bank | Reviewer agreement on error category | κ ≥ 0.6 | M | M | 6 |
| M-30 | P | Bank | Predicted vs observed error types (precision/recall) | Beats both baselines before claiming predictive value | M | M | R |
| M-31 | P | Simulation | Cue-free recall on days 0, 1, 2, 7 by condition | Reported | NA | P(post + week) | 4 |
| M-32 | P | Simulation | Learning from unchecked answers | 0 | NA | V | 4 |
| M-33 | P | Learners | One-week cue-free production per rule by condition (primary) | Hedges' g with 95% CI | NA | NA | 6 |
| M-34 | P | Learners | Immediate post-test | Reported by condition | NA | NA | 6 |
| M-35 | P | Learners | Transfer to unseen sentences | Reported by condition | NA | NA | 6 |
| M-36 | P | Learners | False alarms on no-error turns | Reported by condition | M | P | 3 |
| M-37 | P | Learners | Copy rate of planted errors in later production, per rule | < 5% per rule | M | P | 3/6 |
| M-38 | P | Experience | System Usability Scale | Reported | M | P(hosted form) | 6 |
| M-39 | P | Experience | Time on task | Reported | M | P | 3 |
| M-40 | P | Experience | Would use again | Reported | M | P | 6 |
| M-41 | P | Validation | Learner and teacher interviews | 5–8 | NA | P(guide) | 6 |
| M-42 | P | Validation | Concrete commitments (second session, pilot, willingness to pay) | Reported | NA | M | 6 |
| M-43 | P | Human review | Blind marking agreement | κ ≥ 0.6 | NA | M | 6 |
| M-44 | P | Human review | Rule review form results | Reported | NA | P | 6 |
| M-45 | P | Human review | Naturalness of classmate and friend Telugu (1–5) | ≥ 4 | NA | M | 6 |
| M-46 | P8b | Classmate | Selective flip score FT − ½(FM + FG) | Reported (1.0 by construction with a mock) | NA | V(mock) | 4 |
| M-47 | P8b | Classmate | RMSE and controllability against target knowledge | Reported | NA | V(mock) | 4 |
| M-48 | P8b | Classmate | Guidance responsiveness | Reported | NA | V(mock) | 4 |
| M-49 | P8b | All | Scorecard lists every metric vs target and the gaps | Generated on every run | NA | V | 4 |
| M-50 | X | Ladder | Retention by skill (cue-free recall at delay, per skill and modality) | Reported | M | M | 3 |
| M-51 | X | Leveler | Leveler vs teacher bands | κ ≥ 0.6 before "validated" | M | M | R |
| M-52 | X | Placement | Placement accuracy (placed skills confirmed on first review) | Reported; target set after the pilot | M | M | 3 |
| M-53 | X | Ladder | Time to mastery per skill; prerequisite revisit rate | Reported | M | M | 3 |
| M-54 | X | UI | Learner-visible Latin-script strings | 0 (lint) | B | B | 1 |
| M-55 | X | Checker | Accuracy on IndicGEC robustness set (false accept / false reject) | Reported | M | M | 4 |
| M-56 | X-A1 | Classmate | Persona breaks **shown** to learners (assistant or teacher register, formatting, gloss) | 0 | B | P | 2/4 |
| M-57 | X-A1 | Memory | Ungrounded facts passing `check_mnemonic_grounding` on a held-out adversarial set (≥ 60 drafts) | 0 | B | M | 2 |
| M-58 | X-A1 | Memory | Shown images in which OCR or a reviewer finds embedded text | 0 | B | M | 4 |
| M-59 | X-A1 | Memory | Shown aids with Hindi alt text and an audio alternative | 100% | M | M | 4 |
| M-60 | X-A1 | Memory | Active concepts with a non-generative fallback aid | 100% | M | M | 3 |
| M-61 | X-A1 | Memory | Per-aid and per-technique effect on cue-free recall at ≥ 1 and ≥ 7 days (micro-randomised) | Reported with CI; flag harm | M | M | 4 |
| M-62 | X-A1 | Memory | Generation cost per approved asset; spend vs budget | ≤ budget; reported | M | M | 4 |
| M-63 | X-A1 | Memory | Incorrect associations (responses equal to an aid's declared lure) per aid and technique | Reported; in Study M ≤ M-A + 5 pp | M | M | 4/6 |
| M-64 | X-A1 | Study M | 7-day cue-free production, M-B, M-C, M-D vs M-A | Hedges' g + 95% CI | NA | NA | 6 |
| M-65 | X-A1 | Study M | Immediate, 1-, 7- and 30-day retention; transfer; unaided production by condition | Reported | NA | NA | 6 |
| M-66 | X-A1 | Study M | Time to mastery by condition | Reported | NA | NA | 6 |
| M-67 | X-A1 | Reverse study | Aid exposures per rule balanced across A, B and C | Equal (max difference 0) | NA | NA | 4 |
| M-68 | X-A1 | Memory | Cue-free recall after fading to level 0 (per concept type) | Reported | M | M | 3 |

## 16. Risks — R (Table 10, p.15, plus prompt §13)

| ID | Kind | Risk | Mitigation (implemented where) | Ph | Tests / metric |
|---|---|---|---|---|---|
| R-01 | P | No published Hindi→Telugu errors | Separate evidence fields; Dravidian proxies; learner writing; pilot data; direction reported as exploratory | 1/6 | TS-BANK-03 |
| R-02 | P | Contrast predictions miss real errors | Validity test; promotion only after observed data; unexpected errors kept | R | M-30 |
| R-03 | P | Small review panel | 2 raters per language; Cohen's κ; 3rd reviewer for disputes | 4/6 | M-29, TS-TCH-KAPPA |
| R-04 | P | Typology databases thin or noisy for Telugu | Differences are leads only; checked against a grammar and a speaker | R | P-BANK-12 |
| R-05 | P | Local Hyderabad Hindi differs from textbook Hindi | Local speakers review gold forms and variants; checker accepts listed variants | 6 | TS-CHK-VAR |
| R-06 | P | Weak Telugu generation | Template filling; bank fallback; per-direction model bake-off | 4 | M-11, TS-BAKE |
| R-07 | P | Checker cannot judge free explanations | Concept check on the key idea only; else unsure → teacher | 2 | TS-WHY-* |
| R-08 | P | Mirror mode may not transfer | Exploratory only; core is same-direction | 4 | P-SESS-03 |
| R-09 | P | Teaching effect confused with seeing explained errors | Matched condition B (same items, explanations, time) | 4 | TS-STUDY-02..05 |
| R-10 | P | Learner writing carries personal data | Institutional permission; anonymised; pseudonymous ids; own server; no external AI | 1 | TS-PRIV-* |
| R-11 | P | Checker accepts a wrong Telugu fix (worst failure) | Native-checked rules; false-accept target; blind teacher marking; unsure abstention | 2/6 | M-07, M-16 |
| R-12 | P | Prompt injection (learner text, hijacked model) | No authority; learner text never in the classmate prompt; all output filtered; read-only tools; red team | 2/4 | M-14, TS-RED-* |
| R-13 | P | Learners copy planted errors | Every planted error shown corrected at the end; copy rate per rule | 3 | M-37, TS-EXCH-END |
| R-14 | P | Learners learn that there is always an error | ~20% no-error turns; false alarms measured | 2/3 | M-36 |
| R-15 | P | No clear user or buyer | 5–8 week-one interviews; record commitments | 6 | M-41, M-42 |
| R-16 | P | Short timeline | Build against mocks; gate before learners; "built, not evaluated" label | all | X-GATE-02 |
| R-17 | P8b | Teaching Raju reduces production practice (83% no-error turns; A < C in simulation) | Own sentence in every session; no-error share controlled; production substituted when nothing is plantable; reported, not hidden | 2/3 | TS-PLAN-05, M-31 |
| R-18 | E | All content is unreviewed drafts, which blocks the gate | Native review is the critical path in the implementation plan; dev mode is flagged and never shown to pilot learners | 1/6 | G3 |
| R-19 | E | Solo capacity vs scope | Sequenced slices; roadmap items gated; scope cuts recorded, not hidden | all | Milestone reports |
| R-20 | E | Self-hosted models need a GPU | Mock-first development; Ollama 4B for dev; 12B on a rented or institute GPU for evaluation | 4 | P-MODEL-01 |
| R-22 | X-A1 | Mnemonics create incorrect associations (keyword or false-friend lures) | Declared lures per aid; misassociation logging; harm flag and retirement; false-friend aids must show the contrast | 3/4 | M-63 |
| R-23 | X-A1 | Learner data leaks to an external image service | Offline concept-level generation only; allow-listed request schema; no runtime client (ADR-0005) | 1/4 | TS-IMG-03, TS-PRIV-07 |
| R-24 | X-A1 | Teacher review load and generation cost overrun | Concept prioritisation; budget file and cost ledger; fallback-first | 4 | M-62 |
| R-25 | X-A1 | Memory aids confound the reverse-learning comparison | Fixed, identical memory support across A/B/C; balance check | 4 | M-67, TS-STUDY-10 |
| R-26 | X-A1 | Mnemonic benefits fade at long delays or help recognition more than production | 7- and 30-day production outcomes; claims only from delayed results | 6 | M-64, M-65 |
| R-27 | X-A1 | Raju drifts into general-assistant behaviour | Closed turn types; model fills only the sentence slot; student-only filter; fixed Hindi lines | 2/4 | M-56, TS-RAJU-* |
| R-21 | E | Reusing team code from the LMA repo | Credit, licence check, and team consent recorded in ADR-0001 | 1 | — |

## 17. Ethics and limitations — P-ETH (§9, p.15)

| ID | Kind | Source | Requirement | setu | LMA | Ph | Acceptance | Tests |
|---|---|---|---|---|---|---|---|---|
| P-ETH-01 | P | §9 | Untrusted text comes from 3 paths (learner input, uploaded writing, model replies); models only produce text | B(Didi) | P | 2 | Each path covered by red-team cases | TS-RED-01..30 |
| P-ETH-02 | P | §9 | Learner text reaching coach or friend goes as a delimited, length-capped data field, and output is filtered | B | NA | 4 | G learner text, T wrapped in a `<learner_text>` field, ≤300 chars | TS-RED-10 |
| P-ETH-03 | P | §9 | The friend may say odd things; the guarantee covers authority, not content | NA | NA | 4 | Documented; friend output still filtered | Doc |
| P-ETH-04 | P | §9 | Adults only; informed consent under the institute's ethics process | M | P(PDFs) | 1/6 | No session without a consent record | TS-PRIV-01 |
| P-ETH-05 | P | §9 | Pseudonymous ids; own server; no commercial API sees learner text | B | P | 1 | Runtime has no external model endpoint configured; an egress test | TS-PRIV-02..04 |
| P-ETH-06 | P | §9 | Learner writing only with institutional permission, from adults, anonymised before analysis | M | M | R/6 | Upload requires a consent id; PII scrub | TS-PRIV-05 |
| P-ETH-07 | P | §9, §11 | Classes 6–10 need parental consent, child assent and DPDP compliance | NA | NA | R | Classroom features off until the gate | FW-P19 |
| P-ETH-08 | P | §9 | Limitations stated (text-first, analyser pending, one pair, adults, small panel, short pilot, no fine-tuning) | NA | NA | 0 | In PRD non-goals and the report | Doc |
| P-ETH-09 | P | §9 | Telugu facts confirmed so far against Krishnamurti & Gwynn (polar suffix, two "we", verbless X-is-Y, ఇది for "she", negative verb, -కి, కోసం, -రు with మీరు, participle relatives, plain subject in the past); all still await native review | NA | P(book_examples) | 1 | Source citations stored per rule | TS-BANK-14 |
| P-ETH-10 | P | §9 | No rule yet observed in learner data | — | — | 1 | All imported rules: evidence ≤ proxy | TS-BANK-03 |

## 18. Timeline and origin — P-PLAN, P-ORIG (§1, §10, Fig. 3)

| ID | Kind | Source | Requirement | Ph | Acceptance |
|---|---|---|---|---|---|
| P-PLAN-01 | P | §10 | Four-week parallel plan as a reference (adapted for a solo builder; see the implementation plan) | 0 | Mapped in implementation-plan.md §2 |
| P-PLAN-02 | P | §10, Fig.3 | Gate before learners: test-suite targets met and consent signed | 5 | G1–G4 in metrics-and-gates.md |
| P-PLAN-03 | P | §10 | A part that misses the gate is reported as "built, not evaluated" and the study runs without it | 5 | Feature flag state + report |
| P-PLAN-04 | P | §10 | 5–8 week-one interviews with learners and teachers; record commitments | 6 | Interview log |
| P-PLAN-05 | P | §10 | Content deliverables: 15 + 10 rules × 10 items, mirror items, 150 shared words, 4 scenes, native audio for the top 100 items, teacher panel, held-out items | 1–6 | DQ-01 resolved; content counts dashboard |
| P-PLAN-06 | P | §10 | Learners start by day 17; delayed test by day 24 (course timeline; replaced by gate-driven dates here) | 6 | Pilot schedule |
| P-ORIG-01 | P | §1 | CETLS roundtable: AI adult-controlled; give hints and assess process, not hand out answers | 3 | Hints never contain answers; teacher override |
| P-ORIG-02 | P | §1 | TA review: classmate weaker than the learner; novelty in mechanisms; one component at a time with many tests; simulation first; leveler deferred | all | Matches the phase order |
| P-ORIG-03 | P | §2 | Compare Indilingo directly before the pilot | 6 | Comparison note |

## 19. Newer-copy additions — P8b (LMA paper, 30 Oct)

| ID | Kind | Requirement | setu | LMA | Ph | Acceptance | Tests |
|---|---|---|---|---|---|---|---|
| P8b-01 | P8b | Epistemic-state spec. Access: seen words and taught rules. Error structure: 1 planted error on an unknown rule, or none on taught rules. Change: unknown→taught only on a checked correct fix; taught→forgotten when recall < 0.5; unsure, wrong, bare "wrong" or a why-answer change nothing | P | V | 2 | Each clause has a test | TS-CLS-* |
| P8b-02 | P8b | "Why?" after every 3rd checked fix; no model call; the answer goes to the teacher queue and changes nothing | P(every rule) | V | 3 | G the 3rd fix, T a fixed why prompt; state unchanged | TS-EXCH-WHY |
| P8b-03 | P8b | Planner weights rules by the learner's error history | M | V | 2 | Weighted sampling, seeded | TS-PLAN-08 |
| P8b-04 | P8b | Step 0 script bridge: Letters page; 6 differences (short/long e/o, ళ, ఱ, ంం, pronounced final vowel); reading game | P(no ఱ) | V | 3 | All 6 differences are skills in L0 | TS-L0-* |
| P8b-05 | P8b | Devanagari reading aid on every Telugu sentence, fading after 3 correct per rule | P | V | 3 | P-OPT-02 | TS-UI-FADE |
| P8b-06 | P8b | Hindi-letter typing converted letter by letter; ए/ओ → ఎ/ఒ and final म → ం forgiven, with the forgiveness disclosed; explanations not converted | P | V | 2 | Disclosed in Hindi feedback | TS-NORM-02..04 |
| P8b-07 | P8b | Equal aids across conditions; Hindi-typed answers counted per learner | NA | B | 4 | P-EVAL-15 | TS-STUDY-03 |
| P8b-08 | P8b | Evidence base for the script bridge: Shintani 2013 (production → productive knowledge), Escudero 2008 / Cerni 2019 (written form helps), Hayes-Harb 2021 (misleading L1 letter habits), TwiLex 2024 (reading while listening is no better) | NA | NA | 0 | Cited in learning-methodology.md | Doc |
| P8b-09 | P8b | v0 parametric simulator: half-life model; retrieval ×(1.2 + 3(1−p)); restudy ×(1.1 + 1.5(1−p)); why ×1 by default; copy probability 0.1; 9 rules, 3 per condition; results A>B, A<C | NA | V | 4 | Re-implemented as one config of simulator v1; results reproduced with seeds | TS-SIM-REPRO |
| P8b-10 | P8b | Simulator faults fixed: matched feedback across conditions; recognition grows half-life ×1.2, not ×2 | NA | V | 4 | Regression tests | TS-SIM-03 |
| P8b-11 | P8b | Harder and unseen test items to avoid ceiling effects (Chrysalis); check pre-test is not near ceiling | NA | B | 4 | Held-out hard pool; pre-test ceiling check | TS-STUDY-09 |
| P8b-12 | P8b | Facilitator script, consent form, background questionnaire; one profile per learner; export after every session | NA | P(PDFs) | 4/6 | In-app consent and export | TS-PRIV-01 |
| P8b-13 | P8b | Scorecard finding: unsure 60% → 20%; 145-answer teacher label sheet; checker–teacher κ is the next number | NA | P | 2/6 | Labels collected; κ computed | M-16 |
| P8b-14 | P8b | Spoken vs textbook Telugu (వస్తున్నా / వస్తున్నాను); spoken forms accepted only after native approval | M | M | 2/6 | Variant with `register=spoken` and an approval record | TS-CHK-VAR |

## 20. Future work — FW (§11 pp. 16–18; prompt §15)

Every row has its own entry in [`../research/roadmap-future-work.md`](../research/roadmap-future-work.md) with spec, research question, risks, dependencies, gate and evaluation. None is a first-milestone commitment.

| ID | Title | Gate before work or exposure |
|---|---|---|
| FW-R01 | Larger controlled trial with several delayed tests | Pilot complete; preregistration; power analysis |
| FW-R02 | Learner-error collection at scale | Ethics approval; annotation protocol with κ |
| FW-R03 | Each direction separately; contrast model vs general GEC baseline | ≥ observed data in both directions |
| FW-R04 | Checker robustness (spelling, morphology, alternatives, regional, ambiguity, abstention) | Analyser evaluated on 50 sentences |
| FW-R05 | Forgetting vs remembering classmate; feedback types by band and direction | Stage A gates passed |
| FW-R06 | Feedback style (direct, L1 explanation, explicit contrast), matched, measured by transfer | Coach gates passed |
| FW-R07 | Adaptive error-profile diagnostic | Tracker beats BKT (M-23) |
| FW-R08 | Teacher error-to-lesson pipeline; teacher time saved | Upload privacy gate |
| FW-R09 | Replay the learner's own wrong forms through the classmate | Copy-rate gate (M-37) |
| FW-R10 | When the classmate should first appear; adaptive switch | X-CLS-START data |
| FW-R11 | Confidence and calibration | Confidence flag reviewed |
| FW-R12 | Validate simulated learners against pilot data; predict the next cohort | Pilot data |
| FW-R13 | Long-term retention (1–3 months) and real-world tasks | Pilot complete |
| FW-R14 | Four-dimension leveler; can-do descriptors; ReadMe++ for Hindi; Telugu learner scale | Teacher band labels |
| FW-R15 | External state vs machine unlearning vs fine-tuned learner models | M-01/M-02 baselines |
| FW-R16 | Fairness by script familiarity, schooling, exposure, region | Enough learners per subgroup |
| FW-R17 | Personalisation vs fixed sequence; transparent tracker vs richer tracing | Tracker evaluated |
| FW-P18 | Released dataset with licensing, privacy, access control; LTRC licence check | Licences confirmed |
| FW-P19 | Classroom deployment incl. classes 6–10 (parental consent, assent, DPDP) | Legal and ethics approval |
| FW-P20 | Per-sound pronunciation scoring (ళ, short ఎ/ఒ, word-final u); ASR tuned on Hindi-accented Telugu | M-25 passed; κ ≥ 0.6 sound check |
| FW-P21 | Activation steering for the friend's register and the classmate persona; never for correctness | Friend gates passed |
| FW-P22 | LoRA for spoken dialogue; DPO for coach hints on teacher-approved logs | Privacy review of logs |
| FW-P23 | Hindi head start (twins in varnamala order, new letters, Sanskrit-origin words, false friends) | **Pulled into Phase 3 (X-BEG)** |
| FW-P24 | Content factory from state textbooks; Hindi glosses; checks; teacher wait-list | Permission from the textbook publisher |
| FW-P25 | Shared weak-student benchmark | Stage A suite stable |
| FW-P26 | Human tandem pairs (Telugu↔Hindi learners) | TE→HI direction gated |
| FW-P27 | Hyderabadi Telugu and Dakhini Hindi varieties, code-mixing | Local speakers' variant lists |
| FW-P28 | Low-cost deployment (Gemma 3 4B, on-device) | M-01/M-02 at 4B |
| FW-P29 | More pairs (Hindi↔Tamil, Hindi↔Kannada) | Pipeline stable for one pair |
| FW-R18 | (A1) Long-term mnemonic retention (90 days); approved-library aids vs runtime-generated grounded aids | Study M complete; G-MEM-RT |
| FW-R19 | (A1) Which technique works for which unit type and learner profile (adaptive-policy learning) | n ≥ 30 exposures per aid |
| FW-P30 | (A1) Learner-authored mnemonics (the learner writes their own story or keyword; it passes the grounding validator; private) | G-MEM-GROUND; privacy review |
| FW-P31 | (A1) Full memory-palace scenes for L3/L5 phrase sets | Study M shows a benefit for imagery |

## 21. Prompt extensions — X (master prompt)

| ID | Source | Requirement | setu | LMA | Ph | Acceptance (short G/W/T) | Tests |
|---|---|---|---|---|---|---|---|
| X-RULES-01 | §0.1 | Spec first; stop for approval | — | — | 0 | This package; no app code changed | git diff |
| X-RULES-02 | §0.2 | Inventory before replacing; never delete working features without a reason and a migration path | — | — | 0/1 | Migration table in the implementation plan §4 | Doc |
| X-RULES-03 | §0.3 | Traceability matrix covering everything | — | — | 0 | This file; coverage check | Coverage script |
| X-RULES-04 | §0.4 | Statements labelled P / X / E | — | — | 0 | Every spec tags its statements | grep |
| X-RULES-05 | §0.5 | No invented results; failed conditions reported | P | P | all | Report template has a "failed or not run" section | Doc |
| X-RULES-06 | §0.6 | No model has authority over learning records | P | V | 2 | P-ARCH-01, E-01 | TS-AUTH-* |
| X-RULES-07 | §0.7 | Fail closed: unvalidated content is never shown as correct | B | P | 2 | Every display path has a validator plus fallback | TS-DISP-* |
| X-NOENG | §0.8 | No English or Roman script in the learner product; Telugu only in its own script; romanisation optional, fading, approved | B | B | 1 | M-54 = 0; lint in CI | TS-L10N-01..05 |
| X-PRIMARY | §0.9 | Default journey Hindi speaker → Telugu; TE→HI preserved (bank, contracts, tests, mirror) | V | P | 1 | Direction is a stored field; TE→HI tests exist | TS-DIR-* |
| X-CALM | §0.10 | No meaningless streaks, points, badges, confetti or engagement loops | B | P | 1 | No such components; UI review checklist | TS-UI-CALM |
| X-OBJ-01 | §1 | The research question stays testable and can come out null or harmful | — | — | 4/6 | Analysis plan reports null and harm outcomes | Doc |
| X-LAD-L0 | §3.1 | L0 script orientation: Devanagari–Telugu relation explained in Hindi; vowels and consonants; twins; new letters ఎ ఒ ళ flagged; varnamala order | P | P | 3 | Skills for every letter, incl. ఙ ఞ ఱ ః | TS-L0-* |
| X-LAD-L1 | §3.1 | L1 akshara: recognition and recall, vowel signs, gunintalu, syllables, conjuncts, sound–letter, visual discrimination, typing, decoding | P | M | 3 | Skill nodes per family; cue-free typing | TS-L1-* |
| X-LAD-L2 | §3.1 | L2 words: read, hear, understand, recall, produce; first 1,000–2,000 by frequency; cognates first, false friends flagged | P(28) | M | 3 | Lexeme ladder with frequency rank | TS-L2-* |
| X-LAD-L3 | §3.1 | L3 chunks: expressions, phrases, question forms, postpositions and suffixes, routines, substitution practice | M | M | 3 | Chunk skills; substitution tasks | TS-L3-* |
| X-LAD-L4 | §3.1 | L4 sentences and contrasts: patterns, morphology, agreement, negation, questions, copula, pronouns, possession, "we", clauses | P | P | 3 | Maps to the P-BANK families | TS-L4-* |
| X-LAD-L5 | §3.1 | L5 functional communication: scenes, dialogue, connected sentences, writing, listening, speaking | M | M | 3/4 | Scene tasks with production | TS-L5-* |
| X-LAD-VAL | §3.1 | The sequence is a proposal; validate with teachers and learner data; keep the 4-dimension difficulty inside every level | — | — | 6/R | Validation study in the roadmap | FW-R14 |
| X-PERS-01 | §3.2 | Individual skill graph and learner state per student | M | M | 2 | `learner_skill_state` per learner | TS-LAD-01 |
| X-PERS-02 | §3.2 | No mastery inferred from completion, time, clicks or self-reported confidence | B | P | 2 | Mastery updates only from verdicts | TS-LAD-02 |
| X-PERS-03 | §3.2 | Diagnostic lets a learner test out; beginners start at the beginning | M | M | 3 | Placement flow | TS-PLACE-* |
| X-PERS-04 | §3.2 | Track recognition, recall, reading, listening, spelling/typing, explanation and production separately | M | M | 2 | A modality column on evidence | TS-LAD-03 |
| X-PERS-05 | §3.2 | Each skill has prerequisites, evidence, mastery with uncertainty, last practice, due date, common errors, permitted next skills | M | M | 2 | Schema fields | TS-LAD-04 |
| X-PERS-06 | §3.2 | Unlock only after criteria are met on more than one item and context, incl. cue-free recall and production | B | B | 2 | Unlock rule tests | TS-LAD-05..08 |
| X-PERS-07 | §3.2 | Revisit weak prerequisites when downstream performance shows a gap | M | M | 3 | Prerequisite blame rule | TS-LAD-09 |
| X-PERS-08 | §3.2 | Visible Hindi ladder: what you can do, what remains, why next; no technical scores | B | M | 3 | Ladder page | TS-UI-LAD |
| X-PERS-09 | §3.2 | Progression and retention measured by skill, not one overall % | B | M | 3 | M-50 | TS-LAD-10 |
| X-LEV-01 | §3.3 | Leveler v0 implemented as a reproducible baseline, with per-item band and reason | M | M | 2 | P-DIFF-01 | TS-LEV-* |
| X-LEV-02 | §3.3 | Max, weighted and fitted leveler variants compared | M | M | R | Comparison report | FW-R14 |
| X-LEV-03 | §3.3 | Validate against teacher ratings and learner comprehension; κ ≥ 0.6; not claimed until it passes | M | M | R | M-51 | FW-R14 |
| X-LEV-04 | §3.3 | Baseline kept so the richer leveler's benefit can be tested | — | — | R | Versioned leveler ids | TS-LEV-06 |
| X-LEV-05 | §3.3 | L0–L5 can-do descriptors defined and validated; CEFR alignment is a separate study | M | M | 3/R | Descriptors in learning-ladder.md, marked unvalidated | Doc |
| X-BEG-01 | §3.4 | Letter twins as a head start, while teaching genuinely new forms and sounds | P | P | 3 | X-LAD-L0 | TS-L0-* |
| X-BEG-02 | §3.4 | Sanskrit-origin cognates as scaffolds; false friends flagged (पुस्तक/పుస్తకం, अवसर/అవసరం) | P | M | 3 | Lexeme flags | TS-CONT-01 |
| X-BEG-03 | §3.4 | Small cap on new items per session | P(3 lessons/day) | M | 3 | Config `new_item_cap` = 5 | TS-SESS-05 |
| X-BEG-04 | §3.4 | 4 initial scenes (auto stand, mess, landlord, everyday); expand only after teacher review | P(5 scenes, unreviewed) | M | 3 | Scenes have review status | TS-CONT-04 |
| X-BEG-05 | §3.4 | Native audio for the top 100 items, with consent and rights | M | M | 5 | Audio assets with a consent id | TS-AUD-01 |
| X-BEG-06 | §3.4 | Script fading; no Roman-English | P | P | 3 | P-OPT-02 | TS-UI-FADE |
| X-SESS-01 | §4.1 | Session mix configurable and recorded; learner stays tutor, AI stays tutee | P | P | 3 | Config snapshot stored on the session | TS-SESS-01 |
| X-SESS-02 | §4.1 | Modes never combined within an experimental condition | NA | P | 4 | P-EVAL-16 | TS-STUDY-06 |
| X-EXCH-01 | §4.2 | ≤3 drafts generated one at a time, each validated, then bank fallback | P | V | 4 | P-ARCH-03 | TS-AGT-* |
| X-EXCH-02 | §4.2 | No-error turns measure false alarms and over-correction | P | P | 3 | M-36 | TS-EXCH-NE |
| X-EXCH-03 | §4.2 | Optional confidence rating, experimental only | M | M | 4 | Flag off by default | TS-EXP-CONF |
| X-EXCH-04 | §4.2 | First hint never reveals the corrected form; answer after the 2nd miss | B | B | 3 | M-18 | TS-COACH-01..06 |
| X-EXCH-05 | §4.2 | Every decision and version logged | P | P | 1 | E-02 | TS-LOG-* |
| X-CLS-START | §5 | The classmate starts teaching after a configurable minimum number of verified rules; thresholds tested | P(module end) | P(teach_needed) | 3/4 | Config `classmate_start_min_rules`; ablation | TS-CLS-15, FW-R10 |
| X-CLS-NOTRUST | §5 | No learning from "that is wrong", partial, wrong, LLM statements, injection or unsure | P | V | 2 | P8b-01 | TS-CLS-08..12 |
| X-ARCH-01 | §6.1 | Native friend checks Hindi share and out-of-band words; falls back to approved scene content | B | M | 4 | M-21, M-22 | TS-FRND-* |
| X-ARCH-02 | §6.2 | Every tool contract documents name, purpose, when to use and not use, typed args, limits, exact errors, return schema, permission, invalid examples | P | P | 0/2 | api-and-tool-contracts.md | TS-TOOL-* |
| X-ARCH-03 | §6.3 | Red-team target: zero attacks change a verdict, mastery, memory or classmate state | P | P | 2/4 | M-14 | TS-RED-* |
| X-ARCH-04 | §6.3 | Record prompt, model and tool versions and rejection reasons without unnecessary personal data | P | P | 1 | Logs exclude learner names | TS-PRIV-06 |
| X-BANK-01 | §7.1 | Rule record: one-error span; no-error equivalent; L1 and Hindi explanations | P | P | 1 | Schema | TS-BANK-02 |
| X-BANK-02 | §7.1 | Vocabulary prerequisites, allowed target words, analyser and pattern requirements | M | P | 1 | Schema | TS-BANK-02 |
| X-BANK-03 | §7.1 | Concept key for explanation scoring | P | M | 1 | Concept key per rule (Devanagari; no Latin) | TS-WHY-* |
| X-BANK-04 | §7.1 | Speaker approval, regional and register notes, licence and provenance | M | M | 1 | Schema | TS-BANK-02 |
| X-BANK-05 | §7.1 | Opportunity and observed-error counts, reported as rates | M | M | 4 | P-BANK-08 | TS-TCH-AN-01 |
| X-BANK-06 | §7.1 | Lifecycle draft → review → verified/approved → active → deprecated/rejected; immutable history | P | P | 1 | State machine | TS-BANK-05 |
| X-BANK-07 | §7.1 | Only `validity=verified` **and** teacher-approved rules may be planted | M | M | 2 | P-BANK-05 | TS-PLAN-07 |
| X-DSR | §7.4 | Data-source register with licences for every listed source, incl. Sarvam-M as a comparison only | M | M | 0/1 | data-source-register.md | TS-DSR-* |
| X-SPEECH-01 | §8.3 | Text-first; basic speech input and native voices as an extension | M | P | 5 | Flags | TS-SPCH-* |
| X-SPEECH-02 | §8.3 | Evaluate IndicConformer and alternatives on Hindi-accented Telugu; WER vs Whisper | M | M | 5 | M-25 | TS-SPCH-WER |
| X-SPEECH-03 | §8.3 | Native recordings and/or Indic Parler-TTS; speaker review; never assume TTS is native | M | M | 5 | Review record per voice | TS-AUD-02 |
| X-SPEECH-04 | §8.3 | First version: word-level recognition only; per-sound scoring is a separate extension | NA | NA | 5/R | FW-P20 | — |
| X-CHK-01 | §8.1 | Romanised input transliterated but never treated as automatically correct | M | P | 2 | G romanised input, T normalised and then checked normally | TS-NORM-06 |
| X-CHK-02 | §8.1 | Controlled variant list plus teacher queue for spelling, morphology, regional forms and ambiguity | P | P | 2/4 | Variant table with approval | TS-CHK-VAR |
| X-COACH-01 | §8.2 | Begin with fixed teacher-approved hints; then the LLM may choose or draft within validation | P | P | 3/4 | Phase 3 fixed; Phase 4 LLM behind a flag | TS-COACH-* |
| X-MEM-01 | §9 | FSRS for words and chunks; tracker for rules and skills with uncertainty and next review; BKT comparison | P | P | 2 | P-ARCH-12 | TS-SCHED-* |
| X-MEM-02 | §9 | Memory updated only from checker verdicts or teacher resolutions | P | V | 2 | E-01 | TS-AUTH-* |
| X-MEM-03 | §9 | OKF Markdown + YAML export as a view; Postgres is the source of truth | M | M | 2 | Export round-trip; read-only | TS-OKF-* |
| X-MEM-04 | §9 | Log rule and item versions, prompt and model versions, tool calls, verdicts, attempts, confidence, latency, model calls, rejection and fallback | P | P | 1 | E-02 | TS-LOG-* |
| X-TCH-01 | §10 | Teacher console with Hindi-facing UI | B(English) | B | 4 | Teacher strings from the catalog | TS-L10N-03 |
| X-TCH-02 | §10 | Rule review, approve/reject/uncertain, promote, history, source and licence | M | M | 4 | teacher-console.md F1 | TS-TCH-REV |
| X-TCH-03 | §10 | Two raters per language, κ reported, third reviewer for disputes | M | M | 4 | F2 | TS-TCH-KAPPA |
| X-TCH-04 | §10 | Settle unsure corrections with an audit trail | P(display) | P | 4 | F3 | TS-TQ-* |
| X-TCH-05 | §10 | Review variants, regional forms, naturalness, explanation quality | M | M | 4 | F4 | TS-TCH-VAR |
| X-TCH-06 | §10 | Anonymised writing upload → proposals only | M | M | R/4 | F5 | TS-TCH-UP |
| X-TCH-07 | §10 | Analytics per opportunity: progress, false alarms, copy rate, misconceptions, unsure cases | M | P | 4 | F6 | TS-TCH-AN-* |
| X-TCH-08 | §10 | Teacher override of automatic feedback (future classroom use) | M | M | 4 | F7, audited | TS-TCH-OVR |
| X-TCH-09 | §10 | Export only approved, consented, licensed data | M | M | 4 | F8 | TS-TCH-EXP |
| X-TCH-10 | §10 | Observations vs estimates vs missing data vs unreviewed model proposals kept distinct | M | M | 4 | Visual encoding plus labels | TS-TCH-AN-02 |
| X-SIM-01 | §11 A2 | Simulator agents: explicit memory; limited to their own words and rules; configurable initial skill, learning rate, error distribution, confidence, forgetting curve, hint response | NA | P | 4 | Config schema | TS-SIM-01 |
| X-SIM-02 | §11 A2 | Acquire only after a checker-correct verdict; sometimes wrong or partial | NA | V | 4 | M-32 | TS-SIM-02 |
| X-SIM-03 | §11 A2 | Cue-free recall at days 0, 1, 2, 7; reproducible seeds, configs and event logs | NA | P | 4 | M-31 | TS-SIM-REPRO |
| X-SIM-04 | §11 A2 | 20 per condition × A/B/C = 60 baseline runs; ablations (forget vs remember, mirror, predict, hint type, start threshold) | NA | P | 4 | Run manifest | TS-SIM-04 |
| X-SIM-05 | §11 A2 | Simulator results never reported as human effects; calibrated against the pilot later | NA | V | 4/R | Report language check | Doc |
| X-STAGEB-01 | §11 B | Measure time on task, effort, usability, would use again, confidence calibration, false alarms, copy rate, returning for a second session | NA | P | 6 | Fields captured | TS-LOG-03 |
| X-GATE-01 | §12 | Metrics in an automated dashboard plus a reproducible report; thresholds fixed in advance | NA | P | 4 | Scorecard command | TS-SCORE-01 |
| X-GATE-02 | §12 | Never relax targets quietly; a failed gate is reported; revised thresholds are preregistered for later; post-hoc changes marked exploratory | — | — | all | Threshold file is versioned and frozen | Doc |
| X-PRIV-01 | §9 | Pseudonymous ids; minimal personal data; no identifiable learner writing to any commercial API | B | P | 1 | P-ETH-05 | TS-PRIV-* |
| X-DELIV | §16 | Delivery approach: the paper's four-week plan is a reference only; parallelise only behind shared schemas and mocks; check capacity instead of assuming 10 h/day; no participant uses an unvalidated module; a part that misses its gate is "built, not evaluated" | — | — | 0+ | implementation-plan.md §1–2 (solo capacity, decision D4) | Doc |
| X-DOD | §17 | Definition-of-done checklist applied to every feature | — | — | all | PR template | Doc |
| X-AFTER | §18 | Slice protocol (spec IDs, files, dependencies, risks, tests before each slice) and milestone report format | — | — | 1+ | implementation-plan.md §6 | Doc |

## 22. Engineering recommendations — E

| ID | Recommendation | Why | Ph | Tests |
|---|---|---|---|---|
| E-01 | Separate Postgres roles. `setu_read` for tools, agents and the web layer; `setu_writer` used only by OutcomeWriter (and TeacherResolution), with grants on learning tables | Enforces "only the checker writes" below the code level | 1 | TS-AUTH-04, TS-DB-02 |
| E-02 | Append-only `event_ledger` with hash chaining; a trigger blocks UPDATE and DELETE | Auditable history; detects tampering | 1 | TS-DB-03 |
| E-03 | Hindi string catalog plus a CI lint failing on `[A-Za-z]` in learner templates and catalog values | Makes X-NOENG testable | 1 | TS-L10N-01 |
| E-04 | py-fsrs (pinned) for words and chunks | Standard, tested implementation | 2 | TS-SCHED-01 |
| E-05 | Mastery tracker: Beta-Bernoulli posterior with time decay (half-life regression), giving mean and credible interval; BKT and SM-2 baselines | Transparent, gives uncertainty | 2 | TS-SCHED-05..09 |
| E-06 | Content authored as versioned YAML under `content/`, validated by a CLI, imported into immutable versions | Reviewable diffs; reproducible | 1 | TS-BANK-* |
| E-07 | Golden-file tests replace the JS parity port; retire the hosted JS app | One implementation | 1 | — |
| E-08 | Pseudonymous auth: invite code + passphrase (argon2); roles learner, teacher, researcher, admin; dev controls only for researchers | No PII; protects learners | 1 | TS-AUTHN-* |
| E-09 | Docker Compose: app, Postgres 16, optional Ollama; pinned Python ≥ 3.11 | Reproducible environment | 1 | CI |
| E-10 | Playwright E2E flows, asserting Hindi-only text | Catches UI regressions | 3 | TS-E2E-* |
| E-11 | Feature flags tied to gate status; `built_not_evaluated` modules are hidden from learners | Enforces gates | 1 | TS-FLAG-01 |
| E-12 | Seeded RNG per session; config snapshot per session | Reproducibility | 2 | TS-PLAN-01 |
| E-13 | Idempotency keys on answer submission; server owns the pending turn (no re-roll) | Fixes the LMA re-roll and duplicates | 2 | TS-API-IDEMP |
| E-14 | No turn type or answer in any learner-facing API response before the learner answers | Fixes the `turn_type` leak | 2 | TS-API-LEAK |
| E-15 | Accessibility: WCAG 2.2 AA, self-hosted Noto Sans Telugu and Devanagari, ≥ 18 px base, keyboard-only flow, on-screen Telugu keyboard and Devanagari typing | Learners mostly can't type Telugu | 3 | TS-A11Y-* |
| E-16 | Versioned tokenizer for TMR (NFC, punctuation split, clitic policy) | Comparable TMR over time | 2 | TS-TMR-* |
| E-18 | (A1) A separate offline content-pipeline environment with its own egress allow-list; the runtime app has no generation clients | Isolates external image services from learner data | 1 | TS-PRIV-07 |
| E-19 | (A1) Budget file plus a generation cost ledger; the CLI refuses past the ceiling | Cost control | 4 | TS-MEM-COST-01..03 |
| E-20 | (A1) Local multi-script OCR (Devanagari, Telugu, Latin) as an image pre-check | "No embedded text" becomes testable | 4 | TS-IMG-01 |
| E-17 | Held-out manifest frozen once (hash list committed); CI fails if dev code reads held-out labels | Fixes LMA split rewrite | 2 | TS-SUITE-SPLIT |

## 23. Amendment A1 — Memory Assistant (user request, 30 Oct 2026)

Spec: [`memory-assistant.md`](memory-assistant.md). Study: [`../research/memory-experiment-protocol.md`](../research/memory-experiment-protocol.md). ADR-0005.

| ID | Source | Requirement | setu | LMA | Ph | Acceptance (short G/W/T) | Tests |
|---|---|---|---|---|---|---|---|
| X-MEM-AID-01 | A1 R1 | Visual mnemonics, Hindi stories, sound associations, chunking, memory palace, other evidence-informed techniques | P(tricks, unreviewed) | M | 3/4 | Technique catalog in the policy table | TS-MEM-SEL-01 |
| X-MEM-AID-02 | A1 R2 | Technique chosen by unit type (letters, sounds, akshara, vocabulary, false friends, grammar, phrases) | M | M | 3 | Each unit type → eligible techniques | TS-MEM-SEL-02..04 |
| X-MEM-AID-03 | A1 R3 | AI teacher recommends a technique from skill history and difficulty (chooses only among deterministic candidates) | M | M | 4 | Invalid choice → top candidate | TS-MEM-SEL-05..08 |
| X-MEM-AID-04 | A1 R4 | Mnemonics grounded in verified content; no invented Telugu facts | B | M | 2/4 | Grounding validator + teacher review; M-57 = 0 | TS-MEM-GRD-* |
| X-MEM-AID-05 | A1 R5 | Educational images without embedded text; glyphs and Hindi rendered separately by the app | B(SVG, unverified) | M | 4 | OCR check; overlay as DOM text; M-58 = 0 | TS-IMG-* |
| X-MEM-AID-06 | A1 R6 | Approved visual asset library (concept id, version, prompt, review status, licence, alt text, usage history) | P(aids.json) | M | 1/4 | Schema; immutable versions | TS-MEM-LIB-* |
| X-MEM-AID-07 | A1 R7 | Cache and reuse; non-generative fallback | P | M | 3 | M-60 = 100%; no runtime generation calls | TS-MEM-LIB-01..03 |
| X-MEM-AID-08 | A1 R8 | No identifiable learner info to external image services | B | NA | 1 | Allow-listed concept-only payload; offline only | TS-IMG-03, TS-PRIV-07 |
| X-MEM-AID-09 | A1 R9 | Hindi descriptions, audio alternatives, readable contrast, no colour-only meaning | M | M | 3/4 | M-59 = 100%; axe checks | TS-MEM-A11Y-* |
| X-MEM-AID-10 | A1 R10 | Measure whether each aid improves independent delayed recall; viewing is not evidence | M | M | 4 | Micro-randomised effect estimates (M-61) | TS-MEM-MEAS-* |
| X-MEM-AID-11 | A1 R11 | Gradually fade visual, audio and text cues; measure recall at cue level 0 | P(reading aid only) | P | 3 | Cue ladder 3→0; tests at 0 (M-68) | TS-MEM-FADE-* |
| X-MEM-AID-12 | A1 R12 | Store presented, selected, used and later recalled; never award mastery for viewing | M | M | 2/3 | `aid_event`; mastery only from cue-free attempts | TS-MEM-MEAS-01..03 |
| X-MEM-AID-13 | A1 R13 | FSRS for discrete items; aid scheduling integrated with learner state | P | P | 2 | Aid-visible attempts capped at Hard and excluded from mastery | TS-SCHED-MEM-* |
| X-MEM-AID-14 | A1 R14 | No English in generated or static learner-facing assets | B | B | 1/4 | Catalog lint + OCR on images + validator `LATIN` | TS-L10N-*, TS-IMG-01 |
| X-MEM-AID-15 | A1 R15 | Subsystem added to architecture, PRD, journeys, data model, API, content pipeline, matrix, implementation plan, test plan, research protocol, roadmap | — | — | 0 | This amendment | Coverage check |
| X-MEM-EXP-01 | A1 EXP | Separate human experiment M-A (normal + retrieval) / M-B (verbal) / M-C (visual + native audio) / M-D (adaptive) | NA | NA | 6 | Williams 4×4 design; preregistered | TS-MSTUDY-01 |
| X-MEM-EXP-02 | A1 EXP | Comparable concepts, time and practice opportunities | NA | NA | 4 | Balanced sets; equal opportunities and time box | TS-MSTUDY-02..03 |
| X-MEM-EXP-03 | A1 EXP | Immediate, 1-, 7-, 30-day retention; unaided production; transfer; time to mastery; incorrect associations | NA | NA | 6 | M-64..M-66, M-63 | TS-MSTUDY-04..08 |
| X-MEM-EXP-04 | A1 EXP | Memory support identical across the reverse-learning A/B/C conditions | NA | B | 4 | Fixed-mode policy; M-67 balanced | TS-STUDY-10 |
| X-MEM-EXP-05 | A1 EXP | Simulated learners test logic, scheduling and reproducibility only; never reported as human evidence | NA | P | 4 | Report language check | TS-SIM-MEM-01..03 |
| X-MEM-EXP-06 | A1 EXP | Acceptance tests, gates, teacher-review requirements, cost controls and failure behaviour defined before implementation | — | — | 0 | memory-assistant.md §2, §4–6 | Doc |

## 24. Amendment A1 — Raju is a weaker student only (user request, 30 Oct 2026)

Spec: [`classmate-output-contract.md`](classmate-output-contract.md). ADR-0006.

| ID | Requirement | setu | LMA | Ph | Acceptance | Tests |
|---|---|---|---|---|---|---|
| X-RAJU-01 | Closed set of turn types (attempt, retry_attempt, thanks_learned, still_confused, ask_why, confirm_correct); no free chat | B(model-written chatter) | P | 2/3 | No other turn type can be emitted | TS-RAJU-01..03 |
| X-RAJU-02 | The model fills only the L2 sentence slot; all Hindi lines come from fixed catalog templates | B | P | 2/4 | Rendered Hindi equals a catalog entry exactly | TS-RAJU-04..05 |
| X-RAJU-03 | Student-only filter: assistant register, teacher register, formatting, gloss, answer leak, competence ceiling, instruction echo | P | P | 2 | Each reason code tested; M-56 = 0 | TS-RAJU-06..15 |
| X-RAJU-04 | Prompt frames a constrained form-fill, not an assistant; no learner text; decoding limits | B | P | 4 | Prompt-content tests | TS-RAJU-16..17 |
| X-RAJU-05 | Raju never knows more than the learner (state-limited competence) | P | V | 2 | P-CLS-05/10 | TS-CLS-* |
| X-RAJU-06 | Calm adult-classmate persona; the legacy child persona and celebrations retired | B | P | 1 | Catalog review | TS-UI-CALM |

## 25. Implementation status (updated per slice)

Lifecycle: `built` = code exists; `tested` = acceptance tests pass against real Postgres where relevant;
`evaluated` = measured against its metric or gate (none yet). Rows not listed are still `missing`.

| Slice | Row IDs | Lifecycle | Evidence |
|---|---|---|---|
| 1.1 | E-09, X-RULES-02, P-EVAL-02 (CI defined, not yet run) | built, tested | `tests/unit/test_scaffold.py`; legacy suite kept |
| 1.2 | P-ARCH-11 (schema), E-01, E-02, P-BANK-03, P-BANK-04, P-BANK-06, X-BANK-06, TS-DB-01..03, TS-AUTH-04 | built, tested | `tests/db/test_constraints.py`, `test_grants.py`, `test_ledger_and_immutability.py`, `test_real_logins_and_concurrency.py` |
| 1.3 | P-SESS-11, X-RULES-06, X-CLS-NOTRUST, P8b-01 (state changes), P-ARCH-10 (queue, no update on unsure), M-06, M-17, TS-AUTH-01..03, 05 | built, tested | `tests/unit/test_authority.py`, `tests/db/test_outcome_writer.py` |
| 1.4 | P-BANK-01, 02, 05 (only verified + approved content is learner-visible), 07 (versions per record), 09, 15, P-STAT-02, X-BANK-01..07, X-DSR, E-06, P-DATA-01/05/06 (register rows), X-NOENG (database backstop on learner-facing columns), DQ-04..07, DQ-11, DQ-13, DQ-15 | built, tested | `tests/unit/test_patterns.py`, `tests/unit/test_content.py`, `tests/db/test_content_import.py`; `python -m setu.content validate|import` run against the dev database |

| 1.5 | E-08, P-ETH-04, P-ETH-05 (pseudonymous ids; no runtime model client yet to configure), X-PRIV-01, TS-AUTHN-*, TS-PRIV-01, TS-PRIV-06 (logs and login records hold no names or IPs), data-model §5 withdrawal | built, tested | `tests/unit/test_credentials.py`, `tests/db/test_auth_and_consent.py`; dev database upgraded to 0004 |

| 1.6 | X-NOENG, E-03, M-54 (0 Latin in visible text: lint + rendered crawl), TS-L10N-01..05, TS-UI-CALM (no emoji), E-15 (self-hosted fonts, `lang`, 18px base, focus styles) | built, tested | `tests/unit/test_l10n.py`, `tests/db/test_ui_pages.py`; `python -m scripts.lint_hindi` in CI; real server smoke test |

| ADR-0007 | P-ETH-04, P8b-12: consent collected in person, recorded automatically at registration; withdrawal recorded by a researcher | built, tested | `tests/db/test_auth_and_consent.py` |

| 2.1 | P-ARCH-05, P-SESS-09 (normalisation part), P8b-06, X-CHK-01, P-DATA-07 (adapter interface only), TS-NORM-01..10 | built, tested | `tests/unit/test_normalise.py` (38 tests) |

Still open from those rows: P-DATA-07 (the IndicXlit model is not wired in; only the adapter interface), P-BANK-08 (rates per opportunity, teacher analytics), X-BANK-05 (opportunity counts are stored, no analytics yet), DQ-08 (rule titles that reveal answers are imported as drafts and not yet detected automatically), DQ-01 (only 25 rules / 49 items exist vs 250 planned), M-54 for pages not built yet (each new page joins the crawl), E-15 full WCAG audit (axe checks arrive with the learner slices), and the researcher console's other controls (time travel and study setup, phase 4).

