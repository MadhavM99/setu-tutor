# SETU: how the system works

Written for the four team members and the TA. Every file, function and number here was checked against the code and
a running app on 15 Nov 2026 (branch `research/final-audit`, based on `origin/redesign/phase0-spec` at `f9faee4`).
Where the paper and the code differ, the code is described. (`01_research_audit.md`, written on the machine where the
audit ran, was never pushed; the changes made since are recorded in [03_audit_and_changes.md](03_audit_and_changes.md).)

**Update, 15 Nov 2026 evening.** The app now calls `classmate.propose(method="tool_history")`: on a retry the model
sees its own rejected draft. Section 4 below is the trace recorded *before* that change, with the old `method="tool"`,
and is kept as it was because it is the evidence for the change.

## 1. The short version

**For someone new to LLM agents.** SETU teaches Telugu to people who already speak Hindi. After the learner has
picked up letters, words and phrases, a classmate called Raju shows up. Raju writes a Telugu sentence with one
mistake in it, the kind of mistake a Hindi speaker makes. The learner fixes it. If the fix is right, Raju "learns"
that rule; if the learner later forgets the rule, Raju forgets it too and makes the mistake again.

A language model may write Raju's sentence and the coach's hint, but it is never trusted. Ordinary program code
checks every piece of model text before the learner sees it, and ordinary code alone marks answers and updates the
learner's record. If the model's text fails a check, the app shows a sentence a teacher approved earlier. The team's
slogan is "models write, rules decide".

**For the research discussion.** SETU is a FastAPI + PostgreSQL 16 tutor with a six-level ladder (L0 letters to L5
scenes). Its L4 activity is a correction exchange against a knowledge-controlled peer whose state
(`classmate_rule_state`) is data, not model memory. Three LLM roles (Raju, coach, native friend) are proposal-only:
outputs pass deterministic gates (`setu/domain/leakfilter.py`, `friend.choose_line`) or are replaced by bank text.
Grading is a deterministic checker (`setu/domain/checker.py`) that issues unforgeable `Verdict` objects; the single
writer (`setu/store/outcome_writer.py`) accepts only those, a signed `TeacherResolution`, or a scheduler
`ForgetDecision`, runs under a restricted database role, and appends to a ledger. Memory is FSRS for discrete items
plus a Beta mastery tracker for rules. The research around it compares model capabilities (tool calling, stepwise
reasoning, retrieval, fine-tuning, role separation) on small frozen case sets, measures the checker against one
native speaker's labels, and simulates three teaching conditions.

## 2. Terms used below

| Term | Meaning here |
|---|---|
| Reverse learning | The learner corrects a classmate's mistakes instead of only answering questions |
| Planted error | The one deliberate mistake in Raju's sentence, tied to one rule |
| Rule | One Hindi-to-Telugu contrast, e.g. "no word for `है` in `यह किताब है`" (25 in the bank) |
| Item | One sentence pair for a rule: Hindi meaning, correct Telugu, wrong Telugu (49 in the bank) |
| Deterministic | Plain code with no model: the same input always gives the same output |
| Leak filter | The checks on Raju's sentence: only the planned mistake, no answer given away, no unseen words |
| Tool calling | The model replies with a request such as `{"tool": "check_classmate_sentence", ...}` and the program runs it |
| RAG | Retrieval-augmented generation: look up relevant rule text first, give it to the model with the question |
| FSRS | A spaced-repetition scheduler that predicts when a card will be forgotten and when to review it |
| Mastery | The tracker's estimate that the learner can use a rule, with rules for when a skill counts as learned |
| Evaluation harness | The scripts that run a method over fixed cases and score it |
| Ablation | Removing or changing one part to see how much it contributes |
| Leakage (evaluation) | Tuning on the same cases you then report as a test |
| Kappa (κ) | Agreement between two labellers beyond what chance would give: 0 is chance, 1 is perfect |

## 3. Components

LLM = uses a language model. DET = deterministic code.

| Component | Kind | Purpose | Input → output | Where | Depends on | How it fails | Tests |
|---|---|---|---|---|---|---|---|
| Normaliser | DET | Make a typed answer comparable: detect script, convert Telugu typed with Devanagari letters, flag Latin | raw text → `Normalised(status, text, candidates)` | `setu/domain/normalise.py` `normalise_answer`, `match_forgiving` | nothing | Latin input is `needs_transliteration`; the Devanagari converter passed 12 of 14 native checks | `tests/unit/test_normalise.py` (38) |
| Checker | DET | The only source of marks | answer + `ItemKey` → `Verdict` correct / partial / wrong / unsure with a reason code | `setu/domain/checker.py` `check_fix`, `check_own`, `check_recall`, `check_choice`, `check_explanation` | normaliser | Says `unsure` for any form not in the bank (18.2% on held-out cases); weak on "partial" (κ 0.15 against native labels) | `test_checker.py` (41), `test_stage_a.py` (484 frozen cases) |
| Verdict | DET | A mark that cannot be forged | minted only via `Verdict._mint_verdict` with the checker's capability | `setu/domain/verdict.py` | checker | In-process Python can be bypassed by determined code; the DB role and triggers are the second layer | `test_authority.py` (19) |
| OutcomeWriter | DET | The only code that changes learner state | `Verdict` / `TeacherResolution` / `ForgetDecision` → rows in `verdict`, `skill_evidence`, `learner_skill_state`, `learner_lexeme_card`, `classmate_rule_state`, `event_ledger` | `setu/store/outcome_writer.py` `record_verdict`, `apply_resolution`, `apply_forget`, `apply_placement` | checker, scheduler, Postgres role `setu_writer` | Refuses anything else (`NotAVerdict`, `ConflictingVerdict`, `ResolutionRefused`) | `tests/db/test_outcome_writer.py` (21), `test_grants.py` (37), `test_ledger_and_immutability.py` |
| Planner | DET | Decide the turns of a session | rule states + seed → `Plan(turns)` of planted / no_error / own | `setu/domain/planner.py` `plan_session` | DB state | With nothing to plant it gives own-sentence turns | `test_planner.py` (11) |
| Exchange ladder | DET | Steps inside one turn: answer → hint → copy → (why) → close | answers so far → next `Step` | `setu/domain/exchange.py` `step`, `choose_hint` | leak filter | – | `test_exchange.py` (23), `tests/db/test_correction.py` |
| Scheduler | DET | FSRS for cards, Beta tracker for rules, "learned" rule, forgetting | verdict + cue level → rating, new card state, mastery status | `setu/domain/scheduler.py` `fsrs_rating`, `fsrs_review`, `track`, `mastery_status`, `forget_if_due` | `fsrs==6.3.2` | Tracker accuracy (AUC) was never measured | `test_scheduler.py` (27), `tests/db/test_scheduling.py`, `test_reteaching.py` |
| Leak filter | DET | Gate on every model output | sentence + `Context` → list of reason codes (empty = pass) | `setu/domain/leakfilter.py` `check_sentence`, `check_hint`, `check_level` | checker item key, tokenizer | For 43 of 49 items it accepts only the exact bank sentence, so a valid paraphrase is rejected | `test_leakfilter_and_tools.py` (34), frozen leak cases |
| Raju | LLM | Write one Telugu sentence with the planned mistake | rule title, Hindi meaning, allowed words, last sentence → `RajuTurn(text, source model/bank)` | `setu/agents/classmate.py` `propose` (app uses `method="tool_history"` since 15 Nov; was `"tool"`) | model client, leak filter | Drafts a different sentence, or the correct one; falls back to the bank | `test_agents.py` (21), `tests/db/test_agents_app.py` |
| Tool envelope | DET | Run a model-requested check; refuse everything else | JSON reply → result dict or exact `ERROR ...` string | `setu/agents/tools.py` `handle_reply` (3 read-only tools) | leak filter | No write tool exists, so an "unsafe" call can only be refused | `test_leakfilter_and_tools.py`, `test_tool_eval.py`, 17 frozen attacks |
| Coach (दीदी) | LLM | One Hindi hint after a first miss | rule title + Raju's sentence → `CoachHint(text, source model/approved/generic)` | `setu/agents/coach.py` `hint` (research: `hint_with_mode`) | leak filter `check_hint` | Hint in Telugu or with the answer is rejected; generic hint shown (59% fallback in task 6) | `test_agents.py`, `test_coach_rag.py` (32) |
| Native friend (रवि) | LLM | Pick among approved scene lines | approved line + variants → index | `setu/agents/friend.py` `ModelPicker`, `choose_line` | bank | Anything not exactly an approved form is dropped | `test_friend.py`, `tests/db/test_scenes.py` |
| Retrieval | DET | Find the rule a mistake belongs to (research only) | Raju sentence + learner attempt → top-3 rules by BM25 over character n-grams | `setu/agents/retrieval.py` `Retriever.search` | 25 rule files | Right rule first in 16 of 29 cases | `test_coach_rag.py`, `test_rag_eval.py` |
| Model client | plumbing | One OpenAI-compatible chat call, local endpoints by default | messages → `Completion(text, latency, tokens, error)` | `setu/agents/llm.py` `OpenAICompatible`, `MockProvider` (tests only) | `httpx` | Any error returns `ok=False`; callers fall back | `test_agents.py`, `test_credentials.py` |
| Teacher console | people | Review content, settle `unsure` answers, promote rules | signed decision → `apply_resolution` | `setu/web/routes_teacher.py`, `setu/store/resolution.py`, `content_review.py`, `rule_promotion.py` | resolution key | – | `tests/db/test_teacher_*.py`, `test_rule_review.py` |
| Database | state | Everything that persists | – | `setu/store/models.py`, `migrations/versions/0001`–`0015` | Postgres 16 | Triggers refuse classmate changes without evidence and edits to the ledger | `tests/db/test_migrations.py`, `test_constraints.py` |

### The fifteen questions

1. **Problem.** Hindi speakers learning Telugu carry over Hindi habits (a question word at the start, a separate
   negative word, `है` where Telugu has no copula). General apps do not target these.
2. **Why reverse learning is a hypothesis worth testing.** People work harder for an agent they think they are
   teaching (the protégé effect), and explaining someone else's error can expose a rule. The evidence for learning
   from erroneous examples is weak on average (g = 0.136), so it is a hypothesis, not a known benefit.
3. **Why Hindi → Telugu.** The scripts line up almost letter for letter and many Sanskrit words are shared, so a
   Hindi speaker starts with real advantages; the grammars differ in specific, listable ways; and the team found no
   learner-error corpus for this pair.
4. **Why Raju.** He gives the learner something to correct. His knowledge is rows in `classmate_rule_state`
   (unknown / taught / forgotten), so he can be kept one step behind the learner.
5. **Interaction.** At `/learn/rules` the learner sees "राजू ने लिखा: …" and either presses "ये वाक्य सही है" or
   types the corrected sentence (free typing or the on-screen Telugu keyboard).
6. **How Raju's mistakes are made.** The bank holds a wrong sentence for each item. With no model configured the app
   shows it. With a model, `classmate.propose` asks for a sentence with that mistake and shows the model's version
   only if `leakfilter.check_sentence` returns no reasons.
7. **What makes a mistake valid.** In a planted turn the sentence must equal the item's `wrong_form` or fully match
   an approved `wrong_pattern`, use only seen words, be one sentence in Telugu script, and not look like an assistant
   or a teacher. In practice that is an exact match with the bank for 43 of 49 items.
8. **When generated text fails.** The model's own draft and the filter's reasons go back to the model (up to 3 drafts;
   before 15 Nov only the reasons), then the bank sentence is shown.
   Every draft is logged in `model_call` with why it was rejected.
9. **How the learner's knowledge changes.** Only through `OutcomeWriter.record_verdict`: the verdict row, a skill
   evidence row, the mastery tracker, the FSRS card. `unsure` changes nothing and opens a teacher queue item.
10. **Coach.** After the first wrong or partial answer, `coach.hint` may write one Hindi hint; it is shown only if it
    has no answer word, no Telugu and no Latin. Otherwise an approved hint or a generic line is shown.
11. **Native friend.** In L5 scenes a model may only choose among approved lines; `friend.choose_line` shows an
    exact approved form whatever the model returns.
12. **Progression.** L0 letters, L1 syllables, L2 words, L3 phrases, L4 rules (Raju appears after three ready rules),
    L5 scenes. A skill is learned after 3 cue-free successes on 2 items, 2 task types and 2 days, with the tracker's
    lower bound at 0.6 or more (`scheduler.UNLOCK`). A placement test can skip early levels.
13. **Retrieval, memory, spacing.** Retrieval exists only in the research coach. FSRS schedules letters, syllables,
    words and chunks. A Beta tracker with a half-life estimates recall of each rule; when it drops below 0.5 at the
    start of a session, `forget_due` makes Raju forget that rule so it is planted again.
14. **Database state.** `session` → `exchange` → `attempt` → `verdict`, plus `learner_skill_state`,
    `skill_evidence`, `learner_lexeme_card`, `fsrs_review_log`, `classmate_rule_state`, `teacher_queue_item`,
    `model_call` and the append-only `event_ledger`.
15. **Unsafe or wrong agent action.** There is nothing an agent can do except return text. A tool call to an unknown
    tool returns `ERROR unknown_tool`; text that fails a gate is replaced; a provider error falls back to the bank.

## 4. One real episode, traced

Run on 15 Nov 2026 against a copy of the demo database (`setu_audit_demo`), learner `8666-7115`, once without a model
and once with `gemini-3.5-flash`. The rows are copied from the database after each step.

```
GET /learn/rules                        routes_rules.rules_page
  forget_due(...)                       DET  scheduler: does Raju forget anything? (start of a session only)
  _new_session → planner.plan_session   DET  turns = [[planted, HI-TE-902], ...]; seed stored in session
  _next_turn → exchange.pick_item       DET  item HI-TE-902-b, never the sentence used last time
  _raju(...)
    classmate.propose(method="tool")    LLM  prompt: Hindi meaning, rule title, allowed words, last wrong sentence
      leakfilter.check_sentence(draft)  DET  reasons ↔ pass
    → shown text + source               DET  model sentence if it passed, else the bank sentence
  INSERT exchange, INSERT model_call    DB
POST /learn/rules/answer  typed=...     routes_rules.rules_answer
  checker.check_fix(raw, ItemKey)       DET  normalise_answer → _classify → Verdict
  INSERT attempt                        DB   raw text, script, cue level, idempotency key
  writer.record_verdict(verdict, skill) DET  verdict, skill_evidence, tracker, ledger; teaches Raju if earned
  exchange.step(...)                    DET  next step: hint / copy / why / close
  (hint step) coach.hint(...)           LLM  shown only if leakfilter.check_hint passes
```

**Exchange A, with the model. Raju's turn fell back to the bank.**

| Step | What happened | Recorded |
|---|---|---|
| Raju drafts | Model wrote `అతను నహీ రాడు` three times; the bank sentence is `అతను నహీ వస్తాడు` | 3 `model_call` rows, each `rejected: NOT_ONE_ERROR`, 142+13, 166+13, 166+13 tokens |
| Shown | Bank sentence `అతను నహీ వస్తాడు` | `exchange.source = bank`, `task.raju.drafts = 3` |
| Answer 1 | Learner submits Raju's sentence unchanged | `attempt n=1, cue_level 0` → verdict `wrong / planted_error_unchanged`, `checker-1` |
| Hint | Coach model replied in Telugu inside a code fence | `model_call` `rejected: NOT_HINDI, TELUGU_IN_HINT`; generic hint shown: "जिस हिस्से में हिंदी की आदत दिख रही है, उसे फिर से देखिए।" |
| Answer 2 | Unchanged again | `attempt n=2, cue_level 1, hint_type generic` → `wrong` |
| Copy | Correct sentence shown; learner types `అతను రాడు` | `attempt n=3, cue_level 2, after_reveal true` → `correct / accepted_form`, but no skill evidence and Raju is not taught |

**Exchange B. One draft passed, the learner fixed it first time.**

| Step | What happened | Recorded |
|---|---|---|
| Raju drafts | Model wrote `నేను నహీ వెళ్తాను`, equal to the bank sentence | 1 `model_call`, no error, 146+14 tokens; `exchange.source = model` |
| Answer 1 | Learner types `నేను వెళ్ళను` | verdict `correct / accepted_form`; `skill_updated`; `classmate_taught` in the ledger; `classmate_rule_state (HI-TE-902, taught, 1)` |

**Exchange C. An answer the checker cannot read.**

| Step | What happened | Recorded |
|---|---|---|
| Answer 1 | Learner types `nuvvu vastaava` (Latin letters) | verdict `unsure / input_needs_transliteration`; nothing else changes; one open `teacher_queue_item` |
| Teacher | Sees it at `/teacher/queue` with सही / आंशिक / गलत buttons | a signed resolution would go through `OutcomeWriter.apply_resolution` |

What the trace shows about the model's role:

- The model's three rejected drafts in Exchange A are a plausible different sentence with the same Hindi negator. The
  filter cannot tell whether it is a good planted error, so it rejects it.
- The app's retry loop sent back only the code `NOT_ONE_ERROR`, without the model's own draft, and got the same
  sentence three times. That is the confound tested in `reports/generation_ablation.md`.
- When the model does pass (Exchange B) the learner sees exactly the bank sentence. In the shipped planted turn the
  model therefore adds no text the bank did not already have.

## 5. Where a model is involved, and where it is not

| Step | Model? | In the shipped app? |
|---|---|---|
| Choosing the rule, item and turn type | no | yes |
| Writing Raju's sentence | yes, proposal only (`method="tool_history"`: harness runs the check, model sees its draft) | yes, if `SETU_LLM_URL` is set |
| Deciding whether to call a check tool (`agentic_tools`) | yes | **no, research only** |
| Checking Raju's sentence | no | yes |
| Marking the learner's answer | no | yes |
| Writing the hint | yes, proposal only (rule title + Raju's sentence, no retrieval) | yes, if a model is set |
| Retrieval for the hint (RAG) | no model in retrieval; model writes the hint | **no, research only** |
| Picking a scene line | yes, among approved lines | yes, if a model is set |
| Updating mastery, Raju's knowledge, schedules | no | yes |
| Diagnosing the error step by step, LLM judge, single-agent baseline | yes | **no, research only** |

With no model configured, which is the default and what CI tests, the whole app runs on bank text.

## 6. Diagrams

Both are generated from the code's real module names by `python -m scripts.make_figures`:

- `docs/submission/figures/fig1_architecture.pdf`: components, who proposes, who decides, the authority boundary.
- `docs/submission/figures/fig2_raju_loop.pdf`: Raju's generation loop with the measured fallback rates.
