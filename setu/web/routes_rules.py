"""L4 correction exchanges with the mock classmate (slice S5; P-SESS-*, F-EXCH, F-COACH, F-OWN, P8b-02).

A session is planned once by the planner (seeded; the plan and config are stored in the session) and played turn
by turn. The classmate is a mock: it shows the bank's planted sentence (or, on a no-error turn, the correct
sentence) and only fixed Hindi templates around it; no model is called. Until the learner is ready on
`classmate_start_min_rules` rules every turn is an own sentence: a new rule is introduced with its Hindi
explanation and the learner writes a sentence for one of its items' Hindi meanings.

Every answer goes through the checker and the OutcomeWriter. Hints are teacher-approved hints that pass
`check_hint_has_no_answer` again when served, or the generic template. A hinted answer (cue 1) or the copy after a
reveal is never mastery evidence and never teaches the classmate (the writer and the database both refuse). Only
approved content is used (`learner_rule_version`, `learner_item_version`, practice pool only).
"""
import dataclasses
import json
import os
import random
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import text

from setu.agents import classmate, coach
from setu.domain import checker, leakfilter, planner
from setu.domain import exchange as X
from setu.domain.tokenize import tokens
from setu.store.outcome_writer import SkillTarget
from setu.store.scheduling import forget_due

from .routes_learn import TELUGU_SIGNS
from .routes_ui import form_data, optional_user, render

router = APIRouter()
NAME, PATH, LEARNER_BAND = "rules", "/learn/rules", "L4"
MAX_LEN, MAX_EXPLANATION = 60, 300


@dataclasses.dataclass(frozen=True)
class Board:
    """What the shared on-screen keyboard needs."""
    path: str = PATH
    compose: bool = True
    max_len: int = MAX_LEN


BOARD = Board()

_RULES = """
SELECT rv.id AS rv_id, rv.rule_id, rv.band, rv.title_hi, rv.l1_explanation_hi, rv.concept_key, rv.target_skill_id,
       coalesce(cs.state, 'unknown') AS classmate_state, coalesce(st.cuefree_successes, 0) > 0 AS ready,
       EXISTS (SELECT 1 FROM exchange e JOIN session s ON s.id = e.session_id JOIN rule_version x
               ON x.id = e.rule_version_id WHERE s.learner_id = :l AND x.rule_id = rv.rule_id) AS seen,
       (SELECT count(*) FROM skill_evidence ev WHERE ev.learner_id = :l AND ev.skill_id = rv.target_skill_id
         AND ev.outcome <> 'correct') AS errors,
       (SELECT count(*) FROM skill_evidence ev WHERE ev.learner_id = :l AND ev.skill_id = rv.target_skill_id)
         AS opportunities
  FROM learner_rule_version rv JOIN rule r ON r.id = rv.rule_id AND r.direction = 'HI->TE'
  LEFT JOIN classmate_rule_state cs ON cs.learner_id = :l AND cs.rule_id = rv.rule_id
  LEFT JOIN learner_skill_state st ON st.learner_id = :l AND st.skill_id = rv.target_skill_id
 WHERE rv.target_skill_id IS NOT NULL ORDER BY rv.rule_id"""

_ITEMS = """
SELECT iv.id, i.id AS item_id, i.rule_id, iv.hindi_meaning, iv.wrong_form, iv.correct_form, iv.no_error_equivalent,
       iv.accept_patterns, iv.wrong_patterns,
       coalesce((SELECT array_agg(av.form ORDER BY av.form) FROM learner_accepted_variant av
                  WHERE av.item_version_id = iv.id), '{}') AS variants
  FROM learner_item_version iv JOIN item i ON i.id = iv.item_id
 WHERE iv.pool = 'practice' AND iv.wrong_form IS NOT NULL AND iv.hindi_meaning IS NOT NULL ORDER BY i.id"""


def _bank(c, learner_id):
    items = {r.id: r for r in c.execute(text(_ITEMS))}
    with_items = {r.rule_id for r in items.values()}
    rules = {r.rule_id: r for r in c.execute(text(_RULES), {"l": learner_id}) if r.rule_id in with_items}
    return rules, {k: v for k, v in items.items() if v.rule_id in rules}


def _key(item, items) -> checker.ItemKey:
    others = {r.item_id: [r.correct_form] for r in items.values() if r.id != item.id}
    return checker.ItemKey(item_id=item.item_id, target_script="telugu", correct_form=item.correct_form,
                           accepted_forms=tuple(item.variants), wrong_form=item.wrong_form,
                           accept_patterns=tuple(item.accept_patterns), wrong_patterns=tuple(item.wrong_patterns),
                           other_items=others)


def _plan(rules, seed) -> planner.Plan:
    views = [planner.RuleView(r.rule_id, r.band, r.ready, r.classmate_state, True, r.errors, r.opportunities)
             for r in rules.values()]
    # X-CLS-START is an experimental parameter; SETU_CLASSMATE_START_MIN_RULES may lower it (demos); it is recorded
    # in the session's config snapshot like every other planner setting.
    start = int(os.environ.get("SETU_CLASSMATE_START_MIN_RULES", planner.Config().classmate_start_min_rules))
    return planner.plan_session(rules=views, learner_band=LEARNER_BAND, seed=seed,
                                config=planner.Config(classmate_start_min_rules=start))


def _open_session(c, learner_id):
    return c.execute(text("SELECT id, seed, config_snapshot FROM session WHERE learner_id = :l AND mode = 'learn' "
                          "AND ended_at IS NULL AND config_snapshot->>'activity' = :a ORDER BY started_at DESC "
                          "LIMIT 1"), {"l": learner_id, "a": NAME}).first()


def _new_session(c, learner_id, rules):
    seed = random.SystemRandom().randrange(2**31)
    plan = _plan(rules, seed)
    cfg = {"activity": NAME, "planner": plan.planner_version, "exchange": X.VERSION,
           "config": dataclasses.asdict(plan.config), "classmate_active": plan.classmate_active,
           "turns": [[t.kind, t.rule_id] for t in plan.turns]}
    sid = c.execute(text("INSERT INTO session (learner_id, mode, config_snapshot, seed) VALUES (:l, 'learn', "
                         "CAST(:cfg AS jsonb), :s) RETURNING id"),
                    {"l": learner_id, "cfg": json.dumps(cfg), "s": seed}).scalar_one()
    return c.execute(text("SELECT id, seed, config_snapshot FROM session WHERE id = :s"), {"s": sid}).first()


_EXCHANGE = ("SELECT e.id, e.kind, e.task, e.session_id, e.item_version_id, e.shown_text, rv.rule_id "
             "FROM exchange e JOIN session s ON s.id = e.session_id LEFT JOIN rule_version rv "
             "ON rv.id = e.rule_version_id WHERE s.learner_id = :l AND e.task->>'activity' = :a ")


def _last(c, learner_id):
    return c.execute(text(_EXCHANGE + "ORDER BY e.created_at DESC LIMIT 1"), {"l": learner_id, "a": NAME}).first()


def _answers(c, exchange_id) -> list[X.Answer]:
    return [X.Answer(r.n, r.kind, r.outcome) for r in c.execute(text(
        "SELECT a.n, v.kind, v.outcome FROM attempt a JOIN verdict v ON v.attempt_id = a.id WHERE a.exchange_id = :e "
        "ORDER BY a.n"), {"e": exchange_id})]


def _why_due(c, learner_id) -> bool:
    n = c.execute(text(
        "SELECT count(*) FROM verdict v JOIN attempt a ON a.id = v.attempt_id JOIN exchange e ON e.id = a.exchange_id "
        "JOIN session s ON s.id = e.session_id WHERE s.learner_id = :l AND v.kind = 'fix' AND v.outcome = 'correct' "
        "AND a.cue_level = 0 AND NOT a.after_reveal AND e.planted"), {"l": learner_id}).scalar_one()
    return X.asks_why(n)


def _turn_kind(row) -> str:
    return row.task["turn_kind"]


def _state(c, learner_id, row) -> X.Step:
    if row.task.get("step") == "intro":
        return X.Step("intro")
    answers = _answers(c, row.id)
    last = answers[-1] if answers else None
    due = bool(last and last.kind == "fix" and last.n == 1 and last.outcome == "correct" and _why_due(c, learner_id))
    return X.step(_turn_kind(row), answers, why_due=due)


def log_call(c, exchange_id, agent: str, completion, *, rejected=()):
    """One `model_call` row: model, prompt version, request hash, reply, latency, and why it was not used."""
    if completion is None:
        return
    err = completion.error or (("rejected: " + ", ".join(rejected)) if rejected else None)
    c.execute(text("INSERT INTO model_call (exchange_id, agent, model, prompt_version, request_hash, response_text, "
                   "latency_ms, error, prompt_tokens, completion_tokens) VALUES (:e, :a, :m, :pv, :h, :t, :ms, :err, "
                   ":pt, :ct)"),
              {"e": exchange_id, "a": agent, "m": completion.model, "pv": classmate.VERSION,
               "h": completion.request_hash or "-", "t": completion.text, "ms": completion.latency_ms, "err": err,
               "pt": completion.prompt_tokens, "ct": completion.completion_tokens})


def _raju(c, provider, learner_id, turn_kind, rule, item, rules, items):
    """The model proposes Raju's sentence; the leak filter decides; the bank sentence is the fallback."""
    bank = item.wrong_form if turn_kind == "planted" else (item.no_error_equivalent or item.correct_form)
    if provider is None:
        return bank, "bank", None
    seen = set(c.execute(text("SELECT form FROM classmate_vl WHERE learner_id = :l"), {"l": learner_id}).scalars())
    seen |= set(tokens(item.wrong_form or "")) | set(tokens(item.correct_form)) | {
        w for v in item.variants for w in tokens(v)}
    unknown = {i.item_id: _key(i, items) for i in items.values() if i.rule_id != rule.rule_id
               and rules[i.rule_id].classmate_state != "taught"}
    ctx = leakfilter.Context(item=_key(item, items), turn=turn_kind, seen_words=frozenset(seen),
                             unknown_rule_items=unknown)
    turn = classmate.propose(provider, ctx, rule_title=rule.title_hi or "", hindi_meaning=item.hindi_meaning,
                             bank_sentence=bank, method="tool")
    return turn.text, turn.source, turn


def _create(c, session, turn: int, turn_kind: str, rule, item=None, *, intro=False, replant=False, provider=None,
            learner_id=None, rules=None, items=None):
    task = {"activity": NAME, "turn": turn, "turn_kind": turn_kind, "step": "intro" if intro else "exchange",
            "replant": replant}
    generated = None
    if intro:
        kind, planted, shown = "learn", None, None
    elif turn_kind in ("planted", "no_error"):
        kind, planted = ("correction", True) if turn_kind == "planted" else ("no_error", False)
        shown, source, generated = _raju(c, provider, learner_id, turn_kind, rule, item, rules or {}, items or {})
        task["raju"] = {"source": source, "drafts": len(generated.drafts) if generated else 0}
    else:
        kind, planted, shown = "own", None, item.hindi_meaning
    eid = c.execute(text(
        "INSERT INTO exchange (session_id, kind, rule_version_id, item_version_id, planted, shown_text, source, task) "
        "VALUES (:s, :k, :rv, :iv, :p, :t, :src, CAST(:task AS jsonb)) RETURNING id"),
        {"s": session.id, "k": kind, "rv": rule.rv_id, "iv": item.id if item else None, "p": planted, "t": shown,
         "src": task.get("raju", {}).get("source", "bank"), "task": json.dumps(task, ensure_ascii=False)}).scalar_one()
    for d in (generated.drafts if generated else ()):
        log_call(c, eid, "classmate", d.completion, rejected=d.reasons)
    return eid


def _last_item(c, learner_id, rule_id):
    return c.execute(text(
        "SELECT i.item_id FROM exchange e JOIN session s ON s.id = e.session_id JOIN item_version i "
        "ON i.id = e.item_version_id JOIN rule_version rv ON rv.id = e.rule_version_id WHERE s.learner_id = :l "
        "AND rv.rule_id = :r ORDER BY e.created_at DESC LIMIT 1"), {"l": learner_id, "r": rule_id}).scalar()


def _next_turn(c, learner_id, rules, items, provider=None):
    """Create the exchange for the next planned turn, or return None when the session's plan is used up."""
    session = _open_session(c, learner_id)
    if session is None:
        return None, False
    turns = session.config_snapshot["turns"]
    used = c.execute(text("SELECT coalesce(max((task->>'turn')::int) + 1, 0) AS pos, count(*) FILTER "
                          "(WHERE task->>'step' = 'intro') AS intros FROM exchange WHERE session_id = :s"),
                     {"s": session.id}).first()
    views = [X.ItemView(r.item_id, r.id, r.rule_id) for r in items.values()]
    for pos in range(used.pos, len(turns)):
        kind, rule_id = turns[pos]
        intro = False
        if kind == "own":
            choice = X.own_rule([X.OwnRule(r.rule_id, r.ready, r.seen) for r in rules.values()],
                                new_this_session=used.intros, seed=session.seed, turn=pos)
            if choice is None:
                continue
            rule_id, intro = choice
        if rule_id not in rules:
            continue
        rule = rules[rule_id]
        if intro:
            return _create(c, session, pos, kind, rule, intro=True), True
        item = X.pick_item(views, rule_id, last_item=_last_item(c, learner_id, rule_id), seed=session.seed, turn=pos,
                           fresh_only=kind == "planted")
        if item is None and kind == "planted":  # never re-plant the exact last sentence: own sentence instead
            kind = "own"
            item = X.pick_item(views, rule_id, last_item=None, seed=session.seed, turn=pos)
        if item is not None:
            replant = kind == "planted" and rule.classmate_state == "forgotten"
            return _create(c, session, pos, kind, rule, items[item.version_id], replant=replant, provider=provider,
                           learner_id=learner_id, rules=rules, items=items), True
    c.execute(text("UPDATE session SET ended_at = now() WHERE id = :s"), {"s": session.id})
    return None, True


def _keys(c):
    letters = c.execute(text("SELECT telugu FROM learner_letter WHERE kind IN ('vowel', 'consonant') "
                             "ORDER BY varnamala_order")).scalars().all()
    return (list(letters) + list(TELUGU_SIGNS) + [" "]) if letters else []


def _hint(c, row, rules, items, provider=None):
    """(hint_type, text): the coach model's hint if one passed the leak check for this exchange, else the approved
    hint, else the generic line (text None). The model is asked at most once per exchange."""
    hints = [(h.type, h.text_hi) for h in c.execute(text(
        "SELECT type, text_hi FROM learner_hint WHERE rule_version_id = :rv ORDER BY type, id"),
        {"rv": rules[row.rule_id].rv_id})]
    approved = X.choose_hint(hints, _key(items[row.item_version_id], items))
    if provider is None:
        return approved
    prior = c.execute(text("SELECT response_text, error FROM model_call WHERE exchange_id = :e AND agent = 'coach' "
                           "ORDER BY created_at DESC LIMIT 1"), {"e": row.id}).first()
    if prior is not None:
        return ("l1_rule", prior.response_text) if prior.error is None else approved
    h = coach.hint(provider, _key(items[row.item_version_id], items), rule_title=rules[row.rule_id].title_hi or "",
                   approved=approved, wrong_sentence=row.shown_text or "")
    if h.completion is not None:
        shown = h.completion if h.source != "model" else dataclasses.replace(h.completion, text=h.text)
        log_call(c, row.id, "coach", shown, rejected=h.rejected)
    return h.hint_type, h.text


def _position(c, row):
    session = c.execute(text("SELECT config_snapshot FROM session WHERE id = :s"), {"s": row.session_id}).scalar_one()
    return row.task["turn"] + 1, len(session["turns"])


def _render(request, user, c, row, step, rules, items, buffer=""):
    rule = rules[row.rule_id]
    n, total = _position(c, row)
    ctx = {"exchange_id": row.id, "rule": rule, "step": step, "turn_kind": _turn_kind(row), "n": n, "total": total,
           "step_n": n, "step_total": total,
           "act": BOARD, "buffer": buffer}
    if step.name == "intro":
        return render(request, "learner/rule_intro.html", title_key="page.rules", user=user, **ctx)
    item = items[row.item_version_id]
    hint = _hint(c, row, rules, items, _llm(request)) if step.name == "hint" else None
    return render(request, "learner/exchange.html", title_key="page.rules", user=user, item=item,
                  shown=row.shown_text, hint=hint, keys=_keys(c), replant=bool(row.task.get("replant")), **ctx)


def _llm(request):
    return getattr(request.app.state, "llm", None)


def _message(request, user, key, more=False):
    return render(request, "learner/message.html", title_key="page.rules", user=user, message_key=key,
                  more_path=PATH if more else None)


def _ready_bank(c, user):
    rules, items = _bank(c, user.learner_id)
    return (rules, items) if rules else (None, None)


@router.get(PATH, response_class=HTMLResponse)
def rules_page(request: Request):
    user = optional_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    with request.app.state.db.tx() as c:
        rules, items = _ready_bank(c, user)
        if rules is None:
            return _message(request, user, "raju.not_ready")
        last = _last(c, user.learner_id)
        if last is not None and last.rule_id in rules and (last.item_version_id in items or last.task["step"] == "intro"):
            step = _state(c, user.learner_id, last)
            if step.name != "close":  # still open: the same step again (no re-roll)
                return _render(request, user, c, last, step, rules, items)
        has_session = _open_session(c, user.learner_id) is not None
    if not has_session:
        forget_due(request.app.state.db.engine, request.app.state.writer, user.learner_id,
                   at=request.app.state.clock())  # P8b-01: only when a session starts, never mid-session
        with request.app.state.db.tx() as c:
            rules, items = _bank(c, user.learner_id)
            _new_session(c, user.learner_id, rules)
    with request.app.state.db.tx() as c:
        rules, items = _bank(c, user.learner_id)
        exchange_id, _ = _next_turn(c, user.learner_id, rules, items, _llm(request))
        if exchange_id is None:
            return _message(request, user, "raju.done", more=True)
        row = c.execute(text(_EXCHANGE + "AND e.id = :e"), {"l": user.learner_id, "a": NAME, "e": exchange_id}).first()
        return _render(request, user, c, row, _state(c, user.learner_id, row), rules, items)


def _owned(c, user, data):
    try:
        exchange_id = uuid.UUID(str(data.get("exchange_id")))
    except ValueError:
        return None
    return c.execute(text(_EXCHANGE + "AND e.id = :e"), {"l": user.learner_id, "a": NAME, "e": exchange_id}).first()


@router.post(PATH + "/continue")
async def rules_continue(request: Request):
    """After a new rule's intro card: the own-sentence exchange for the same turn and rule (no attempt, no verdict)."""
    user = optional_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    data = await form_data(request)
    with request.app.state.db.tx() as c:
        row, (rules, items) = _owned(c, user, data), _bank(c, user.learner_id)
        last = _last(c, user.learner_id)
        if row is None or last is None or last.id != row.id or row.task["step"] != "intro" or row.rule_id not in rules:
            return RedirectResponse(PATH, status_code=303)
        session = c.execute(text("SELECT id, seed FROM session WHERE id = :s"), {"s": row.session_id}).first()
        views = [X.ItemView(r.item_id, r.id, r.rule_id) for r in items.values()]
        item = X.pick_item(views, row.rule_id, last_item=None, seed=session.seed, turn=row.task["turn"])
        if item is not None:
            _create(c, session, row.task["turn"], "own", rules[row.rule_id], items[item.version_id])
    return RedirectResponse(PATH, status_code=303)


@router.post(PATH + "/key", response_class=HTMLResponse)
async def rules_key(request: Request):
    """One key on the compose keyboard: rebuilds the page with the sentence so far. Writes nothing."""
    user = optional_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    data = await form_data(request)
    with request.app.state.db.tx() as c:
        row, (rules, items) = _owned(c, user, data), _bank(c, user.learner_id)
        if row is None or row.rule_id not in rules or row.item_version_id not in items:
            return RedirectResponse(PATH, status_code=303)
        step = _state(c, user.learner_id, row)
        keys = _keys(c)
        if step.name not in ("answer", "hint", "copy"):
            return RedirectResponse(PATH, status_code=303)
        buffer = str(data.get("buffer", ""))[:MAX_LEN]
        if data.get("erase"):
            buffer = buffer[:-1]
        elif str(data.get("key", "")) in keys:
            buffer = (buffer + str(data["key"]))[:MAX_LEN]
        return _render(request, user, c, row, step, rules, items, buffer=buffer)


@router.post(PATH + "/answer", response_class=HTMLResponse)
async def rules_answer(request: Request):
    user = optional_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    data = await form_data(request)
    with request.app.state.db.tx() as c:
        row, (rules, items) = _owned(c, user, data), _bank(c, user.learner_id)
        if row is None or row.rule_id not in rules or row.item_version_id not in items:
            return RedirectResponse(PATH, status_code=303)
        step = _state(c, user.learner_id, row)
        if step.name not in ("answer", "hint", "copy", "why") or str(data.get("n")) != str(step.n):
            return RedirectResponse(PATH, status_code=303)  # stale or replayed form
        rule, item = rules[row.rule_id], items[row.item_version_id]
        hint_type = _hint(c, row, rules, items, _llm(request))[0] if step.name == "hint" else None
    turn_kind, attempt_id = _turn_kind(row), uuid.uuid4()
    key = _key(item, items)
    target = None
    if step.name == "why":
        raw = str(data.get("explanation", ""))[:MAX_EXPLANATION]
        result = checker.check_explanation(attempt_id=attempt_id, raw=raw, concept_key=rule.concept_key or {})
        mode, cue, aids = "typed", 0, []
    else:
        says_correct = bool(data.get("says_correct")) and turn_kind != "own"
        if data.get("built"):
            raw, mode = str(data.get("buffer", ""))[:MAX_LEN], "onscreen_keyboard"
        else:
            raw, mode = str(data.get("typed", ""))[:MAX_LEN], "typed"
        if says_correct:
            raw = ""
        cue, aids = {"answer": (0, []), "hint": (1, ["hint"]), "copy": (2, ["revealed_answer"])}[step.name]
        if turn_kind == "own":
            result = checker.check_own(attempt_id=attempt_id, raw=raw, item=key, response_mode=mode)
        else:
            result = checker.check_fix(attempt_id=attempt_id, raw=raw, item=key, response_mode=mode,
                                       no_error_turn=turn_kind == "no_error", says_correct=says_correct)
        if step.name != "copy":  # copying a revealed answer is never evidence (spec §3.1 step 5)
            target = SkillTarget(rule.target_skill_id, rule.band, item_ref=item.item_id,
                                 task_type={"planted": "fix"}.get(turn_kind, turn_kind),
                                 production=turn_kind != "no_error")
    n = result.normalised
    with request.app.state.db.tx() as c:
        inserted = c.execute(text(
            "INSERT INTO attempt (id, exchange_id, n, raw_text, normalised_text, input_script, forgiveness_applied, "
            "response_mode, cue_level, assistance, hint_type, after_reveal, idempotency_key) VALUES (:id, :e, :n, "
            ":raw, :norm, :script, CAST(:fg AS jsonb), :mode, :cue, CAST(:aids AS jsonb), :ht, :ar, :k) "
            "ON CONFLICT (idempotency_key) DO NOTHING RETURNING id"),
            {"id": attempt_id, "e": row.id, "n": step.n, "raw": raw,
             "norm": getattr(n, "text", None) if step.name != "why" else None,
             "script": getattr(n, "input_script", None) if step.name != "why" else None,
             "fg": json.dumps(list(result.forgiveness), ensure_ascii=False), "mode": mode, "cue": cue,
             "aids": json.dumps(aids), "ht": hint_type, "ar": step.revealed, "k": f"{row.id}:{step.n}"}).scalar()
    if inserted is None:  # a concurrent duplicate submission
        return RedirectResponse(PATH, status_code=303)
    request.app.state.writer.record_verdict(result.verdict, skill=target, at=request.app.state.clock())
    with request.app.state.db.tx() as c:
        answers = _answers(c, row.id)
        if _state(c, user.learner_id, row).name != "close":
            return RedirectResponse(PATH, status_code=303)
    scored = [a for a in answers if a.kind != "explanation"]
    outcome = scored[-1].outcome if scored else None
    # k = 1: a cue-free correct first fix of a planted sentence taught the classmate (the writer enforces it)
    taught = turn_kind == "planted" and scored[0].n == 1 and scored[0].outcome == "correct"
    with request.app.state.db.tx() as c:
        first = c.execute(text("SELECT a.raw_text, v.outcome FROM attempt a JOIN verdict v ON v.attempt_id = a.id "
                               "WHERE a.exchange_id = :e AND a.n = 1"), {"e": row.id}).first()
        state = c.execute(text("SELECT state FROM classmate_rule_state WHERE learner_id = :l AND rule_id = :r"),
                          {"l": user.learner_id, "r": row.rule_id}).scalar()
    return render(request, "learner/exchange_close.html", title_key="page.rules", user=user, item=item,
                  turn_kind=turn_kind, correct=outcome == "correct", taught=taught, act=BOARD, shown=row.shown_text,
                  first=first, state_key=f"raju.st.{state or 'unknown'}",
                  src_key="raju.src_model" if (row.task.get("raju") or {}).get("source") == "model" else "raju.src_bank",
                  outcome_key={"correct": "fb.correct", "unsure": "fb.unsure"}.get(outcome, "fb.wrong"))
