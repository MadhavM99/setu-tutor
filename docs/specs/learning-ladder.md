# Learning ladder L0–L5, personalisation, placement and leveler

Tags: **[P]** paper · **[X]** prompt extension · **[E]** engineering recommendation.

**Status.** The six-band ladder is a **proposed instructional sequence [X-LAD-VAL]**. The paper itself uses item bands L0–L2 (§6.1) and leaves L0–L5 can-do descriptors to future work (§11). Nothing here is claimed as validated until teacher agreement reaches κ ≥ 0.6 and learner data support it.

**Two different "bands".** Item difficulty bands are produced by the leveler from the four dimensions (§6). Learner ladder bands L0–L5 group skills. The planner uses both:
- items at the learner's band b or b+1 [P-ARCH-02];
- skills that are unlocked in the learner's graph.

---

## 1. Skill graph

A **skill** = (band, family, target, modality). For example, `L0.letter.ళ.recognition` or `L4.rule.HI-TE-001.production`. Skills have prerequisites (`skill_prereq`). Tracking is per learner. [X-PERS-01, X-PERS-04]

**Modalities [X-PERS-04]:**

| Code | Modality | Example task (cue-free unless noted) |
|---|---|---|
| REC | recognition | see Telugu → type the Hindi letter or meaning |
| RCL | recall | see/hear Hindi → type Telugu (keyboard or Devanagari conversion) |
| RD | reading | read a Telugu word or sentence aloud-silently → answer a meaning question typed in Hindi |
| LS | listening | hear Telugu → type the Hindi meaning or the Telugu word (flag: audio available) |
| SP | spelling/typing | type a dictated word in Telugu script |
| EX | explanation | explain in Hindi why (scored on the concept key) |
| PR | production | own Telugu word, phrase or sentence for a Hindi goal |

**Bands and skill families (Hindi→Telugu primary path):**

| Band | Families (first-release content) | Notes |
|---|---|---|
| **L0 — script orientation** | Devanagari↔Telugu order, explained in Hindi; vowels అ–ఔ; consonants క–ఱ, in varnamala order; letter twins; **new letters and sounds flagged:** short ఎ / ఒ, ళ, ఱ, ంం and final -ం, the pronounced final vowel; ఙ ఞ ః (missing today); confusable shapes (e.g. ఎ/ఏ, ఒ/ఓ, బ/ద) | Letter twins come from Unicode +0x300 (setu `text.py`, LMA `script.py`), pending native review [P8b-04, X-BEG-01] |
| **L1 — akshara** | Vowel signs (incl. ై ౌ, missing today); gunintalu tables; virama ్; common conjuncts / ottulu; syllable decoding; sound–letter mapping; visual discrimination; Telugu typing | "Knowing Devanagari ≠ knowing Telugu" [X-LAD-L1] |
| **L2 — words** | Top 1,000–2,000 by IndicCorp v2 frequency, filtered by textbook topic order (Tenepalukulu/Vennela, order only); numbers; greetings; question words; **cognates first** (पुस्तक/పుస్తకం); **false friends flagged** (अवसर/అవసరం …); ~150 Kanojia shared words | FSRS per lexeme × modality [X-LAD-L2, P-BANK-10] |
| **L3 — chunks** | Routine chunks per scene (auto stand: ఎంత? / చార్మినార్ వెళ్తారా?); postpositions and suffixes (-లో, -కి, -తో, కోసం); question forms; substitution frames | FSRS for chunks; substitution tasks [X-LAD-L3] |
| **L4 — sentences and contrasts** | The 13 Table 6 contrast families as rule skills (polar questions, copula, possession, negation, "we", gender, respect, she/it, relative clauses, ने, adverbial clauses, new sounds) plus high-frequency patterns | Mastery tracker per learner×rule; the classmate operates here [X-LAD-L4] |
| **L5 — functional communication** | Scenes: auto stand, mess, landlord, everyday; short dialogues; connected sentences; independent writing; listening; (speaking, when gated) | Native friend; own sentences [X-LAD-L5] |

Every item in every band also carries the four-dimension difficulty (script, TMR, word forms, structure). [X-LAD-VAL]

## 2. Per-skill record [X-PERS-05]

`learner_skill_state` holds:
- `mastery_mean`, `mastery_lo`, `mastery_hi` (credible interval);
- `evidence_n`, `distinct_items`, `distinct_task_types`, `distinct_days`, `cuefree_successes`, `production_successes`;
- `last_practised`, `due_at`;
- `common_errors` (top error tags with counts per opportunity);
- `status` ∈ {locked, available, learning, mastered, due, relearning, placed};
- `source` ∈ {observed, placed}.

**Never updated by:** time spent, clicks, lessons opened, self-rated confidence, model statements. [X-PERS-02]

## 3. Feature: mastery and unlock (F-LAD)

- **Purpose:** decide what a learner has demonstrably learned and what opens next.
- **Learner outcome:** progress means durable, cue-free ability on more than one item, including production.
- **User flow:** none directly. Results surface on the ladder view and in the session composer.
- **Data inputs:** checker verdicts (OutcomeWriter events), teacher resolutions, the skill graph.
- **Data writes:** `learner_skill_state` (by OutcomeWriter only).
- **Model involvement:** none.
- **Failure behaviour:** unsure verdicts are ignored. If evidence is missing, the skill stays `learning`. The tracker never extrapolates mastery from unrelated skills.
- **Accessibility/localisation:** none (backend).
- **Rule [E, defaults to calibrate on pilot data]:** a skill becomes `mastered` when all of these hold:
  1. ≥ 3 correct checked attempts;
  2. ≥ 2 distinct items;
  3. ≥ 2 task types;
  4. ≥ 1 cue-free recall or production success (for L2+ at least 1 **production**);
  5. evidence on ≥ 2 distinct days;
  6. `mastery_lo` ≥ 0.6 (Beta posterior with decay, E-05).

  Placement counts as 1 day. Attempts after a revealed answer do not count.
- **Unlock:** a skill becomes `available` when all its prerequisites are `mastered`, or `placed` with a confirmation pending.
- **Due:** when the tracker's predicted recall falls below 0.5 (the paper's forgetting line, P8b-01), status → `due`. For L4 rule skills this also sets the classmate's state to `forgotten`.

**Acceptance criteria**

| Given | When | Then |
|---|---|---|
| 3 correct answers on the same item on the same day | evaluated | not mastered |
| 3 correct answers across 2 items and 2 task types, incl. 1 production, over 2 days, with `mastery_lo` ≥ 0.6 | evaluated | mastered |
| An unsure verdict | processed | no field changes |
| A correct answer after the answer was revealed | processed | `evidence_n` unchanged, logged as `copy_practice` |

**Tests:** TS-LAD-01..10.

## 4. Feature: revisit weak prerequisites [X-PERS-07]

- **Purpose:** catch gaps that only show up downstream.
- **Learner outcome:** a forgotten prerequisite is repaired before the learner keeps failing on the skills built on it.
- **User flow:** a short "पहले ये दोहरा लें" step inside the next session.
- **Data inputs:** error tags on downstream attempts (e.g. an L4 failure whose diff is a vowel-sign error maps to L1 `vowel_sign.ె`), via a deterministic blame map in item metadata.
- **Data writes:** a `due` flag on the prerequisite (OutcomeWriter).
- **Model involvement:** none.
- **Failure behaviour:** with no blame tag, nothing is flagged.
- **Accessibility/localisation:** standard.
- **Acceptance criteria:**

  | Given | When | Then |
  |---|---|---|
  | 2 downstream failures tagged with prerequisite P within 7 days | evaluated | P is `due`, and the next session includes P before new items |

- **Tests:** TS-LAD-09.

## 5. Feature: placement diagnostic (F-PLACE) [X-PERS-03, FW-R07 for the adaptive error profile]

- **Purpose:** don't force learners through letters they know; start true beginners at L0.
- **Learner outcome:** a correct starting point.
- **User flow:** see J-3 in learner-journeys.md. The diagnostic is adaptive:
  1. Start at L2 high-frequency word recall.
  2. Two successes move up a band; two failures move down.
  3. Each band probes ≥ 2 items × ≥ 2 task types, including production.
  4. It stops after 15 minutes or when the band is stable.
- **Data inputs:** checker verdicts on held-in diagnostic items (never study test items).
- **Data writes:** `learner_skill_state.status = placed`, `source = placed`, `due_at` within 3 days for confirmation.
- **Model involvement:** none.
- **Failure behaviour:** stopping early starts the learner at the lowest unconfirmed band.
- **Accessibility/localisation:** Hindi instructions; keyboard and Devanagari typing.
- **Acceptance criteria:**

  | Given | When | Then |
  |---|---|---|
  | A learner who types all L0/L1 letters correctly and fails L2 words | diagnostic ends | L0/L1 placed, L2 available |
  | A placed skill failed at its confirmation review | processed | status → learning |

- **Tests:** TS-PLACE-01..06. Metric M-52.

## 6. Leveler (P-DIFF-01, X-LEV)

- **v0 [P]:** band = max over four dimensions. Every item stores `band` plus `band_reason` (the dimension that set it), and `leveler_version = v0`.

  | Dimension | Computed from |
  |---|---|
  | script | new letters not yet in the learner's L0/L1 mastered set; for content labelling, against the canonical order |
  | vocabulary | TMR against the band's word list (E-16 tokenizer) |
  | word forms | number of inflectional suffixes / analyser features |
  | structure | pattern family (simple, copular, negation, clause) |
- **Variants [X-LEV-02]:**
  - v1-weighted: a linear combination with teacher-set weights;
  - v1-fitted: ordinal regression fitted to teacher bands on a training split.

  They are compared on held-out teacher bands (κ) and learner comprehension. v0 is kept as the baseline. [X-LEV-04]
- **Validation [X-LEV-03]:** the leveler is not called "validated" until κ ≥ 0.6 against independent teacher ratings. Until then the UI never claims a level ("आपका स्तर" is not shown as a CEFR-like grade).

## 7. Can-do descriptors (draft, unvalidated) [X-LEV-05]

| Band | Draft Hindi descriptor (catalog key) |
|---|---|
| L0 | "आप तेलुगु के अक्षर पहचान सकते हैं और उन्हें हिंदी अक्षरों से जोड़ सकते हैं।" |
| L1 | "आप तेलुगु के छोटे शब्द अक्षर-अक्षर पढ़ और लिख सकते हैं।" |
| L2 | "आप रोज़ के आम शब्द पढ़, सुन, समझ और लिख सकते हैं।" |
| L3 | "आप किसी जगह (ऑटो, मेस) के बने-बनाए वाक्यांश बोल-लिख सकते हैं।" |
| L4 | "आप सही तेलुगु वाक्य बना सकते हैं और हिंदी-भाषियों की आम गलतियाँ पकड़ सकते हैं।" |
| L5 | "आप छोटी बातचीत में समझ और जवाब दे सकते हैं।" |

Validation happens in FW-R14. Any CEFR alignment is a separate study.

## 8. Ladder view (F-LAD-UI) [X-PERS-08]

- **Purpose:** transparency without technical scores.
- **Learner outcome:** the learner knows what they can do and why the next step was chosen.
- **User flow:** page "मेरी सीढ़ी" with three lists:
  - "अब आप ये कर सकते हैं" (mastered, by band);
  - "अभी सीख रहे हैं" (learning or due);
  - "आगे" (locked, with the prerequisite named).

  A single recommendation explains itself, e.g. "अगला: -లో और -కి, क्योंकि आप जगहों के नाम सीख चुके हैं।"
- **Data inputs:** `learner_skill_state`.
- **Data writes:** none.
- **Model involvement:** none. The text is templated from the catalog.
- **Failure behaviour:** with no data, it shows the beginner path.
- **Accessibility/localisation:** Hindi only; no percentages; screen-reader labels.
- **Acceptance criteria:**

  | Given | When | Then |
  |---|---|---|
  | Any learner | the page renders | no Latin characters, no numbers > 0 presented as scores |
  | A placed-but-unconfirmed skill | the page renders | shown under "अभी सीख रहे हैं" with the note "पक्का करना बाकी" |

- **Tests:** TS-UI-LAD, TS-L10N-01.
## 9. Implementation notes: tokenizer, TMR and leveler v0 (slice 2.3, 31 Oct 2026)

- `setu/domain/tokenize.py` (`tokenizer-1`): canonical surface forms split on whitespace; clitics and suffixes are
  not split (ఇంట్లో is one token) until an analyser replaces it under a new version.
- **TMR** counts token occurrences not in the known set. It excludes the planted rule's allowed target forms
  (`exempt`) and pure numbers, records the tokenizer version, and refuses an empty sentence.
- `setu/domain/leveler.py` (`leveler-v0`, registered in `LEVELERS` as the comparison baseline): band = the hardest
  **assessed** dimension; the result names the deciding dimension and gives its reason.

  | Dimension | Rule | Status |
  |---|---|---|
  | script | Only independent letters → L0; any vowel sign, virama, anusvara or visarga → L1 | Computed |
  | structure | One word → L2; 2–3 words → L3; 4+ words → L4; at least the contrast family's band (sentence-level contrasts L4, clause contrasts L5, `spelling` L2) | Computed |
  | vocabulary | Frequency rank thresholds 300 / 1,000 / 2,000 → L2 / L3 / L4, beyond → L5 | **Unassessed** until IndicCorp frequency ranks are imported |
  | word forms | — | **Unassessed** until the morphological analyser (Phase 4); a home-made suffix list would misfire (నేను ends in ను) and would be unreviewed Telugu analysis |

  The leveler reports unassessed dimensions and sets `complete = false`, never guessing.
- **Learner-relative extras:** letters the learner has not met (`unknown_letters`) and the TMR against the learner's
  known words.
- **Import:** new item versions store `band`, `band_reason` and `leveler_version`. Items imported before slice 2.3
  (the 49 in the dev database) keep an empty band until they next change (item versions are immutable) or the
  database is rebuilt.
- **Validation status:** thresholds and family bands are drafts. Nothing is "validated" until κ ≥ 0.6 against
  independent teacher bands (M-51).
## 10. Implementation notes: scheduler and mastery (slice 2.6, 31 Oct 2026)

- **FSRS** (`fsrs==6.3.2`, fuzzing off for reproducible intervals) for letters, akshara, words and chunks.
  Rating from the verdict: correct → Good, partial → Hard, wrong → Again, unsure → no review; any recall cue or a
  multiple-choice answer caps it at Hard. Easy is never inferred. Cards store py-fsrs state and step
  (migration 0007); every review is logged with the attempt's cue level.
- **Mastery tracker `tracker-1`**: a Beta(α, β) belief with a 90% interval (`mastery_lo`, `mastery_hi`) and a memory
  half-life.
  - A cue-free correct answer adds 1 to α and multiplies the half-life by 1.2 + 3(1 − p).
  - A partial answer adds 0.5 to each of α and β.
  - A wrong answer adds 1 to β and halves the half-life (floor 0.5 days).
  - Evidence fades towards Beta(1, 1) with a 60-day half-life.
  - Answers with a recall cue or after a reveal are not evidence.
  - Predicted recall is 2^(−days / half-life); `due_at` is when it reaches 0.5.
  - All parameters are drafts to calibrate on pilot data.
- **Unlock rule** (§3) computed from the immutable `skill_evidence` rows: at least 3 cue-free correct answers on 2+
  items, 2+ task types and 2+ days, at least one production for L2 and above, and `mastery_lo` ≥ 0.6 (in practice
  about five consecutive cue-free successes). A mastered skill whose predicted recall falls below 0.5 is `due`.
- **Forgetting:** `setu/store/scheduling.forget_due` reads (as `setu_read`) the rules the classmate knows and the
  learner's tracker for each rule's `target_skill_id`. The scheduler issues a `ForgetDecision` when predicted recall
  is below 0.5, and the OutcomeWriter applies it. Rules without a `target_skill_id` cannot be forgotten yet.
- **Baselines:** BKT (four-parameter, standard equations) and SM-2, plus log-loss and AUC, ready for M-23/M-24 once
  there is response data.
## L0 as built (slice S1, 31 Oct 2026)

- **Content:** `content/hi-te/script/letters.yaml`, generated by `python -m setu.content letters` from the
  normaliser's Unicode tables. 48 modern letters (13 vowels, 35 consonants) in varnamala order, each with its
  Devanagari twin; ఎ ఒ ళ ఱ flagged as new for Hindi readers. Archaic ఌ and ఴ are left out. All are drafts: a
  letter needs two native-speaker approvals (database check) before `learner_letter` shows it.
- **Skill graph:** per row of the varnamala, a recognition skill (`L0.script.<row>.REC`) and a recall skill
  (`.RCL`, requires the row's REC); each row's REC requires the previous row's REC. Every rule version gets a
  production skill `<band>.rule.<rule_id>.PR` as its `target_skill_id`, which lets forgetting run on real content.
- **Practice chain per new letter:** intro (no answer) → multiple choice (recognition, assisted, cue 1) → recognise
  on the full Devanagari key set (cue-free) → recall on the full on-screen Telugu key set (cue-free). Typing is
  optional. After a wrong answer the rest of the chain is `after_reveal`. Due reviews come first; at most 5 new
  letters a day. The task is held on the server (`exchange.task`), so reloading does not re-roll it, and a second
  submission changes nothing.
- **Deviations:** the anusvara/visarga and the ం-doubling difference belong to L1 (S2, with vowel signs); the
  reading game (P8b-04) and the diagnostic test-out move to S7.
## L1 as built (slice S2, 31 Oct 2026)

- **Content:** `content/hi-te/script/aksharas.yaml`, generated by `python -m setu.content aksharas`: 489 drafts.
  - 448 sign forms: the 12 vowel signs plus ం and ః on 32 consonants.
  - 32 double letters (క్క …) and 9 common conjuncts (క్ష త్ర ప్ర శ్ర స్త స్థ ష్ట ర్మ గ్ర).
  - Ordered sign by sign. The rare ఙ ఞ ఱ get no signs or doubles. Each twin is the letter-by-letter bridge (కె → कॆ).
- **Visibility:** `learner_akshara` shows an akshara only if it has two native approvals **and** every letter in it
  is approved.
- **Skills:** `L1.akshara.<family>.REC/RCL` for vowel_signs, nasal_visarga, doubles and conjuncts.
  - vowel_signs REC requires every L0 row's REC.
  - nasal_visarga and doubles require vowel_signs; conjuncts require doubles.
- **Prerequisite gate (X-PERS-04):** an akshara is offered only after the learner has recalled every letter in it,
  cue-free and correctly.
- **Practice:** the same chain as letters, with differences:
  - only the first akshara of each sign gets the intro card (a worked example); later ones start at the choice step;
  - choice distractors are the same consonant with other signs;
  - recognise and recall are built on an on-screen keyboard of every approved consonant plus every sign. It needs
    no JavaScript: each key is a server round trip that writes nothing, and only real keys are accepted. It is
    recorded as `onscreen_keyboard`, cue-free;
  - up to 10 new aksharas a day.
- **Deviations:**
  - the ంం pronunciation difference is a note on the ం intro, not its own exercise;
  - the list of 1 000+ possible conjuncts is reduced to 9 common ones until native reviewers pick more;
  - 489 aksharas each need two approvals; batch approval belongs to the teacher console (Phase 4).
## L2 as built (slice S3, 31 Oct 2026)

- **Content:** the 28 imported words (`content/hi-te/lexicon.yaml`).
  - Four false friends gained `looks_like_hi` (अवसर, उपन्यास, चरित्र, आलस्य). This is the first authored edit to a
    converted file, recorded in `content/EDITS.json`; the conversion guard test now accepts only recorded edits.
- **Migration 0010:**
  - A word needs two native approvals, the same as letters and aksharas. Before this, one `approved` status was
    enough.
  - `learner_lexeme` now also requires every letter in the word to be approved.
  - The importer fills each word's group (its source unit), ladder order and letters.
- **Skills:** `L2.word.<unit>.REC/RCL`, where REC requires `L1.akshara.vowel_signs.REC`.
- **Unlocking:** a word is offered only after cue-free recall of all its letters.
- **Chain per new word:**
  1. intro, with the meaning, a cognate note ("हिंदी के ‘पुस्तक’ जैसा") or a false-friend warning;
  2. Hindi meaning → pick the Telugu word (recognition);
  3. Telugu word → pick the meaning (recognition). For a false friend, its Hindi look-alike is one of the options;
     choosing it is wrong and the warning is shown again;
  4. build the word on the compose keyboard: letters, vowels and signs (cue-free recall).

  At most 5 new words a day.
- **Deviations:**
  - The order follows the source units, not IndicCorp frequency, which isn't available yet.
  - The unlock rule checks letters, not the specific vowel signs a word uses.
  - L2 mastery needs production, so these words cannot reach "mastered" until S4/S5 add production tasks. This is
    by design.
## L3 as built (slice S4, 31 Oct 2026)

- **Content:** `content/hi-te/chunks.yaml`, 32 chunks, 8 for each of four scenes: auto stand, mess, landlord and
  family (standing in for the "everyday" scene).
  - **They were drafted by a language model (Claude) and are unreviewed.** The provenance of every chunk says so.
  - Spoken forms (వెళ్తారా, చూడొచ్చా, వెళ్ళొస్తాను …) are marked `register: spoken` so reviewers confirm them
    (P8b-14).
  - The content plan's ~80 team-written chunks replace or extend these.
- **Migration 0011:** a `chunk` table.
  - `learner_chunk` shows a chunk only with two native approvals, an approved scene and approved letters.
- **Skills:** `L3.chunk.<scene>.REC/RCL`, where REC requires `L1.akshara.vowel_signs.RCL`.
- **Unlocking:** a chunk unlocks after cue-free recall of its letters.
- **Practice:** the word chain, with the scene's title and setup on the intro card.
  - Recall is built on the compose keyboard, which has a space key.
  - Punctuation and spacing are forgiven by the normaliser.
  - At most 5 new chunks a day.
- **Deviations:**
  - Substitution frames are deferred: combining a frame with fillers produces sentences nobody reviewed (case
    endings can change). They need approved frame-filler pairs.
  - The college scene has no chunks yet.
