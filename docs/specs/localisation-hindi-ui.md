# Hindi-only learner UI: localisation spec

Requirement [X-NOENG]: the learner-visible product is entirely in natural, simple Hindi written in Devanagari. Telugu appears only in Telugu script. There is no English and no Roman script anywhere a learner can see. Internal identifiers, logs and developer docs may be in English.

## 1. Feature: string catalog and lint (F-L10N)

- **Purpose:** make "no English" a property you can test, not a hope.
- **Learner outcome:** a fully Hindi interface; no confusion from mixed scripts.
- **User flow:** all pages.
- **Data inputs:** `locale/hi.yaml`, with keys grouped by `nav.*`, `btn.*`, `fb.*`, `hint.*`, `err.*`, `ladder.*`, `onb.*`, `tch.*`, `res.*`.
- **Data writes:** none.
- **Model involvement:** none for UI strings. Model text shown to learners must pass `display_check`: Devanagari and Telugu only, plus digits and punctuation.
- **Failure behaviour:** a missing key fails at build time, never at runtime.
- **Accessibility/localisation:**
  - `lang="hi"` on the page;
  - `lang="te"` on Telugu spans;
  - Noto fonts self-hosted;
  - screen-reader labels in Hindi;
  - digits in Devanagari for counts (configurable).
- **Lint [E-03]:** CI fails if any value in `locale/hi.yaml`, any Jinja template under `templates/learner/` or `templates/teacher/`, or any learner-facing reason string matches `[A-Za-z]`. Exceptions are declared in `locale/allow-latin.txt`, which starts empty; adding to it needs an ADR.
- **Acceptance criteria:**

  | Given | When | Then |
  |---|---|---|
  | The full E2E learner flow | crawled by Playwright | 0 Latin characters in visible text (M-54) |
  | A checker reason code | shown | rendered through its catalog key in Hindi; the raw code is never shown |

- **Tests:** TS-L10N-01..05.

## 2. Terminology (draft; teacher review required)

| Concept | Hindi term |
|---|---|
| Lesson / practice | अभ्यास |
| Check | जाँच |
| Correct / partly right / wrong | सही / आंशिक रूप से सही / गलत |
| Teacher will check | शिक्षक देखेंगे |
| Hint | संकेत |
| Answer (after 2nd miss) | सही वाक्य |
| No mistake | इसमें कोई गलती नहीं |
| Skill ladder | मेरी सीढ़ी |
| Review | दोहराना |
| Classmate | सहपाठी — राजू |
| Coach | दीदी (hints only; no free Q&A with a model) |
| Native friend | रवि |
| Settings (learner) | पसंद |
| Progress | आप क्या कर सकते हैं |
| Teacher console | शिक्षक कक्ष |
| Research console (researchers only, may be in English per [X-RULES-08]) | शोध — internal |

## 3. Persona and tone

- **राजू** is a fellow adult learner from Lucknow who has just moved to Hyderabad. He is *not* a 12-year-old. He is polite and brief, asks "सही है?" and "पर ऐसा क्यों?", thanks the learner calmly, and never celebrates himself, never explains grammar, and never uses emoji. This changes setu `writer.py:34-44`.
- **दीदी** gives hints only, chosen from approved hint types. Free questions to a model are removed (privacy, P-ETH-05). A "सवाल पूछें" button may later route questions to the teacher queue.
- **रवि** speaks Telugu lines limited to the learner's level. Set-ups are in Hindi.

## 4. Romanisation policy [X-NOENG]

- Off by default (`learner.romanisation_enabled = false`).
- It may be turned on only if a teacher approves it for a learner, as a temporary aid. It is shown beside the Telugu, never alone, and fades with the same rule as the Devanagari aid.
- The Devanagari reading aid is not romanisation: it is the learner's own script. [P8b-05]

## 5. Strings to remove from the current product (audit §2)

- "Progress", "Teacher", "Settings", "Setu · Telugu for Hindi speakers", "lessons", "Module", "CHECK", "hint", "Lesson याद करो", "Level", "Unit", "status: draft_unverified…", "Day … turns … model calls", "Last steps (log)".
- "Raju" in Latin letters.
- English checker reasons.
- "(2/2 key ideas)".
- The Telugu-script wrong-script message.
- From the LMA hosted app: all English UI.

## 6. Memory aids and Raju lines (amendment A1)

- **Aid text** (stories, captions, articulation notes, alt text, audio descriptions) is Hindi in Devanagari, plus Telugu only in Telugu script. The grounding validator rejects Latin.
- **Images contain no text at all.** Any glyph or caption is rendered by the app as DOM/SVG text from fonts and the catalog (`lang` attributes set). OCR rejects images with text in any script.
- **Raju's Hindi lines** are catalog entries under `raju.*` only (classmate-output-contract.md §1). The lint also checks that templates rendering Raju's turns take no free-text variables except the validated Telugu sentence slot.
