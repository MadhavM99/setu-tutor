# Memory Assistant (स्मृति सहायक): adaptive memory and visual learning subsystem

Status: **Phase 0 amendment A1** (user request, 30 Oct 2026). Spec only; nothing is implemented. Tags: **[X-A1]** amendment requirement · **[P]** paper · **[E]** engineering recommendation. Requirement numbers (R1–R15, EXP) refer to the amendment text. Traceability rows: matrix §23 (`X-MEM-AID-*`).

## 0. Position in the system

- The Memory Assistant is a first-class subsystem. It supplies **encoding aids** (mnemonics, images, audio, chunking, stories, scenes) and **fades** them.
- It never decides what the learner knows:
  - mastery comes only from checker-verified **cue-free** attempts [X-A1 R12, X-PERS-02];
  - "models write, rules decide" holds unchanged (ADR-0004).
- Learner-facing aid text is Hindi (Devanagari) plus Telugu in Telugu script. Images carry **no embedded text** of any kind. Glyphs and Hindi captions are rendered by the app from fonts [R5, R14, X-NOENG].
- **Evidence status.** Mnemonic techniques are evidence-*informed*, not proven for this pair:
  - the keyword method (Atkinson & Raugh 1975) helps immediate L2 vocabulary recall, but later studies report the advantage can shrink at long delays and benefit receptive more than productive recall;
  - dual coding (Paivio) motivates images plus words.
  These are hypotheses to test [R10, EXP]. The literature review must be done and cited in the memory study's preregistration. No claims are made before it.

## 1. Techniques and the units they apply to [R1, R2]

| Unit type | Eligible techniques (policy table `technique_policy v1`) | Grounded in (verified facts only) | Default when nothing is approved |
|---|---|---|---|
| Telugu letters / script (L0) | **Visual shape association** (approved image of an object whose shape echoes the glyph; glyph overlaid by the app); **Devanagari twin link**; **native pronunciation** audio | Glyph (font), Devanagari twin (reviewed mapping), sound (reviewed), shape-feature description (reviewed against the rendered font) | Glyph beside its Devanagari twin, drawn from fonts, plus native audio or no audio |
| Sounds new to Hindi speakers (ళ, short ఎ/ఒ, ఱ, final vowel) | **Audio contrast pairs** (minimal pairs such as కళ్ళు / కల్లు, recorded); **articulation association** (Hindi description of tongue and lips, approved) | Recorded audio; approved articulation note | Text articulation note (approved) |
| Akshara combinations (L1) | **Chunking** (consonant + vowel sign → syllable); **visual decomposition** (the app highlights glyph parts from the font outlines; no generated image) | Unicode composition; sign inventory | Decomposition view (always available; non-generative) |
| Vocabulary (L2) | **Hindi story / keyword association** (a short Hindi story linking the sound to the meaning); **imagery** (approved illustration of the meaning); **semantic association** (cognate link, word family); **contextual example** (approved sentence) | Lexeme (verified spelling, gloss, cognate or false-friend flag), approved example sentence | Cognate link or approved example sentence |
| False friends | **Contrastive visual story**: two panels, the Hindi meaning vs the Telugu meaning (e.g. अवसर "मौका" vs అవసరం "ज़रूरत"), with an explicit "यह नहीं — यह" contrast to block the wrong link | Lexeme false-friend note (reviewed) | Two-column text contrast from the catalog |
| Grammar / contrasts (L4) | **Simple pattern frame** (slots shown as boxes); **memorable approved example**; **contrastive association** (Hindi pattern vs Telugu pattern) | The rule version's approved explanation, items, and concept key | Approved Hindi explanation plus one worked example from **another** item |
| Phrases / sentences (L3/L5) | **Contextual scene** (approved scene image plus a dialogue line); **retrieval-based reconstruction** (rebuild from Hindi meaning → partial cue → no cue) | Approved chunks and scenes | Reconstruction ladder (always available; non-generative) |
| Lists of items in a scene (optional) | **Memory palace / method of loci**: anchor up to 5 scene items to fixed places in a familiar Hindi setting (घर: दरवाज़ा, रसोई…) | Approved items | Not offered |

**Rules for every technique:**
- An aid supports **one concept**.
- An aid never contains the answer to a task that is about to be scored (the timing rules are in §5).
- False-friend aids always show the contrast, never only the Telugu meaning.

## 2. Features (mandatory template)

### F-MEM-1 Technique selection and AI-teacher recommendation [R2, R3]

- **Purpose:** offer the aid most likely to help this learner with this unit.
- **Learner outcome:** better delayed cue-free recall than without the aid. This is a hypothesis, measured per aid (F-MEM-7).
- **User flow:** on a new or failed item, दीदी says "इसे याद रखने का एक तरीका:" and shows the recommended aid. "दूसरा तरीका" shows the next eligible aid. The learner may say "मुझे इसकी ज़रूरत नहीं".
- **Data inputs:**
  - unit type and eligible techniques (policy table);
  - approved aids for the concept;
  - the learner's `technique_effect` estimates (per learner × technique family: a posterior on whether items studied with this technique were later recalled cue-free);
  - item difficulty (leveler band, FSRS difficulty);
  - the learner's recent errors on the concept.
- **Decision (deterministic) [E]:**
  1. Restrict to eligible techniques that have an approved aid.
  2. Rank by expected delayed-recall gain: learner posterior, falling back to the population posterior, falling back to the policy default order.
  3. Explore with ε = 0.1 (seeded) so per-learner estimates stay identifiable.
  4. Never pick an aid that caused an incorrect association for this learner (F-MEM-7).
- **Model involvement:** optional, behind a flag. The AI teacher (दीदी) may pick **one of the top 2** deterministic candidates and phrase a one-line Hindi reason **from catalog templates with slots**. It cannot add aids, facts or techniques. Its output is validated against the candidate ids, and on failure the top-ranked candidate and a template reason are used.
- **Data writes:** `aid_event(presented, recommended_by=policy|teacher_model, rank, alternatives)`. Nothing is written to mastery.
- **Failure behaviour:** with no approved aid, the non-generative default from §1 is used. If the policy table is missing a unit type, no aid is shown and an alert is logged.
- **Accessibility/localisation:** Hindi only; a keyboard-reachable "दूसरा तरीका" button.
- **Acceptance criteria:**

  | Given | When | Then |
  |---|---|---|
  | A letter unit with approved shape and twin aids | selection runs | one of them is chosen; the choice and rank are logged |
  | A learner whose `technique_effect` for stories is lower than for images, with tight posteriors | selection runs | the image aid ranks first (except on exploration turns, which are logged as such) |
  | The model returns an aid id that isn't among the candidates | — | it is rejected and the top-ranked candidate is used |

- **Tests:** TS-MEM-SEL-01..08.

### F-MEM-2 Grounded mnemonic text [R4, R14]

- **Purpose:** verbal mnemonics, stories and articulation notes that cannot state false Telugu facts.
- **Learner outcome:** memorable, correct associations.
- **User flow:** an aid card with Hindi text; the Telugu glyph or word is shown in Telugu script.
- **Data inputs:** a **fact sheet** built from verified records only: glyph, twin, sound, shape features (reviewed), lexeme gloss, cognate or false-friend note, the approved example, the rule's approved explanation.
- **Generation [E]:**
  - **Offline only** in the first release: a drafting tool on the self-hosted model, or a hand-written draft.
  - Drafts are slot-structured JSON: `{"story_hi": "...", "uses_facts": [fact_ids], "telugu_spans": [...]}`.
- **Validation (deterministic `check_mnemonic_grounding`):**
  - every Telugu character or token appears in the fact sheet;
  - every "X = Y" or "X की आवाज़ Y" pairing matches a verified pair;
  - no other Telugu letters or words;
  - no Latin;
  - length ≤ 160 chars;
  - no grammar claims except quoting the rule's approved explanation key;
  - `uses_facts` covers the target;
  - false-friend aids must contain both meanings.

  Drafts that pass go to **teacher review** (F-MEM-6). Only `approved` aids reach learners.
- **Runtime generation:** a flag, `mem_runtime_verbal`, **off** until gate G-MEM-RT. Even when on: validated as above, labelled internally as `unreviewed`, sampled for teacher audit, never used in study conditions.
- **Model involvement:** drafting only. A model never certifies its own draft.
- **Data writes:** `memory_aid` (draft → approved).
- **Failure behaviour:** a failed draft is not stored for learners; the fallback from §1 is used.
- **Accessibility/localisation:** Hindi; a TTS or recorded audio alternative (F-MEM-5).
- **Acceptance criteria:**

  | Given | When | Then |
  |---|---|---|
  | A draft pairing ఖ with "क" | validated | rejected (`WRONG_PAIR`) |
  | A draft using the untaught letter న | validated | rejected (`UNGROUNDED_TELUGU`) |
  | A draft containing "Telugu" in Latin letters | validated | rejected (`LATIN`) |
  | A false-friend aid showing only the Telugu meaning | validated | rejected (`MISSING_CONTRAST`) |

- **Tests:** TS-MEM-GRD-01..15.

### F-MEM-3 Educational illustrations without embedded text [R5, R8]

- **Purpose:** concept images (an object, a meaning, a scene, a false-friend contrast) that the app overlays with verified text.
- **Learner outcome:** imagery-supported encoding (a hypothesis).
- **Pipeline (offline batch, never per learner):**
  1. **Concept prompt** built from the concept record only (the object or meaning in neutral Hindi plus a fixed style guide). Fixed negative instructions: no letters, numbers, signs, captions or watermarks. **No learner id, learner text or cohort data** [R8].
  2. Generate ≤ 3 candidates.
  3. **Automated checks:**
     - OCR text detection across Devanagari, Telugu and Latin (local OCR) → any text means rejection;
     - safety filter;
     - resolution and contrast checks;
     - perceptual-hash de-duplication.
  4. **Teacher review** (F-MEM-6): object correct, culturally appropriate, not misleading, no hidden text.
  5. Approved, the asset is stored with its version.
- **Rendering:** the app composes the approved image with the glyph (Noto font), the Devanagari twin and a Hindi caption, all from the catalog or verified content, as HTML/SVG layers. **Glyphs are never drawn by a model.**
- **Providers:** a self-hosted open image model is preferred. An external service is allowed **only** in the offline content-pipeline environment, with concept-level prompts (ADR-0005). The runtime app has no image-generation client.
- **Model involvement:** generation only. Approval is human, with automated pre-checks.
- **Data writes:** `visual_asset` (version, prompt, model, seed, checks, review, licence, alt text).
- **Failure behaviour:** after 3 failed candidates the concept is marked `needs_manual`, and the non-generative fallback (font-rendered glyph decomposition, or a text-only story) is used.
- **Accessibility/localisation:** a Hindi alt text is required. Contrast is checked. Meaning never depends on colour alone (shape, labels and position carry it too).
- **Acceptance criteria:**

  | Given | When | Then |
  |---|---|---|
  | A candidate in which OCR finds any glyph | checked | rejected |
  | An approved asset | rendered | the overlay text is selectable DOM text, and the image file has no text layer |
  | Any request to the image provider | inspected | the payload contains only concept fields (an allow-list schema test) |

- **Tests:** TS-IMG-01..12.

### F-MEM-4 Asset library, cache and fallback [R6, R7]

- **Purpose:** reuse approved aids; keep their history.
- **Record (`memory_aid` / `visual_asset`):** concept id; technique; version; content or asset URI; generation prompt; model and seed; automated-check results; review status (`draft | in_review | approved | rejected | retired`); reviewers; licence and provenance; Hindi alt text; audio-alternative id; contrast-check result; usage counters (presented, selected, used, later recalled cue-free); retirement reason.
- **Cache:** keyed on `concept_id + technique + version`. Shared by all learners and immutable once approved; a new version supersedes it. Runtime makes no generation calls.
- **Fallback:** every concept has a **non-generative** aid that can be computed from verified data: twin view, glyph decomposition, cognate link, approved example, reconstruction ladder. The test suite asserts coverage.
- **Data writes:** library tables; usage counters through the event log.
- **Failure behaviour:** a missing or corrupt asset means the fallback is used and an alert is logged.
- **Acceptance criteria:**

  | Given | When | Then |
  |---|---|---|
  | Every active concept | checked | ≥ 1 fallback aid is renderable without any model |
  | Two learners on the same concept | aids served | the same approved asset is served (cache hit), with no generation calls |

- **Tests:** TS-MEM-LIB-01..06.

### F-MEM-5 Audio aids and accessibility [R1, R9]

- **Native pronunciation:** recordings (consented, rights recorded) are preferred. Synthetic TTS is used only after speaker review and is marked internally.
- **Audio alternatives:** every visual aid has a Hindi audio description; recorded or reviewed TTS is acceptable for the Hindi narration.
- **Accessibility:**
  - WCAG 2.2 AA contrast for overlays;
  - no colour-only cues;
  - aid cards keyboard-operable;
  - `lang` attributes;
  - captions for audio.
- **Purpose / learner outcome:** pronunciation and sound discrimination; equal access to every aid.
- **User flow:** a listen button on aid cards; "विवरण सुनें" for audio descriptions.
- **Data inputs / writes:** `audio_asset`; `aid_event(used)` on play.
- **Model involvement:** none at runtime. Reviewed TTS is produced offline.
- **Failure behaviour:** no approved audio → the button is hidden and the text alternative shown. Native audio is never replaced by unreviewed TTS.
- **Acceptance criteria:**

  | Given | When | Then |
  |---|---|---|
  | Any shown visual aid | rendered | a Hindi alt text and a playable audio description exist (M-59) |
  | An aid card | inspected | contrast ≥ 4.5:1 for overlays |

- **Tests:** TS-MEM-A11Y-01..05.

### F-MEM-6 Teacher review of aids [R4, R6, review requirements]

| Aid kind | Reviewers before learner exposure | Review questions (Hindi form) |
|---|---|---|
| Letter-sound or linguistic claim (shape note, articulation, twin) | **2 native Telugu speakers** (same rule as content) | Is the claim correct? Is the shape description true of the font? Could it mislead? |
| Hindi story or keyword mnemonic | 1 teacher + a grounding validator pass | Natural Hindi? Memorable? Correct link? No wrong association? Culturally appropriate? |
| Illustration | 1 teacher + automated checks | Right object? No text? Not misleading or offensive? Is the alt text accurate? |
| False-friend contrast | 1 Hindi + 1 Telugu speaker | Are both meanings correct? Is the contrast clear? |
| Grammar aid | As for rules (2 speakers + teacher) | Same as rule review |

- **Purpose:** no unreviewed or false aid reaches learners.
- **Learner outcome:** learners meet only correct associations.
- **User flow:** teacher console F9.
- **Data inputs:** drafts with validator results.
- **Data writes:** review records and new aid versions.
- **Model involvement:** none.
- **Failure behaviour:** approval is blocked when reviewer counts are short, alt text is missing, or OCR flags text. Rejected aids keep their history; an aid can be retired with a reason.
- **Accessibility/localisation:** Hindi review form.
- **Acceptance criteria:**

  | Given | When | Then |
  |---|---|---|
  | A letter-sound aid with one native approval | approval is attempted | refused |

- **Tests:** TS-MEM-REV-01..05.

### F-MEM-7 Measuring whether an aid helps [R10, R12]

- **Event log (`aid_event`):**
  - `presented` (shown), `selected` (the learner chose it, or "दूसरा तरीका"), `used` (the learner opened, expanded or played it, with dwell time), `dismissed`;
  - per later attempt on the concept: `cue_level` (none / partial / full) and verdict;
  - `recalled_after_aid`, computed: the first cue-free attempt ≥ 1 day later.
- **Mastery rule:** viewing, selecting or using an aid **never** changes mastery or FSRS beyond the rules in F-MEM-8. Only cue-free checked attempts count [X-PERS-02].
- **Per-aid effectiveness [E]:**
  - **Micro-randomisation**: for eligible items, a seeded 15% of first encounters get the non-generative default instead of the top aid.
  - Effect = the difference in cue-free recall at ≥ 1 and ≥ 7 days, per technique and per aid, with Beta posteriors.
  - Shown to teachers as "अनुमान" with n.
  - Aids with credible harm or no benefit after n ≥ 30 exposures are flagged for review.
- **Incorrect associations:** errors that match an aid-specific *lure* are logged as `aid_misassociation`. Each aid declares its lures: e.g. the keyword itself instead of the Telugu word, the Hindi meaning of a false friend, a look-alike glyph.
- **Acceptance criteria:**

  | Given | When | Then |
  |---|---|---|
  | An item answered correctly with the aid visible | processed | the attempt is `cue_level=full`; mastery unchanged |
  | A recall error equal to the aid's declared lure | processed | an `aid_misassociation` event is logged |

- **Tests:** TS-MEM-MEAS-01..08.

### F-MEM-8 Cue fading and FSRS integration [R11, R13]

- **Cue ladder per concept:**

  | Level | Shown |
  |---|---|
  | 3 | Full aid (image or story plus glyph and audio) |
  | 2 | Partial (image only, or first syllable, or the story title) |
  | 1 | Minimal (Hindi meaning only, which is the task prompt itself) |
  | 0 | No cue |

  - Each correct cue-free recall moves the concept down one level.
  - A failure at level 0 brings back level 2 for the next encounter only.
  - Tests and probes always run at level 0.
- **FSRS [E]:**
  - Discrete items (letters, akshara, lexemes, chunks) are FSRS cards per modality.
  - An attempt where an aid was visible **before** answering is logged with `cue_level > 0`. It updates FSRS with a rating capped at **Hard**, and never counts toward unlock or mastery.
  - Cue-free attempts update FSRS normally.
  - Aid scheduling is integrated: an aid is offered only at encoding (new or relearning) and after a lapse, never on a routine due review. The fading level is stored per (learner, concept).
  - Rules and skills keep the mastery tracker, and aids for grammar follow the same cue-level rules.
- **Data writes:** `concept_cue_state(learner, concept, level)`, FSRS review log with `cue_level`.
- **Acceptance criteria:**

  | Given | When | Then |
  |---|---|---|
  | 3 correct cue-free recalls | processed | level 0 reached; aid hidden by default |
  | A due review | the session is planned | no aid is shown before the answer |
  | A study test | rendered | cue level 0 |

- **Tests:** TS-MEM-FADE-01..08, TS-SCHED-MEM-01..04.

## 3. Interfaces

| Interface | Kind | Notes |
|---|---|---|
| `lookup_verified_facts(concept_id)` | Read-only tool (drafting tool, teacher model) | Returns the fact sheet only |
| `check_mnemonic_grounding(concept_id, draft)` | Deterministic validator / tool | Reasons: `UNGROUNDED_TELUGU`, `WRONG_PAIR`, `LATIN`, `TOO_LONG`, `GRAMMAR_CLAIM`, `MISSING_CONTRAST`, `MISSING_TARGET`, `UNSAFE` |
| `check_image_asset(asset)` | Offline pipeline check | OCR text, safety, contrast, dHash |
| `GET /aid/{concept_id}` | Learner HTTP | Returns the approved aid fragment at the learner's cue level, or the fallback |
| `POST /aid/event` | Learner HTTP | presented / selected / used / dismissed (idempotent) |
| Teacher `/teacher/aids…` | Review queue, approve / reject / retire, alt-text edit | See teacher-console.md F9 |
| `content aids draft|check|generate-images|import` | Offline CLI | Budgeted; writes drafts only |

## 4. Cost controls [E]

- **No generation at runtime.** Images and mnemonic drafts are produced only in the offline pipeline. (Runtime verbal generation is flagged off until G-MEM-RT.)
- **Budget file** `content/aid_budget.yaml`:
  - per-concept caps: ≤ 3 image candidates, ≤ 2 regeneration rounds, ≤ 3 text drafts;
  - per-batch and monthly spend ceilings (GPU-seconds or currency);
  - the CLI refuses to run past the ceiling.
- **Cost ledger:** every generation call is logged with provider, model, seconds and cost, and summarised in the scorecard (M-62).
- **Priority order:** fallback-only concepts first; then L0 letters (~60 concepts); then the top 300 lexemes; then false friends; then scenes.
- **Reuse:** one approved asset serves every learner. Retiring an asset doesn't regenerate it automatically.

## 5. Failure behaviour summary [X-RULES-07]

| Failure | Behaviour |
|---|---|
| No approved aid | Non-generative fallback |
| Grounding validator fails | Draft rejected; not stored for learners |
| Image has text, wrong object, or is unsafe | Rejected; after 3 attempts, manual creation or fallback |
| Image provider unavailable or over budget | Batch stops; nothing reaches learners; fallback stays in use |
| Asset missing at runtime | Fallback, plus an alert |
| Aid would reveal the answer to the current scored task | Not shown before the answer (§2 F-MEM-8; validator `AID_REVEALS_ANSWER`) |
| Aid shows harm (misassociation or lower recall) | Flagged; teacher may retire it; the policy stops selecting it |
| Teacher model chooses an invalid aid | Top-ranked deterministic candidate |

## 6. Release gates

Added to metrics-and-gates.md.

| Gate | Requires |
|---|---|
| **G-MEM-ASSET** (any aid shown to pilot learners) | 100% of shown assets `approved`; OCR text-free check passed (M-58 = 0 text in shown images); Hindi alt text present (M-59 = 100%); licence recorded; linguistic aids approved by 2 speakers; fallback coverage 100% (M-60) |
| **G-MEM-GROUND** | Grounding validator: 0 ungrounded facts on a held-out set of ≥ 60 adversarial drafts (M-57); teacher audit of 50 approved aids finds 0 factual errors |
| **G-MEM-RT** (runtime verbal generation) | G-MEM-GROUND, plus ≤ 2% of runtime drafts rejected after sampling, plus a cost ceiling |
| **G-MEM-EXP** (memory study) | Ethics approval incl. the 30-day follow-up; preregistration; balanced materials |

## 7. Reverse-learning study consistency [EXP]

In the reverse-learning study, conditions **A, B and C receive identical memory support**:
- the same aid assets;
- the same cue levels and fade schedule;
- the same number of aid presentations per rule.

The memory policy runs in **fixed mode**: no exploration and no adaptive selection. Aid exposures are logged and checked for balance (TS-STUDY-10). The adaptive memory policy is studied only in the separate memory experiment.
