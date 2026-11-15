"""The match game (/learn/match): pair each Telugu word with its meaning, or with its picture.

A round holds four words the learner has already met (never a new word) and one shared list of answers. Each pair
is stored as its own exchange, answered through the same checker and OutcomeWriter as every other answer, so the
record stays one thing. Marking goes to the flash-card schedule only, with no skill evidence: a shared answer list
allows elimination, so the game helps remembering but does not count as proof of knowing (see setu/domain/matching.py).
The open round is kept on the server, so reloading the page does not re-roll it.
"""
import json
import random
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import text

from setu.domain import checker, matching
from setu.store.outcome_writer import CardTarget

from . import pictures
from .routes_learn import WORDS, _any_approved, _units
from .routes_ui import form_data, optional_user, render

router = APIRouter()
PATH = "/learn/match"


def _met_words(c, learner_id):
    """Approved words the learner has met (a card exists), with the earliest due time of their cards."""
    views, meta = _units(c, WORDS, learner_id)
    due = {r.card_ref: r.due for r in c.execute(text(
        "SELECT card_ref, min(due) AS due FROM learner_lexeme_card WHERE learner_id = :l AND card_kind = 'lexeme' "
        "GROUP BY card_ref"), {"l": learner_id})}
    words = [matching.Word(v.id, v.telugu, v.label, pictures.has_picture(v.telugu), due[v.id])
             for v in views if v.id in due]
    return words, meta


def _open_round(c, learner_id):
    """The newest round with no answers yet: its exchanges, oldest first."""
    rows = c.execute(text(
        "SELECT e.id, e.task FROM exchange e JOIN session s ON s.id = e.session_id LEFT JOIN attempt a ON "
        "a.exchange_id = e.id WHERE s.learner_id = :l AND e.task->>'activity' = 'match' AND a.id IS NULL "
        "AND e.created_at > now() - interval '1 day' ORDER BY e.created_at DESC, e.id"), {"l": learner_id}).all()
    if not rows:
        return []
    latest = rows[0].task["round"]
    return sorted((r for r in rows if r.task["round"] == latest), key=lambda r: r.task["slot"])


def _new_round(c, learner_id, words, now):
    seed = random.SystemRandom().randrange(2**31)
    chosen = matching.pick_round(words, now=now, seed=seed)
    if not chosen:
        return []
    mode, options, round_id = matching.round_mode(chosen, seed=seed), matching.option_order(chosen, seed=seed), uuid.uuid4()
    sid = c.execute(text("INSERT INTO session (learner_id, mode, config_snapshot, seed) VALUES (:l, 'learn', "
                         "CAST(:cfg AS jsonb), :s) RETURNING id"),
                    {"l": learner_id, "cfg": json.dumps({"activity": "match", "planner": "match-1"}),
                     "s": seed}).scalar_one()
    for slot, w in enumerate(chosen):
        task = {"activity": "match", "type": "match", "letter_id": w.id, "options": options, "mode": mode,
                "round": str(round_id), "slot": slot}
        c.execute(text("INSERT INTO exchange (session_id, kind, source, task) VALUES (:s, 'review', 'bank', "
                       "CAST(:t AS jsonb))"), {"s": sid, "t": json.dumps(task, ensure_ascii=False)})
    return _open_round(c, learner_id)


def _message(request, user, key):
    return render(request, "learner/message.html", title_key="match.title", user=user, message_key=key)


def _round_page(request, user, rows, meta, chosen=None, error_key=None):
    task = rows[0].task
    by_id = {r.task["letter_id"]: meta[r.task["letter_id"]] for r in rows}
    pairs = [(r.id, meta[r.task["letter_id"]]) for r in rows]
    options = [(i, by_id[i]) for i in task["options"]]
    return render(request, "learner/match.html", title_key="match.title", user=user, pairs=pairs, options=options,
                  mode=task["mode"], chosen=chosen or {}, error_key=error_key, lesson=True, nav="today")


@router.get(PATH, response_class=HTMLResponse)
def match_page(request: Request):
    user = optional_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    now = request.app.state.clock()
    with request.app.state.db.tx() as c:
        if not _any_approved(c, WORDS):
            return _message(request, user, "learn.not_ready")
        words, meta = _met_words(c, user.learner_id)
        rows = _open_round(c, user.learner_id) or _new_round(c, user.learner_id, words, now)
        if not rows:
            return _message(request, user, "match.need_words")
        return _round_page(request, user, rows, meta)


@router.post(PATH + "/answer", response_class=HTMLResponse)
async def match_answer(request: Request):
    user = optional_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    data = await form_data(request)
    with request.app.state.db.tx() as c:
        rows = _open_round(c, user.learner_id)
        _, meta = _units(c, WORDS, user.learner_id)
    if not rows or any(r.task["letter_id"] not in meta for r in rows):
        return RedirectResponse(PATH, status_code=303)
    chosen = {str(r.id): str(data.get(f"pair_{r.id}", "")) for r in rows}
    valid = set(rows[0].task["options"])
    if any(v not in valid for v in chosen.values()):  # a pair left open (or a value that is not in the list)
        return _round_page(request, user, rows, meta, {k: v for k, v in chosen.items() if v in valid},
                           error_key="match.answer_all")
    results = []
    for r in rows:
        unit, attempt_id = meta[r.task["letter_id"]], uuid.uuid4()
        pick = chosen[str(r.id)]
        result = checker.check_choice(attempt_id=attempt_id, chosen=pick, correct=unit.id)
        with request.app.state.db.tx() as c:
            inserted = c.execute(text(
                "INSERT INTO attempt (id, exchange_id, n, raw_text, response_mode, cue_level, assistance, after_reveal, "
                "idempotency_key) VALUES (:id, :e, 1, :raw, 'multiple_choice', 1, CAST(:aids AS jsonb), false, :k) "
                "ON CONFLICT (idempotency_key) DO NOTHING RETURNING id"),
                {"id": attempt_id, "e": r.id, "raw": pick,
                 "aids": json.dumps(["choices", "illustration"] if r.task["mode"] == "picture" else ["choices"]),
                 "k": f"{r.id}:1"}).scalar()
        if inserted is not None:  # card review only: no skill evidence from a game with a shared answer list
            request.app.state.writer.record_verdict(result.verdict, card=CardTarget("lexeme", unit.id, "REC"),
                                                    at=request.app.state.clock())
        results.append({"unit": unit, "ok": result.verdict.outcome == "correct", "pick": meta.get(pick)})
    right = sum(1 for x in results if x["ok"])
    return render(request, "learner/match_result.html", title_key="match.title", user=user, results=results,
                  right=right, total=len(results), tone=matching.summary([x["ok"] for x in results]),
                  mode=rows[0].task["mode"], lesson=True, nav="today")
