"""L0 script orientation and letter practice (slice S1). Every answer goes through the checker and the
OutcomeWriter; the page only shows approved letters (`learner_letter`) and keeps the pending task on the server, so
a learner cannot re-roll a task (E-13)."""
import datetime as dt
import json
import random
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import text

from setu.domain import checker
from setu.domain import letter_practice as LP
from setu.store.outcome_writer import CardTarget, SkillTarget

from .routes_ui import form_data, optional_user, render

router = APIRouter()
SESSION_CONFIG = {"activity": "letters", "planner": "letter-practice-1", "new_cap": 5}


def _letters(c) -> list[LP.LetterView]:
    rows = c.execute(text("SELECT id, telugu, devanagari, twin_label_hi, letter_group, varnamala_order "
                          "FROM learner_letter ORDER BY varnamala_order")).all()
    return [LP.LetterView(r.id, r.telugu, r.devanagari, r.twin_label_hi, r.letter_group, r.varnamala_order)
            for r in rows]


def _session(c, learner_id) -> tuple:
    today = dt.datetime.now(dt.UTC).date()
    row = c.execute(text("SELECT id, seed FROM session WHERE learner_id = :l AND mode = 'learn' AND ended_at IS NULL "
                         "AND config_snapshot->>'activity' = 'letters' AND started_at::date = :d "
                         "ORDER BY started_at DESC LIMIT 1"), {"l": learner_id, "d": today}).first()
    if row:
        return row.id, row.seed
    seed = random.SystemRandom().randrange(2**31)
    sid = c.execute(text("INSERT INTO session (learner_id, mode, config_snapshot, seed) VALUES (:l, 'learn', "
                         "CAST(:cfg AS jsonb), :s) RETURNING id"),
                    {"l": learner_id, "cfg": json.dumps(SESSION_CONFIG), "s": seed}).scalar_one()
    return sid, seed


def _last_exchange(c, learner_id):
    return c.execute(text(
        "SELECT e.id, e.task, a.id AS attempt_id, v.outcome FROM exchange e JOIN session s ON s.id = e.session_id "
        "LEFT JOIN attempt a ON a.exchange_id = e.id LEFT JOIN verdict v ON v.attempt_id = a.id "
        "WHERE s.learner_id = :l AND e.task->>'activity' = 'letters' ORDER BY e.created_at DESC LIMIT 1"),
        {"l": learner_id}).first()


def _task(task_json) -> LP.Task:
    return LP.Task(task_json["type"], task_json["letter_id"], tuple(task_json.get("options", ())),
                   tuple(task_json.get("chain", ())), bool(task_json.get("revealed")))


def _create_exchange(c, session_id, task: LP.Task) -> uuid.UUID:
    payload = {"activity": "letters", "type": task.type, "letter_id": task.letter_id, "options": list(task.options),
               "chain": list(task.chain), "revealed": task.revealed}
    kind = "learn" if task.type == "intro" else "review"
    return c.execute(text("INSERT INTO exchange (session_id, kind, source, task) VALUES (:s, :k, 'bank', "
                          "CAST(:t AS jsonb)) RETURNING id"),
                     {"s": session_id, "k": kind, "t": json.dumps(payload, ensure_ascii=False)}).scalar_one()


def _page(request, user, exchange_id, task: LP.Task, letters):
    by_id = {x.id: x for x in letters}
    letter = by_id[task.letter_id]
    telugu_keys = [x.telugu for x in letters]
    deva_keys = list(dict.fromkeys(x.devanagari for x in letters))
    return render(request, f"learner/letter_{task.type}.html", title_key="page.letters", user=user,
                  exchange_id=exchange_id, letter=letter, options=[by_id[o] for o in task.options if o in by_id],
                  telugu_keys=telugu_keys, deva_keys=deva_keys)


@router.get("/learn", response_class=HTMLResponse)
def learn_home(request: Request):
    user = optional_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    with request.app.state.db.tx() as c:
        letters = _letters(c)
    if not letters:
        return render(request, "learner/message.html", title_key="page.letters", user=user,
                      message_key="learn.not_ready")
    return render(request, "learner/script_intro.html", title_key="page.letters", user=user)


@router.get("/learn/letters", response_class=HTMLResponse)
def letter_task(request: Request):
    user = optional_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    now = dt.datetime.now(dt.UTC)
    with request.app.state.db.tx() as c:
        letters = _letters(c)
        if not letters:
            return render(request, "learner/message.html", title_key="page.letters", user=user,
                          message_key="learn.not_ready")
        last = _last_exchange(c, user.learner_id)
        if last is not None and last.attempt_id is None:  # still open: show the same task again (no re-roll)
            return _page(request, user, last.id, _task(last.task), letters)
        pending = None
        if last is not None:
            pending = LP.after_answer(_task(last.task), last.outcome or "correct")
        cards = [LP.CardView(r.card_ref, r.modality, r.due) for r in c.execute(text(
            "SELECT card_ref, modality, due FROM learner_lexeme_card WHERE learner_id = :l AND card_kind = 'letter'"),
            {"l": user.learner_id})]
        new_today = c.execute(text(
            "SELECT count(*) FROM exchange e JOIN session s ON s.id = e.session_id WHERE s.learner_id = :l "
            "AND e.task->>'activity' = 'letters' AND e.task->>'type' = 'intro' AND e.created_at::date = :d"),
            {"l": user.learner_id, "d": now.date()}).scalar_one()
        session_id, seed = _session(c, user.learner_id)
        task = LP.next_task(letters=letters, cards=cards, pending=pending, now=now, new_today=new_today,
                            seed=seed, new_cap=SESSION_CONFIG["new_cap"])
        if task is None:
            return render(request, "learner/message.html", title_key="page.letters", user=user,
                          message_key="learn.done_today")
        exchange_id = _create_exchange(c, session_id, task)
    return _page(request, user, exchange_id, task, letters)


@router.post("/learn/letters/continue")
async def letter_continue(request: Request):
    """The intro card has no answer: moving on creates the next step of the chain without any attempt or verdict."""
    user = optional_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    data = await form_data(request)
    with request.app.state.db.tx() as c:
        last = _last_exchange(c, user.learner_id)
        if last is None or str(last.id) != str(data.get("exchange_id")) or last.task["type"] != "intro":
            return RedirectResponse("/learn/letters", status_code=303)
        letters = _letters(c)
        session_id, seed = _session(c, user.learner_id)
        task = LP.next_task(letters=letters, cards=[], pending=_task(last.task), now=dt.datetime.now(dt.UTC),
                            new_today=0, seed=seed)
        if task is not None:
            _create_exchange(c, session_id, task)
    return RedirectResponse("/learn/letters", status_code=303)


@router.post("/learn/letters/answer", response_class=HTMLResponse)
async def letter_answer(request: Request):
    user = optional_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    data = await form_data(request)
    try:
        exchange_id = uuid.UUID(str(data.get("exchange_id")))
    except ValueError:
        return RedirectResponse("/learn/letters", status_code=303)
    with request.app.state.db.tx() as c:
        row = c.execute(text(
            "SELECT e.id, e.task, a.id AS attempt_id FROM exchange e JOIN session s ON s.id = e.session_id "
            "LEFT JOIN attempt a ON a.exchange_id = e.id WHERE e.id = :e AND s.learner_id = :l"),
            {"e": exchange_id, "l": user.learner_id}).first()
        letters = {x.id: x for x in _letters(c)}
    if row is None or row.task is None or row.task["type"] == "intro" or row.task["letter_id"] not in letters:
        return RedirectResponse("/learn/letters", status_code=303)
    task, letter = _task(row.task), letters[row.task["letter_id"]]
    if row.attempt_id is not None:  # already answered: show the same feedback (idempotent)
        with request.app.state.db.tx() as c:
            outcome = c.execute(text("SELECT outcome FROM verdict WHERE attempt_id = :a"),
                                {"a": row.attempt_id}).scalar()
        return _feedback(request, user, letter, outcome)

    attempt_id = uuid.uuid4()
    if task.type == "choice":
        chosen = str(data.get("choice", ""))
        result = checker.check_choice(attempt_id=attempt_id, chosen=chosen, correct=letter.id)
        raw, mode, cue, aids, normalised = chosen, "multiple_choice", 1, ["choices"], None
    else:
        key, typed = str(data.get("key", "")), str(data.get("typed", ""))
        raw, mode = (key, "onscreen_keyboard") if key else (typed[:40], "typed")
        target, accepted = ("devanagari", [letter.devanagari]) if task.type == "recognise" else ("telugu", [letter.telugu])
        result = checker.check_recall(attempt_id=attempt_id, raw=raw, accepted=accepted, target_script=target,
                                      response_mode=mode, closed=True)
        cue, aids, normalised = 0, [], result.normalised
    with request.app.state.db.tx() as c:
        inserted = c.execute(text(
            "INSERT INTO attempt (id, exchange_id, n, raw_text, normalised_text, input_script, response_mode, "
            "cue_level, assistance, after_reveal, idempotency_key) VALUES (:id, :e, 1, :raw, :norm, :script, :mode, "
            ":cue, CAST(:aids AS jsonb), :ar, :k) ON CONFLICT (idempotency_key) DO NOTHING RETURNING id"),
            {"id": attempt_id, "e": exchange_id, "raw": raw, "norm": normalised.text if normalised else None,
             "script": normalised.input_script if normalised else None, "mode": mode, "cue": cue,
             "aids": json.dumps(aids), "ar": task.revealed, "k": f"{exchange_id}:1"}).scalar()
    if inserted is None:  # a concurrent duplicate submission: show its feedback
        return RedirectResponse("/learn/letters", status_code=303)
    modality = LP.MODALITY[task.type]
    request.app.state.writer.record_verdict(
        result.verdict, card=CardTarget("letter", letter.id, modality),
        skill=SkillTarget(f"L0.script.{letter.group}.{modality}", "L0", item_ref=letter.id, task_type=task.type))
    return _feedback(request, user, letter, result.verdict.outcome)


def _feedback(request, user, letter, outcome):
    key = {"correct": "fb.correct", "unsure": "fb.unsure"}.get(outcome, "fb.wrong")
    return render(request, "learner/letter_feedback.html", title_key="page.letters", user=user, letter=letter,
                  outcome_key=key, correct=outcome == "correct")
