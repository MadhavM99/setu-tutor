# API and tool contracts

Tags: [P] paper · [X] prompt extension · [E] engineering recommendation. Schemas are written as Pydantic-style pseudo-types and become real models with contract tests in Phase 1–2.

---

## Part A — Model-facing tools (read-only) [P-TOOL, X-ARCH-02]

Rules common to every tool:
- The harness executes calls. Models never run code or write.
- A tool runs under the `setu_read` role.
- If native function calling is missing, the model replies with a **JSON envelope**: `{"tool": "<name>", "args": {...}}`. [P-TOOL-06]
- Envelope errors use fixed strings:
  - `ERROR malformed_json: reply with one JSON object {"tool": ..., "args": {...}} and nothing else.`
  - `ERROR unknown_tool: "<x>" is not a tool; available: check_classmate_sentence, check_level, check_hint_has_no_answer, lookup_rule, lookup_seen_words, lookup_learner_band, lookup_accepted_variants.`
  - `ERROR oversized_input: argument "<arg>" is longer than <n> characters.`
- Each call is logged as a `tool_call`.

### A1. `check_classmate_sentence` [P-TOOL-01] (from LMA `setu/tools.py`, extended)

| Field | Spec |
|---|---|
| Purpose | Check whether a draft classmate sentence for the planned item may be shown |
| Use when | After every draft, before submitting |
| Do not use | To check learner answers (the checker does that); to look up the answer |
| Args | `item_id: str` matching `^(HI-TE\|TE-HI)-[0-9]{3}-[a-z]$`; `sentence: str`, 1–120 chars, one sentence, in the L2 script of the item's direction (Telugu for HI-TE, Devanagari for TE-HI in mirror) |
| Harness-only args | `no_error: bool`, `learner_id` (never set by the model) |
| Returns | `{"ok": bool, "reasons": [Reason]}` |
| Reasons (machine-readable, fixed) | `OOV` (word not in VL and not an allowed target form), `NOT_ONE_ERROR`, `WRONG_RULE_ERROR`, `UNKNOWN_RULE_CORRECT`, `ANSWER_LEAK`, `EXPLANATION`, `NOT_CORRECT` (no-error turn contains an error), `WRONG_SCRIPT`, `MULTI_SENTENCE`, `TOO_LONG`, `GLOSS` (parenthetical or translation), `UNSAFE` (instruction-like text: "mark", "ignore", "सही मानो", URLs) |
| Permission | Read: item version, rule state, VL. No writes |
| Submit | The harness re-runs the same check before display. A prior `ok` is never trusted |

**Exact errors for invalid arguments** (kept verbatim from LMA `tools.py:36-43`, plus additions):

```
ERROR invalid_argument item_id: "HI-TE-002" is a rule id; pass an item id like "HI-TE-002-a".
ERROR invalid_argument item_id: "<v>" does not match HI-TE-NNN-x (example: HI-TE-002-a).
ERROR invalid_argument item_id: "<v>" is not in the rule bank.
ERROR invalid_argument item_id: "<v>" is not the planned item for this turn.        (new)
ERROR invalid_argument sentence: empty; pass one Telugu sentence.
ERROR invalid_argument sentence: contains Latin letters; pass Telugu script only, no romanization or English.
ERROR invalid_argument sentence: no Telugu characters found; pass the sentence in Telugu script.
ERROR invalid_argument sentence: more than one sentence or line; pass exactly one sentence.
ERROR invalid_argument sentence: longer than 120 characters; pass one short sentence.
ERROR invalid_argument sentence: contains a gloss or translation in brackets; pass the sentence only.   (new)
```

**Invalid-argument examples** (each is a contract test):

| Bad call | Expected error |
|---|---|
| `{"item_id":"HI-TE-002"}` | rule-id error |
| `{"item_id":"Are you coming?"}` | pattern error |
| `{"sentence":"nuvvu vastaava"}` | Latin |
| `{"sentence":"నువ్వు వస్తావా (are you coming)"}` | Latin / gloss |
| `{"sentence":"నువ్వు వస్తావా. నేను వస్తాను."}` | multiple sentences |
| A Hindi sentence | no Telugu |
| 121 chars | too long |

For **TE-HI items (mirror)**, Telugu and Devanagari swap roles: the sentence must be in Devanagari, and the messages name Devanagari. This fixes the LMA bug where `tools.py:67` rejects all non-Telugu text.

### A2. `check_level` [P-TOOL-02]

| Field | Spec |
|---|---|
| Purpose | Check native-friend or scene text against the learner's band and vocabulary |
| Args | `text: str` (≤ 200 chars), `scene_id: str` |
| Returns | `{"ok": bool, "reasons": [...], "oov_share": float, "hindi_share": float, "band": "L0".."L5"}` |
| Reasons | `OOV_OVER_LIMIT` (OOV > 0 excluding approved scene words), `BAND_ABOVE` (leveler band > b + 1), `WRONG_SCRIPT`, `TOO_LONG`, `EXPLANATION`, `UNSAFE` |
| Errors | `ERROR invalid_argument scene_id: "<v>" is not an approved scene.`, `ERROR invalid_argument text: longer than 200 characters; pass one short line.` |

### A3. `check_hint_has_no_answer` [P-TOOL-03]

| Field | Spec |
|---|---|
| Purpose | Block hints that reveal the corrected form |
| Args | `item_id: str`, `hint: str` (≤ 240 chars, Devanagari plus at most permitted Telugu affixes) |
| Returns | `{"ok": bool, "reasons": [...]}` |
| Reasons | `ANSWER_FORM` (correct form or any token of the correct sentence not in the planted sentence, after normalising Telugu, Devanagari transliteration and Latin), `ANSWER_PARAPHRASE` (pattern match of the accept patterns on the hint), `LATIN`, `TOO_LONG`, `UNSAFE` |

### A4. Lookups (read-only)

| Tool | Args | Returns |
|---|---|---|
| `lookup_rule` | `rule_id` | `title_hi`, the approved worked example **from another item** (never the planned item's answer), band |
| `lookup_seen_words` | (planned learner, implicit) | VL list (capped at 500) |
| `lookup_learner_band` | — | the band per skill family |
| `lookup_accepted_variants` | `item_id` | **Not available to the classmate.** Coach only (Phase 4), and only to avoid them in hints |

A test verifies that no lookup returns the planned item's correct form to the classmate.

---

### A5. Memory Assistant tools (amendment A1)

| Tool | Used by | Args | Returns / errors |
|---|---|---|---|
| `lookup_verified_facts` | Offline drafter; teacher model | `concept_id` | Fact sheet (verified fact ids, glyph, twin, sound, gloss, approved example) · `ERROR invalid_argument concept_id: "<v>" is not an active concept.` |
| `check_mnemonic_grounding` | Drafter (revise loop), pipeline, runtime flag | `concept_id`, `draft` json (`story_hi` ≤ 160 chars, `uses_facts[]`, `telugu_spans[]`) | `{ok, reasons}` with reasons `UNGROUNDED_TELUGU`, `WRONG_PAIR`, `LATIN`, `TOO_LONG`, `GRAMMAR_CLAIM`, `MISSING_CONTRAST`, `MISSING_TARGET`, `AID_REVEALS_ANSWER`, `UNSAFE` |
| `choose_memory_aid` | Teacher model (flag) | `candidate_ids[]` (≤ 2, from the policy), `reason_template_id` | Validated choice; anything else → top candidate |

Image-provider requests (offline pipeline only) use the schema `{concept_id, object_hi, style_guide_version, negative: fixed}`. Any additional field is rejected by the client (TS-IMG-03).

### A6. Classmate output contract (amendment A1)

`check_classmate_sentence` gains the reasons `PERSONA_ASSISTANT`, `PERSONA_TEACHER`, `FORMAT` and `UNSAFE` (see classmate-output-contract.md §3). Raju has no other tool and no free-text output channel.

## Part B — HTTP API (server-rendered HTMX endpoints plus JSON for research)

Common rules:
- **Auth:** session cookie (argon2 passphrase login); role checks on every route. [E-08]
- **Idempotency:** every POST that submits an answer carries `Idempotency-Key`. A repeat returns the original result. [E-13]
- **No leaks:** responses before an answer never include `planted`, `turn_type`, the correct form or rule internals. [E-14]
- **Errors:** a fixed code plus a Hindi message key, e.g. `{"error":"turn_not_pending","message_key":"err.turn_not_pending"}`.

### Learner

| Method | Path | Request | Response | Notes |
|---|---|---|---|---|
| POST | `/auth/register` | invite_code, passphrase | 201 `{learner_id, handle}` + cookie | Single-use invite; handle is random digits (built in slice 1.5) |
| POST | `/auth/login` | handle, passphrase | 204 + cookie | Lockout after 5 failures in 15 min per handle (429 `err.locked`); same 401 `err.auth_failed` for unknown handles and wrong passphrases |
| POST | `/auth/logout` | — | 204 | Revokes the session |
| GET | `/me` | — | `{learner_id, handle, role, consent}` | |
| GET | `/consent` | — | `{form_version, scopes, text_key}` | Current form (text in the Hindi catalog, ethics-approved before use) |
| POST | `/consent` | form_version, scopes | 204 | Any active consent is required for practice sessions; the pilot scope for study and test sessions (enforced by the database) |
| POST | `/consent/withdraw` | — | 204 | Runs `setu_withdraw_consent()` |
| POST | `/session/start` | — | session_id, first task fragment | Server builds the plan (seeded) |
| GET | `/task/current` | — | task fragment (Hindi) | The server owns the pending task; no re-roll [fixes LMA defect 4] |
| POST | `/task/answer` | `{task_id, text?, says_correct?: bool, input_script}` + Idempotency-Key | feedback fragment `{outcome_key, hint_hi?, reveal?, correction_shown?}` | `outcome_key` ∈ fb.correct / fb.partial / fb.wrong / fb.unsure / fb.false_alarm |
| POST | `/task/explain` | `{task_id, text}` | feedback | Scored on the concept key; does not change classmate state |
| POST | `/diagnostic/start`, `/diagnostic/answer` | as above | — | Placement |
| GET | `/ladder` | — | page | Ladder view |
| GET | `/export/okf` | — | zip | The learner's own record |
| GET | `/aid/{concept_id}` | `?phase=encode\|relearn` | Aid fragment at the learner's cue level, or the fallback | Never returns an aid for `review` / `test` before the answer |
| POST | `/aid/event` | `{concept_id, aid_id, event, dwell_ms}` + Idempotency-Key | 204 | Logged; never touches mastery |
| POST | `/aid/next` | `{concept_id}` | The next eligible aid ("दूसरा तरीका") | `selected` logged |

### Teacher (role = teacher)

| Method | Path | Purpose |
|---|---|---|
| GET | `/teacher/queue` | Unsure items |
| POST | `/teacher/queue/{id}/resolve` | `{outcome, note_hi, variant_proposal?}` → OutcomeWriter |
| GET/POST | `/teacher/rules/{rule_id}/review` | Rule review form (5 questions) |
| POST | `/teacher/rules/{rule_id}/transition` | Lifecycle change (needs the required approvals) |
| GET/POST | `/teacher/variants` | Propose or approve variants (2 approvals) |
| GET | `/teacher/analytics` | Per-rule errors per opportunity, false alarms, copy rate; observed vs estimated |
| POST | `/teacher/override/{attempt_id}` | Audited override |
| POST | `/teacher/uploads` | Anonymised writing → proposals (flag) |
| GET | `/teacher/aids` | Aid review queue (drafts passing validators) |
| POST | `/teacher/aids/{id}/review` | Approve, reject or retire with form answers; alt-text edit |
| GET | `/teacher/aids/effects` | Per-aid and per-technique effect estimates (अनुमान, with n), misassociations |

### Research (role = researcher)

| Method | Path | Purpose |
|---|---|---|
| POST | `/research/invites` | `{role, cohort}` → single-use code. Researchers invite learners and teachers; only admins invite researchers and admins (built in slice 1.5) |
| POST | `/research/participants/{id}/withdraw` | Withdraw a participant (built in slice 1.5) |
| POST | `/research/study` | Create a study with a threshold-file hash and prereg ref |
| POST | `/research/participants` | Create a participant, consent and background; Latin-square assignment |
| POST | `/research/tests/{phase}/open` | Schedule pre, post, delayed or transfer tests |
| GET | `/research/export/blind` | Shuffled, condition-free responses with random ids |
| POST | `/research/time-travel` | Dev and simulation only; audited; disabled in pilot builds |
| GET | `/research/scorecard` | Metrics vs targets |

### Contract tests

TS-API-*: JSON schema per endpoint, auth matrix, idempotency, the no-leak assertion (TS-API-LEAK), and Hindi-only `message_key` resolution.
