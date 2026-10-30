# Content and the bidirectional transfer-error bank

Tags: [P] paper · [P8b] newer paper copy · [X] prompt extension · [E] engineering recommendation.

## 1. Principles

- One Hindi–Telugu **contrast table** feeds two direction-specific rule books. [P-BANK-01]
- **Validity** and **learner evidence** are separate fields and are never merged. [P-BANK-04]
- Only rules with `validity=verified`, `teacher_approved` and `lifecycle=active` may be planted. [P-BANK-05, X-BANK-07]
- Learner evidence only sets priority.
- Corrections create new versions; nothing is overwritten. [P-BANK-06]
- Rates are always reported per opportunity (k / n). [P-BANK-08]
- Global similarity (WALS κ = 0.442; Grambank κ = −0.025) is **not** used to predict errors. [P-TYP-01]

## 2. Rule record

The columns are in data-model.md. Value sets:

| Field | Values |
|---|---|
| validity | `verified` = wrong in context, with the correction and accepted variants checked against a grammar and by two speakers · `uncertain` = context, register or regional variants still need checking · `rejected` = the contrast or the correction was wrong |
| learner_evidence | `model_predicted` (proposed by an LLM acting as an L1 learner; candidate only) · `predicted` (from the contrast table) · `proxy` (seen for another L1, e.g. another Dravidian L1 learning Hindi) · `observed` (seen in Hindi↔Telugu learner data, per opportunity) · `replicated` (observed again in an independent sample) |
| lifecycle | draft → review → verified → active → deprecated / rejected |

**Item must-haves** before a rule becomes `active`:
- exactly one error span;
- anchored wrong and accept patterns;
- a no-error equivalent;
- vocabulary prerequisites;
- allowed target forms;
- a concept key with no Latin;
- 3 hints (recast, l1_rule, contrast), each validated by `check_hint_has_no_answer`;
- ≥ 10 items per rule (6 practice, 2 test-held-out, 2 diagnostic) [P-PLAN-05].

## 3. Contrast families (Table 6), to be reviewed before activation [P-BANK-16..24]

| Family | HI→TE expected error (hypothesis) | TE→HI expected error (hypothesis) | Current drafts |
|---|---|---|---|
| Gender on adjectives, possessives, verbs | — | wrong gender, esp. inanimate nouns (Chinnappa 1978, proxy) | TE-HI drafts (LMA); TH-GEN-01 |
| 3rd-person pronoun gender | wrong choice among అతను / ఆమె / అది | — | HI-TE-007 |
| Negation | separate negator word (కాదు) where Telugu uses a verbal affix | negator after the verb | HI-TE-005 (fix the `కాదు$` pattern that flags correct noun negation) |
| Polar questions | initial question particle instead of final -ā | क्या omitted | HI-TE-001 (fix: the planted క్యా is a Hindi word in Telugu script; review whether it is a plausible learner error) |
| Copula | है-style copula (ఉంది) inserted in verbless X-is-Y | है dropped | HI-TE-002 |
| Relative clauses | जो…वो style (జో) | clause placed before the noun | HI-TE-010 (fix: 010-a plants more than one error; only 1 item exists) |
| "We" incl./excl. | one form for both | — | HI-TE-006; TH-CLU-01 (band 3 vs L0–L2: logged) |
| Possession | — | dative मुझे for owning objects | HI-TE-003 |
| Ergative ने | ने-like marking (HI-TE-011) | ने dropped or misused | HI-TE-011 (garbled explanation to fix), TE-HI drafts |
| Adverbial clauses | subordinator word where Telugu uses a verb suffix | — | **missing** |
| Respect agreement | singular ending with మీరు (weak) | — | HI-TE-009 (`transfer = unclear`) |
| "She" / "it" | separate feminine form expected | — | **missing** |
| New sounds | ళ / ల, short ఎ / ఒ (కళ్ళు vs కల్లు) | — | L0 letters only; add as script-confusion rules |
| Other drafts | case -లో (004), animate -ను (012, `unclear`: Hindi को also marks animates), continuous (013), కోసం (014: explanation cites English), -కి (015), agreement control (008: a positive control that is still planted, to be reclassified as no-error-only) | — | HI-TE-004, 008, 012–015 |

**TH-GEN-01** and **TH-CLU-01** (paper §6.2) are imported as `uncertain` / `draft`, exactly as in the paper. [P-BANK-09]

## 4. Offline construction pipeline [P-BANK-12..15]

1. **Typology diff.** WALS (chapters 20–128, 143–144) and Grambank features that differ become candidate leads (`content_proposal`, origin `typology`).
2. **Grammar check.** Each lead is checked against reference grammars (Krishnamurti & Gwynn 1985; NCERT/CIIL for Hindi) and by two native speakers per language; disputes go to a third. The MT-divergence checklist (Krishnamurthy, n.d.) is used. The review form records: acceptable/natural, category correct, explanation accurate and useful, band fit, reviewer confidence. Cohen's κ is computed per batch.
3. **Corpus layer.** The LTRC Hindi–Telugu corpus (~700K pairs; a few hundred simple pairs selected) shows how each contrast is realised. Translation pairs are **not** learner errors. Licence must be confirmed first.
4. **LLM proposals.** Allowed only as `model_predicted` drafts.
5. **Pilot and learner writing.** Supplies `observed`, then `replicated`. Unexpected errors are kept as new candidates.

## 5. Other content types

| Type | Source | Size target | Review |
|---|---|---|---|
| Letters and akshara | Unicode twin mapping + setu L0 units (24) + missing letters ఙ ఞ ఱ ః and signs ై ౌ | All Telugu letters and signs; gunintalu | Native check of shapes, sounds, mnemonics. The setu L0-04 / L0-15 issues are fixed |
| Lexicon | IndicCorp v2 frequency (top 2,000) ∩ textbook topic order; Kanojia (~150 shared words); setu L1 cards (28) | 300 for the first release, growing to 1,000 | Gloss and false-friend notes reviewed |
| Chunks | Team-written per scene | ~80 | Two speakers |
| Scenes | Auto stand, mess, landlord, everyday (the setu "family" and "college" modules are merged or deferred) | 4 scripts | Teacher review before any expansion [X-BEG-04] |
| Audio | Native recordings of the 100 most used items | 100 | Consent and rights record; speaker review |
| Own-sentence tasks | Per L3–L5 skill | ≥ 2 per skill | Two speakers approve frames |
| Test pools | Held-out items per rule, including harder items | 2+ per rule | Never shown in practice |

## 6. Data-quality register

| ID | Issue | Action | Phase |
|---|---|---|---|
| DQ-01 | Planned 15 HI→TE + 10 TE→HI rules × 10 items (250) vs 29 + 20 items existing | Author the missing items; dashboard tracks counts | 1/6 |
| DQ-02 | Two v8 PDFs with different content | Uploaded = primary; P8b rows track the additions | 0 |
| DQ-03 | All Telugu content is drafted by Claude and unreviewed (setu and LMA) | Native review is the critical path; no learner exposure before G3 | 6 |
| DQ-04 | HI-TE-010-a plants more than one error; HI-TE-010 has a single item | Rewrite; add items | 1 |
| DQ-05 | HI-TE-001 plants a Hindi word in Telugu script (క్యా) | Speaker review: is this a plausible learner error? | 1 |
| DQ-06 | HI-TE-005 `కాదు$` flags correct noun negation; `^(ఇది\|అది) \S+ ఉంది$` flags correct locatives | Anchor patterns; add counter-examples to tests | 2 |
| DQ-07 | Unanchored accept patterns (`అమ్మను`, `ఇంటికి`, `చదివిన పుస్తకం`) accept fragments | Anchor; test fragments | 2 |
| DQ-08 | Rule titles reveal answers (HI-TE-003/004/005/013) | Rewrite titles; validate | 1 |
| DQ-09 | HI-TE-008 positive control is planted | Reclassify as no-error-only | 1 |
| DQ-10 | HI-TE-014 explanation cites English, not Hindi; HI-TE-012 transfer doubtful | Speaker review; possibly `rejected` | 6 |
| DQ-11 | Key ideas contain English and romanised words | Rebuild concept keys in Devanagari and Telugu only | 1 |
| DQ-12 | setu L0-04 tip uses untaught letters; L0-15 example "फल" used for both ప and ఫ; HI-TE-011 garbled "(మైం/वह)" | Fix in content review | 1 |
| DQ-13 | AI tricks with mixed-script nonsense (`runs/ai/aids.json`) | Not migrated | 1 |
| DQ-14 | Teacher label sheet: 145 synthetic rows, 0 labels, not blind | Re-export shuffled with random ids; label with a teacher | 4/6 |
| DQ-15 | TH-CLU-01 band 3 while the paper's bands are L0–L2 | Item band vs ladder band separated (learning-ladder.md) | 0 |
| DQ-16 | Spoken vs textbook forms (వస్తున్నా / వస్తున్నాను) | Variants with `register = spoken` after approval | 6 |

## 7. Memory-aid content pipeline (amendment A1)

1. **Concepts** are derived from active content (letters, sounds, akshara, lexemes, false friends, rules, chunks, scenes). Each has a fact sheet built **only** from verified fields.
2. **Non-generative fallback** is created automatically for every concept: twin view, glyph decomposition, cognate link, approved example, reconstruction ladder.
3. **Drafts:** hand-written by teachers or the team, or model-drafted offline. Drafts must pass `check_mnemonic_grounding`, and each declares its lures.
4. **Images:** concept-only prompts → ≤ 3 candidates → OCR, safety and contrast checks → teacher review. Glyphs and captions are overlaid by the app.
5. **Audio:** native recordings with consent and rights; reviewed TTS for Hindi audio descriptions.
6. **Review:** see the reviewer table in memory-assistant.md F-MEM-6. Linguistic aids need 2 native speakers.
7. **Budget:** `content/aid_budget.yaml`; cost ledger; priority L0 → top-300 lexemes → false friends → scenes.
8. **Versioning:** approved aids are immutable; corrections create versions; retirements keep their history.

New DQ entries:
- **DQ-17:** the legacy tricks in `runs/ai/aids.json` must not be imported as approved; they enter only as drafts.
- **DQ-18:** shape descriptions in the setu L0 cards were "checked against Noto Sans Telugu" by an AI. They need native and teacher review before they can serve as facts.
