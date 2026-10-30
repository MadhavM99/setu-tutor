# Teacher console

Hindi-first UI [X-TCH-01]. The role is `teacher`; every action is audited in `event_ledger`. Estimates are never shown as observations. [X-TCH-10] Tags: [P] paper · [X] prompt extension · [E] engineering recommendation.

Every feature follows the template: Purpose · Learner outcome · User flow · Data inputs · Data writes · Model involvement · Failure behaviour · Accessibility/localisation · Acceptance criteria · Tests.

## F1. Rule review and promotion [P-EVAL-11, X-TCH-02]

- **Purpose:** decide whether a rule is valid and may be planted.
- **Learner outcome:** learners only ever see verified, natural Telugu.
- **User flow:**
  1. "नियम जाँच" list (filters: direction, lifecycle, validity).
  2. Rule page: every item, the error span highlighted, accepted variants, hints, sources and licence, version history.
  3. Form with 5 questions: acceptable/natural (1–5), category correct (हाँ/नहीं), explanation accurate and useful (1–5), band fit (L0–L5), confidence (1–5), plus a Hindi comment.
  4. Buttons: approve, reject, or mark uncertain.
- **Data inputs:** `rule_version`, `item_version`, `hint`, `data_source`.
- **Data writes:** `rule_review`; lifecycle transitions as new `rule_version` rows.
- **Model involvement:** none.
- **Failure behaviour:** a transition without the required approvals is refused, with a Hindi message naming what is missing.
- **Accessibility/localisation:** Hindi labels; Telugu shown in Telugu script; keyboard-operable.
- **Acceptance criteria:**

  | Given | When | Then |
  |---|---|---|
  | A rule with one speaker approval | promotion to `verified` is attempted | refused |
  | Two approvals that disagree on category | — | the rule goes to a third-reviewer task |
  | `verified` without `teacher_approved` | activation is attempted | refused |

- **Tests:** TS-TCH-REV-01..06.

## F2. Two-rater agreement [X-TCH-03, M-29]

- **Purpose:** measure how reliable the reviews are.
- **Learner outcome:** indirect (trustworthy content).
- **User flow:** a batch view showing raters, κ per question (category, band) and the disputed items.
- **Data inputs:** `rule_review`.
- **Data writes:** `kappa_report`.
- **Model involvement:** none.
- **Failure behaviour:** with n < 10, "κ अभी नहीं निकाला जा सकता" is shown instead of a number.
- **Accessibility/localisation:** the term "सहमति (κ)" is explained in Hindi.
- **Acceptance criteria:**

  | Given | When | Then |
  |---|---|---|
  | A fixture with known labels | computed | κ matches a reference implementation to 3 decimals |

- **Tests:** TS-TCH-KAPPA.

## F3. Unsure queue and settlement [P-ARCH-10, X-TCH-04]

- **Purpose:** settle answers the checker could not judge.
- **Learner outcome:** the learner gets credit after review; the checker never guesses.
- **User flow:**
  1. The queue lists the learner's answer, the item, accepted forms, the checker's reason code (in Hindi) and context.
  2. The teacher chooses सही, आंशिक or गलत, with an optional "इसे मान्य रूप के तौर पर प्रस्तावित करें".
- **Data inputs:** `verdict(unsure)`, item.
- **Data writes:** `teacher_resolution`; OutcomeWriter applies the outcome (mastery and classmate update if correct); a `content_proposal` for the variant.
- **Model involvement:** none.
- **Failure behaviour:** if two teachers resolve the same item concurrently, the first wins and the second sees "पहले ही निपटाया गया".
- **Accessibility/localisation:** Hindi.
- **Acceptance criteria:**

  | Given | When | Then |
  |---|---|---|
  | An unsure item | resolved as correct | exactly one ledger event with `actor = teacher:<id>`, the learner's state updated once |
  | A proposed variant | — | becomes accepted only after a second approval |

- **Tests:** TS-TQ-01..06.

## F4. Variant, regional-form and naturalness review [X-TCH-05, P8b-14]

- **Purpose:** keep accepted forms correct while still allowing spoken and regional Telugu.
- **User flow:** proposed variants, each with its register (written/spoken), region, examples and the approvals so far.
- **Data inputs and writes:** `accepted_variant` (proposed → approved needs 2 approvals).
- **Model involvement:** none.
- **Failure behaviour:** a rejected variant keeps its history.
- **Accessibility/localisation:** Hindi.
- **Acceptance criteria:** an approved spoken variant is accepted by the checker from the next session on. TS-TCH-VAR.

## F5. Learner-writing upload → proposals (gated) [X-TCH-06, FW-R08]

- **Purpose:** find real errors in learner writing.
- **User flow:**
  1. Upload text with a consent id.
  2. A PII scrub runs (numbers, names list, emails).
  3. The deterministic checker and pattern matcher propose spans and rule matches.
  4. The teacher accepts or rejects.
  5. Accepted items update `opportunities` and `observed_errors` and may move evidence to `observed`.
- **Data writes:** `content_proposal` only, until the teacher approves.
- **Model involvement:** none in Phase 4. An LLM span proposer is a roadmap item and its output is always `model_predicted`.
- **Failure behaviour:** without a consent id, the upload is refused.
- **Accessibility/localisation:** Hindi.
- **Acceptance criteria:**

  | Given | When | Then |
  |---|---|---|
  | An upload | processed | zero rule changes until approval |
  | Text containing a phone number | uploaded | stored scrubbed |

- **Tests:** TS-TCH-UP, TS-PRIV-05.

## F6. Analytics [X-TCH-07, X-TCH-10, P-BANK-08]

- **Purpose:** show class-level learning and problems honestly.
- **User flow:** a class view and a per-rule view.
  - Errors per opportunity (k/n), false alarms, copy rate, common misconceptions (top error tags), unsure cases, and progress by skill.
  - Each number is labelled as one of: "देखा गया" (observed), "अनुमान" (estimate, from the tracker), "डेटा नहीं", or "मॉडल का प्रस्ताव — जाँचा नहीं गया".
- **Data inputs:** verdicts, attempts, `learner_skill_state`.
- **Data writes:** none.
- **Model involvement:** none.
- **Failure behaviour:** with n < 5 opportunities, "कम डेटा" is shown and no rate.
- **Accessibility/localisation:** colour is never the only cue; Hindi labels.
- **Acceptance criteria:**

  | Given | When | Then |
  |---|---|---|
  | A rule with 6 errors in 40 opportunities | shown | displayed as "40 में 6", never "6 गलतियाँ" alone |
  | Estimated mastery | shown | carries the अनुमान label |

- **Tests:** TS-TCH-AN-01..04.

## F7. Teacher override [X-TCH-08]

- **Purpose:** in future classroom use, the teacher has final authority over automatic feedback.
- **User flow:** on any attempt, "फ़ैसला बदलें", with a reason required.
- **Data writes:** `teacher_override`, then applied through OutcomeWriter with a compensating event. The original verdict is kept.
- **Model involvement:** none.
- **Failure behaviour:** without a reason, the override is refused.
- **Acceptance criteria:**

  | Given | When | Then |
  |---|---|---|
  | An override | applied | the ledger shows both events; the analytics mark the item as overridden |

- **Tests:** TS-TCH-OVR.

## F8. Exports [X-TCH-09]

- **Purpose:** share only what may be shared.
- **User flow:** export datasets (rules, items, anonymised attempts).
- **Data inputs:** approved content; consented learners; licensed sources.
- **Rule:**
  - only `lifecycle = active | verified` content;
  - only learners with consent scope `data_sharing`;
  - sources whose licence permits it.

  Everything else is excluded, with a count of excluded rows.
- **Tests:** TS-TCH-EXP.
