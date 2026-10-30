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
