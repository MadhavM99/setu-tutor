# Current-product audit (Phase 0)

Audited on 30 Oct 2026, read-only, before the baseline commit `7b84c7e` on branch `redesign/phase0-spec`.

Two codebases were audited:

| Name used here | Path | Role in the redesign |
|---|---|---|
| **setu-tutor** | `~/Developer/setu-tutor` | The product being rebuilt (decision D1). Streamlit app, no commits before the baseline. |
| **LMA** | `~/Desktop/LMA---Reverse-learning-Tutor` (team repo `FavianaNoronha/LMA---Reverse-learning-Tutor`, HEAD `c11a63a`) | The research implementation of the paper. Used as a source to reuse code and data from. |

File:line references point into the repo named in each section. Every criticism is tied to an observed flow or a code path. Claims marked ✔ were re-verified by hand during Phase 0 (lines read, or the checker probed with the real code).

---

## 1. setu-tutor: inventory

| Area | Finding | Evidence |
|---|---|---|
| Framework / runtime | Streamlit multipage app (`st.navigation`) and a terminal CLI, both over one engine (`setu/tutor.py`) that returns plain dicts | `app.py:13-26`, `setu/cli.py` |
| Python | `.venv` is 3.9.0; Docker image is python:3.11-slim | `Dockerfile:3` |
| Package manager | pip with an unpinned `requirements.txt` (pydantic≥2, streamlit≥1.40, certifi, pytest); no lockfile. `width="stretch"` probably needs a newer Streamlit than 1.40 | `requirements.txt`, `web/learn.py:75` |
| Routes / pages | सीखो और Raju को सिखाओ (default) · Progress · Raju की कॉपी · अक्षर-पुस्तक · Teacher · Settings; the course map is in the sidebar | `app.py:13-19`, `setu/web.py:187-217` |
| State | Per-learner JSON `runs/<id>.json` (pydantic `LearnerRecord`); the open question is kept in `rec.pending`, so the page redraws from disk; UI state lives in `st.session_state` | `setu/memory.py:42-101`, `setu/tutor.py:473-487` |
| Database | **None.** JSON files and a jsonl teacher queue | `memory.py:93-101` |
| Auth | **None.** The learner id is any typed name. Teacher and Settings pages are open to everyone | `web/settings.py:13-16`, `setu/web.py:169-171` |
| Hosting | Docker; volume `/data`; port 8501; Google Fonts loaded from the network | `Dockerfile`, `setu/web.py:27` |
| Model provider | Google AI Studio (`GeminiAPI`, default `gemma-4-26b-a4b-it`; 7 auth/variant fallbacks), Gemini image models ("Nano Banana"), vision check, or an OpenAI-compatible URL | `setu/llm.py:28,75-181,197-243,255-282` ✔ |
| Timeout | 20 s in code; the README and docstring say 12 s | `llm.py:273` ✔, `README.md:155` |
| Prompts | Raju persona "12-year-old classmate… mix things up"; Raju task and reaction prompts; Didi (teacher, receives the learner's free question); trick, picture, picture-check and SVG prompts; Ravi (friend); offline hook drafting | `writer.py:34-119`, `didi.py:20-76`, `aids.py:28-49`, `friend.py:15-47`, `scripts/draft_hooks.py:22-34` |
| Integrations | Google AI Studio (text, vision, image), optional OpenAI-compatible server, Google Fonts | — |
| Tests | 12 files, 98 functions, **138 cases pass in 7 s** with model keys unset. With `GEMINI_API_KEY` set, some tests call Google for real and `test_no_model_configured_means_templates` fails | `tests/test_raju.py:225-228`, `tests/test_web.py:25`, `tests/test_rules.py:84` |
| CI, logs, analytics | No CI. The log keeps the last 30 events in the learner JSON. No analytics | `memory.py:42-56` |

## 2. setu-tutor: learner journey, screen by screen

1. **First open.**
   - Sidebar: "👤 me", "0 / 45 lessons" and an emoji course map (✅ ▶️ ⬜ 🔒).
   - Main page: "🌉 Setu", a 6-chip path bar (📖 सीखो · ⚡ अभ्यास · ✅ जाँच · 🧒 Raju… · ❓ क्यों? · 🔁 दोहराओ) and "शुरू करो ▶".
   - No onboarding, name, consent or placement. The only shortcut is Settings → "सीधे यहाँ से शुरू करो".
   - Evidence: `web/learn.py:191-215`.
2. **Cards.**
   - Big Telugu = Hindi, an emoji or AI picture, example word, shape description, mnemonic, "दीदी की तरकीब ✨" and "🙋 दीदी से पूछो".
   - The first view blocks on a spinner "AI … बना रहा है… 10–30 सेकंड".
   - Evidence: `learn.py:98, 218-240`, `web.py:224-258`.
3. **Drill.**
   - "अभ्यास (गिनती नहीं होगी)": "అ = ?", and the answer is typed **in Hindi**.
   - A miss shows the card again with a Didi hint. After 3 misses the answer is shown and the item marked weak.
   - Evidence: `learn.py:241-251`, `tutor.py:321-363`.
4. **Check.**
   - "CHECK · गिनती होगी · यहाँ कोई hint नहीं". Getting it right makes the unit "ready" and adds it to Raju's notebook.
   - The check stays open until answered correctly.
   - Evidence: `tutor.py:365-384` ✔.
5. **Raju lesson (step x.4).**
   - Raju's bubble ("मुझे लगता है ఖ = क … सही है?"), the caption "✨ AI ने लिखा · 5 checks pass", a reply box and "✓ कोई गलती नहीं".
   - Then follow-ups, and finally `st.balloons()` with "🎉 Module … पूरा!".
   - Evidence: `learn.py:179-185` ✔, `followups.py:33-42`.
6. **Daily cap.** 3 new lessons a day, then "आज के लिए बस!" and up to 3 spot checks. Evidence: `tutor.py:47, 235-249`.
7. **Revision.** "🔁 दोहराओ: Raju भूल गया" comes first when Raju forgets a unit (recall below 0.5). Evidence: `tutor.py:212-225`, `raju.py:39-46`.
8. **Rules chapter.**
   - A scene box with Ravi's line, sentence cards with a Devanagari reading aid, then drill and check (Hindi keyboard accepted).
   - Raju plants an error; then "पर ऐसा क्यों?" asks for an explanation (keyword-scored); then a second sentence to judge.
   - Evidence: `web.py:128-152`, `followups.py:13`, `checker.py:57-71`.

**English and other non-Hindi text the learner sees** (violates X-NOENG):
- "Progress", "Teacher", "Settings", "Setu · Telugu for Hindi speakers", "{n} / 45 lessons", "Module 1 · …", "Raju" in Latin letters.
- "CHECK … hint", "Lesson याद करो".
- Raw English checker reasons: "Raju's mistake left unchanged", "not the right answer", "a known mistake", "not a known right or wrong answer; a teacher will check".
- "(2/2 key ideas)".
- Letters page "Level / Unit / status: draft_unverified · … drafted by Claude (AI)".
- Progress page "Day … turns … model calls … Last steps (log)" with raw JSON.
- A wrong-script hint written in **Telugu script** ("తెలుగు లిపిలో రాయండి"), which a beginner cannot read.
- Evidence: `app.py:10-18`, `web.py:191`, `course.py:41`, `learn.py:255`, `tutor.py:66` ✔, `checker.py:29-43` ✔, `letters.py:17-25`, `progress.py:17-32`.

## 3. setu-tutor: teaching features and intended outcomes

| Feature | Intended outcome | Does it produce it? |
|---|---|---|
| Letter cards (twin, shape, mnemonic, example, emoji) | Script recognition by Devanagari analogy | Partly. Recognition only; there is no Telugu recall or typing for letters |
| Drill until right | Retrieval practice | Undermined: the first-miss hint shows the answer (§5.1) |
| Scored check | Mastery gate | No. One answer, usually a prompt just drilled (39/45), cannot fail, and the hint shows the answer |
| Raju letter "mistakes" (ఖ = क?) | Learning by teaching | Weak. It is a yes/no recognition quiz wrapped in a persona |
| Raju sentence mistakes (15 rules) | Correcting transfer errors | Closest to the paper. The checker is loose (§5.3) |
| "Why?" explanation | Self-explanation | Can be gamed with keywords (§5.3) |
| Didi Q&A and hints | Help with misconceptions | Sends the learner's text to a commercial model; hints the wrong letter (§5.9) |
| Ravi scene line | Context | Unreviewed model text, not in the teacher view |
| AI tricks and pictures | Memory hooks | Unreviewed. They include mixed-script nonsense and unchecked objects |
| L1 words (numbers, greetings, question words, tatsama, false friends) | Core vocabulary | 28 cards. No frequency list, no FSRS, no listening |
| Forgetting → revision | Spacing | Half-life stand-in, not FSRS (`memory.py:4` ✔) |
| Progress and letter-book pages | Self-monitoring | They show lesson counts and logs, not demonstrated skills |
| `Word` / `reading_forms` | Reading units | Dead code; no data uses it |

## 4. setu-tutor: data structures

**Learner** (`memory.py:42-56`):
- Fields: `learner_id, day_offset, units{uid: UnitMemory}, raju{uid: state}, fu_done, fu_from, pending, last_unit, variety, weak[], modules_done[], model_calls, turns, log[30]`.
- Missing: profile, stored direction, consent and placement.

**UnitMemory:**
- Fields: `introduced_at, ready, correct, wrong, last, half_life`.
- `p = 2^(−days/h)`. A correct answer doubles h (×1.2 for recognition), a wrong answer halves it (floor 0.5), and unsure is ignored.

**Raju state:** `unknown → learning → taught → forgotten` (`contracts.py:16`, `raju.py`).

**Content** (`contracts.py`):
- `Unit{unit_id, level 0-3, title, tip, lesson[], check, items[], words, key_ideas, habit, followups, requires, status, version, reviewer, source}`
- `Item{item_id, prompt, accepted[], raju_wrong, wrong_forms[], answer_script, closed, kind, accept_regex[], wrong_regex[]}`
- The status values `draft_unverified | native_checked | teacher_verified` are **never checked by code** (`bank.py`).

**Rules** (`data/hi-te/rules.json`):
- 15 rules, 29 items.
- Fields `rule_id, name, category, l1_habit, transfer, version, reviewer, reviewed_at, source, title, title_hi, explain_hi, key_ideas, status`; items have `item_id, english, hindi, accepted, planted_error, wrong_regex, fix_regex`.
- **There are no validity or learner-evidence fields.**
- Every source reads "Claude draft (unreviewed)".
- The loader drops `name, category, transfer, english, title, reviewed_at` (`bank.py:33-45`).

**Course** (`course.json`): 3 chapters → 15 modules → 45 units: 24 letter (L0), 6 word (L1) and 15 rule units (5 scenes: auto, mess, landlord, family, college).

**AI aids** (`runs/ai/aids.json`, shared by all learners): tricks and pictures with status `ai | liked | approved | rejected`.

**Teacher queue:** jsonl lines `{learner, item, answer, kind}`. Display only; resolving one means hand-editing files (`teacher.py:30`).

**Content gaps:**
- Letters ఙ ఞ ఱ ః and the vowel signs ై ౌ are missing.
- `wrong_forms`, `followups`, `image` and `words` are empty everywhere.
- L0-04's tip uses untaught letters (నయా).
- L0-15 uses "फल" as the example for both ప and ఫ.
- HI-TE-011's explanation contains a garbled "(మైం/वह)".
- Several Raju mistakes use letters the learner has not been shown.

## 5. setu-tutor: why the experience feels gimmicky and does not teach

Ordered by harm to learning.

1. **Hints give the answer.**
   - `_hint` returns "Lesson याद करो: {hindi} → {telugu}" for every letter and word item (`tutor.py:60-67` ✔).
   - It appears after the first miss in the check that says "यहाँ कोई hint नहीं" (`tutor.py:384` ✔), in Raju turns (`:415`) and in follow-ups (`:470`).
   - After two misses "सही जवाब: …" is printed, and the check simply stays open (`tutor.py:381-383` ✔).
   - Result: a learner can "master" every unit by typing what the hint shows. Mastery measures persistence.
2. **One-answer mastery and recognition only.**
   - One correct check makes a unit ready and teachable to Raju (`tutor.py:369-371` ✔).
   - 39 of 45 checks repeat a drilled prompt; rule checks are copies of the last item (`bank.py:38-39`), so "एक नया सवाल" (`learn.py:207`) is untrue.
   - Letters are only tested Telugu → Hindi. There is no cue-free Telugu production for letters, no listening, no own sentences and no unseen items.
3. **The checker can be fooled.**
   - It checks `accept_regex` before `wrong_regex` (`checker.py:28-35` ✔).
   - Probed with the real code:
     - "అమ్మను" alone → correct for HI-TE-012-a ✔
     - "ఇంటికి" alone → correct for HI-TE-015-a ✔
     - "ఇది జో నేను చదివిన పుస్తకం", which still contains the planted జో → **correct** ✔
   - The "why" scorer accepts keyword salad ("क्या आ", "है नहीं", "ki lo"), and its key ideas include English and romanised words ("end", "last", "kya").
   - This is the paper's "worst action": marking wrong Telugu correct.
4. **Unreviewed AI content is shown to learners.**
   - Tricks with mixed-script nonsense ("ఔषध", "'ఉ'प नमक"; status `ai`).
   - Gemma SVG pictures whose only check is "no text possible" are labelled "✨ AI चित्र · अक्षर असली font से लिखा है" with no warning (`web.py:245-249` ✔, `aids.py:201-203`).
   - Ravi's lines cannot be reviewed (`teacher.py:42-44`).
   - All content is `draft_unverified`, and nothing gates on it.
5. **Gimmicks instead of a tutor.**
   - `st.balloons()` and "🎉" (`learn.py:183-185` ✔), a toast for liking a trick, emoji everywhere.
   - Raju is "a 12-year-old … playful" kid who celebrates ("शाबाश मुझे!", `writer.py:28,34-44`).
   - Picture generation blocks the page for 10–30 s or more; `runs/me.json` shows repeated `MODEL_ERROR: timeout` and HTTP 500.
   - None of these are tied to demonstrated mastery.
6. **English in the learner UI.** Listed in §2.
7. **Privacy and authority.**
   - Didi puts the learner's free question into a prompt sent to Google AI Studio (`didi.py:61-63` ✔). This contradicts `README.md:107` ("What the learner types is never put into a prompt") and the paper's "no commercial API sees learner text".
   - The API key can be sent in a URL query string (`llm.py:177-178`).
   - With no auth, anyone can switch learner, reset, time-travel, or mark everything taught (`settings.py:23-27, 88, 92-98`; `tutor.py:557-575`).
   - JSON writes race: `Aids.mark` writes without `_LOCK` while a background thread writes (`aids.py:93-117`).
8. **Missing learning machinery.** No placement, no FSRS, no per-skill or per-modality tracking, no frequency-ordered vocabulary, no chunk layer, no audio, no own-sentence production, no unseen transfer items.
9. **Smaller defects.**
   - The check loses its step header because pending is saved without `step` (`tutor.py:361`).
   - Didi hints the *next* letter after a 3rd miss (`learn.py:30-35`).
   - The leak filter's NOT_ONE_CLAIM is a substring test, so "क" inside "कार्ड" satisfies it (`leakfilter.py:74`).
   - ANSWER_LEAK misses Devanagari transliterations of the answer (`leakfilter.py:63-73,161`).
   - Didi receives the full card, including the answer, and can paraphrase it.
   - Dead code: `Word` pipeline, `planner.choose` "lesson" branch, `raju.in_state`, `followups.as_item`.

## 6. LMA research repo: inventory and status

**Stack:**
- Python with pydantic v2, FastAPI and uvicorn. The LLM is called through stdlib `urllib` (`OpenAICompatLLM`, temperature 0.8, max_tokens 120, no auth header).
- A browser-only hosted app (one vanilla-JS HTML file) on GitHub Pages from `/docs`.

**Persistence and auth:**
- JSON per learner, a jsonl queue and `localStorage`.
- No database and no auth: `/api/reset` and `/api/inside` work for any `learner_id`. The README suggests a public tunnel.

**Tests:** 116 collected (54 functions, one parametrised over 63 cases). The docs say 112. **Not run in Phase 0**, because no local Python has pytest or pydantic installed. Playwright is missing, so the JS parity check could not run either.

**Prompts:** classmate v0.1, agent v0.1 and the prompt-only baseline are quoted in full in the audit notes. Raju's fixed lines are in Hindi; the rest of the UI is English.

| Paper component | Status | Evidence |
|---|---|---|
| Planner (error-weighted, p_no_error 0.2) | Verified | `planner.py:11-21`, `session.py:120` |
| Classmate state unknown/taught/forgotten, forgetting at recall < 0.5 | Verified | `state.py:8-26`, `session.py:116` |
| VL | Partial: tokens of the accepted sentences of introduced rules | `session.py:93-95` |
| Leak filter (OOV, NOT_ONE_ERROR, UNKNOWN_RULE_CORRECT, ANSWER_LEAK, EXPLANATION, NOT_CORRECT) | Verified (regex v0) | `leakfilter.py:24-57` |
| TMR | Missing | — |
| Checker | Partial: 3 verdicts, `partial` "planned for v1" | `schemas.py:12`, `checker.py:18-22` |
| Coach | Partial: fixed hints; the 2nd hint is "Answer: …"; no no-answer check; titles give answers (HI-TE-003/004/005/013) | `coach.py:6-9` |
| `check_classmate_sentence` tool | Verified: pattern, 120 cap, exact error strings, re-validation, 3-call fallback | `tools.py:7-43`, `agent.py:62-73` |
| Native friend, mirror mode, OKF, IndicXlit, analyser, ASR | Missing | checklist |
| TTS | Browser `speechSynthesis` only | hosted template `:563-569` |
| FSRS, BKT | Missing: half-life placeholder | `memory.py:2-35` |
| Ledger | Partial: the only writer of Raju state, but turn versions are not persisted (trace keeps the last 14) | `ledger.py`, `session.py:66,138-141` |
| Teacher queue | Partial: display only; hosted labels affect only the CSV; "Mark checked" does nothing | hosted `:801,817` |
| Script bridge | Verified (not native-checked) | `script.py` |
| Study A/B/C, tests, Latin square | Built, with validity defects (below) | `session.py:232-310` |
| Simulated learners v0 | Verified (parametric) | `simlearner.py` |
| Scorecard, held-out split | Built; split rewritten on every run; n = 8 / 6 | `scripts/evaluate.py:19-61` |
| Injection tests | 4 attacks, mock only | `tests/test_injection.py` |
| TE→HI | Data only; **broken end to end** | `session.py:47-49`, `tools.py:67`, `checker.py:39-50` |

**Study validity defects:**
1. The test item is the worked example shown at intro, and the "transfer" item is the intro check item, so neither is unseen (`session.py:99-104, 273`).
2. Conditions get unequal help in the hosted app: word tiles, a pre-filled box and Yes/No only in A; B skips the intro check.
3. The Latin square is a 3-way rotation by `sum(ord(id)) % 3`.
4. `/api/turn` lets a learner re-roll a turn, and it reveals `turn_type`.
5. Unanchored `fix_regex` approves wrong "no-error" sentences.
6. 83% of turns are no-error, so Raju never forgot or was re-taught in the simulation.
7. "I don't know" on a test floods the teacher queue.
8. The blind marking sheet is sorted by answer text with sequential ids.
9. Calls per turn is reported as 1.14, but should be 1.0 for a mock that never leaks.
10. Older iOS Safari fails on regex lookbehind and `||=`.

**Data:**
- HI→TE: 15 rules / 29 items. TE→HI: 10 rules / 20 items, all `draft_unverified` / `model_predicted`.
- 63 Stage-A cases; 145 teacher-label rows with **0** labels filled; native review 0 of 25 rules.
- Defects:
  - HI-TE-010-a plants more than one error.
  - HI-TE-001 plants Hindi क्या written in Telugu script.
  - HI-TE-008 is a positive control but still gets errors planted.
  - HI-TE-014's explanation cites English, not Hindi.
  - `కాదు$` flags correct noun negation.
  - `^(ఇది|అది) \S+ ఉంది$` flags correct locatives.

**Results honesty:** mostly honest; mock runs and "by construction" are labelled. Gaps:
- stale counts;
- the checker was tuned on its own scorecard;
- tautological metrics (SFS, RMSE, controllability with a mock);
- there are no real-model or human results.

## 7. Status map (product being rebuilt + reuse source)

| Status | Items |
|---|---|
| **Already working** (kept, refactored) | Script conversion (setu `text.py`, LMA `script.py`); Raju state machine with single-writer updates (both); leak-filter check families; tool contract and error strings (LMA); agent revise/submit loop with harness re-validation (LMA); error-weighted planner (LMA); parametric simulator v0 (LMA); scorecard (LMA); Hindi template lines (setu `writer.py`); learner-id sanitising (setu `memory.py:74`); HTML escaping of model text (setu `web.py`); SVG sanitiser (setu `aids.py:54-74`, only if pictures return later) |
| **Partially working** | Checker (3 verdicts, loose patterns); VL (proxy); coach (fixed, leaky titles); teacher queue (display only); ledger (versions not persisted); study mode (validity defects); "why" scoring (gameable); no-error turns (share uncontrolled) |
| **Missing** | Postgres; auth; FSRS; mastery tracker with uncertainty; BKT/SM-2 baselines; TMR; `partial` verdict; IndicXlit; analyser; native friend (LMA) / checked friend (setu); mirror mode; OKF export; placement diagnostic; L0–L5 ladder; per-modality tracking; vocabulary frequency ladder; chunks; audio; own-sentence task; teacher console (review, κ, settlement, variants, uploads, analytics); data-source register; consent flow in the app |
| **Broken** | Hints reveal answers (setu); scored check cannot fail (setu); accept-before-wrong precedence (setu); TE→HI end to end (LMA); held-out split rewritten each run (LMA); test and transfer items not unseen (LMA); Didi hints the wrong letter (setu); step header lost (setu) |
| **Duplicated** | Two engines (setu `tutor.py`, LMA `session.py`); two checkers; two leak filters; three front ends (Streamlit, FastAPI static page, hosted JS port); two copies of the HI→TE bank with different fields |
| **Unsafe** | No auth on either repo; learner text to a commercial API (setu Didi); unreviewed AI text and pictures shown to learners; API key in a query string; JSON write races; public tunnel recipe (LMA); `SETU_DEMO=1` returns answers; `turn_type` leak (LMA) |
| **Gimmicky** | Balloons, 🎉, emoji UI, the celebrating child persona, AI pictures and tricks, blocking spinners (setu); "Raju (AI)" label on a scripted stand-in in the hosted app; demo mode staging leaky drafts (LMA) |

## 8. Known failures from logs

`runs/me.json` (day_offset 43) shows:
- `MODEL_ERROR: timeout` and HTTP 500 fallbacks;
- 27 model calls over 26 turns;
- L0-01 and L0-02 forgotten, L0-03 taught;
- a pending revision turn written by the model.

These come from a single developer test learner, so there is no learner data to analyse.
