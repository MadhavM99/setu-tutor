"""L5 scenes with the native friend रवि (slice S8; F-SCENE, P-ARCH-08, X-ARCH-01, X-BEG-04, R-INPUT).

A scene is offered only when its script, its scene and every line are approved by two native speakers
(`learner_scene_script`) and the learner has mastered (or been placed on) its prerequisite skills. A run goes line
by line: the friend's approved line (chosen by `setu.agents.friend`, which never lets a model say anything else),
a comprehension question in Hindi (multiple choice: recognition only), then the learner's own Telugu reply (typed or
on the compose keyboard: cue-free production). Replies are accepted only in the approved forms or approved variants;
a near miss gets the line's approved Hindi hint, a second miss shows an approved reply to copy (not evidence), and
an unexpected reply gets a fixed Hindi fallback, goes to the teacher queue and the scene continues on its approved
path. Nothing here produces Telugu that is not in the bank.

Telemetry (`scene_event`): start, each line shown (source, rejected model proposals, out-of-band words, Hindi share),
hints, fallbacks, and completion with comprehension, independent and assisted production, vocabulary introduced and
recalled, and time on task. Learning state changes only through the checker and the OutcomeWriter.
"""
import dataclasses
import datetime as dt
import json
import random
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import text

from setu.agents import friend
from setu.content.importer import scene_skill_id
from setu.domain import checker
from setu.domain import exchange as X
from setu.domain.tokenize import tokens
from setu.store.outcome_writer import SkillTarget

from .routes_learn import TELUGU_SIGNS
from .routes_ui import form_data, optional_user, render

router = APIRouter()
ROOT = "/learn/scenes"
MAX_LEN = 60
MET = ("mastered", "placed")


@dataclasses.dataclass(frozen=True)
class Board:
    path: str
    compose: bool = True
    max_len: int = MAX_LEN


def _script(c, scene_id):
    return c.execute(text("SELECT sc.*, s.title_hi, s.setup_hi FROM learner_scene_script sc JOIN learner_scene s "
                          "ON s.id = sc.scene_id WHERE sc.scene_id = :s"), {"s": scene_id}).first()


def _lines(c, scene_id):
    return c.execute(text("SELECT * FROM learner_scene_line WHERE scene_id = :s ORDER BY n"), {"s": scene_id}).all()


def _variants(c, line_id):
    return c.execute(text("SELECT form FROM learner_scene_reply_variant WHERE line_id = :l ORDER BY form"),
                     {"l": line_id}).scalars().all()


def _missing(c, learner_id, script):
    """Prerequisite skills not yet mastered or placed, with a Hindi name for each."""
    out = []
    for skill_id in script.prerequisites:
        status = c.execute(text("SELECT status FROM learner_skill_state WHERE learner_id = :l AND skill_id = :s"),
                           {"l": learner_id, "s": skill_id}).scalar()
        if status in MET:
            continue
        name = c.execute(text("SELECT s.title_hi FROM skill k JOIN scene s ON s.id = k.target WHERE k.id = :k "
                              "AND k.family = 'chunk'"), {"k": skill_id}).scalar()
        out.append(name)
    return out


def _run(c, learner_id, scene_id):
    return c.execute(text("SELECT id, started_at, config_snapshot FROM session WHERE learner_id = :l AND mode = 'learn' "
                          "AND ended_at IS NULL AND config_snapshot->>'activity' = 'scene' AND "
                          "config_snapshot->>'scene_id' = :s ORDER BY started_at DESC LIMIT 1"),
                     {"l": learner_id, "s": scene_id}).first()


def _exchanges(c, session_id):
    return c.execute(text("SELECT id, task, shown_text FROM exchange WHERE session_id = :s ORDER BY created_at"),
                     {"s": session_id}).all()


def _answers(c, exchange_id):
    return [X.Answer(r.n, r.kind, r.outcome) for r in c.execute(text(
        "SELECT a.n, v.kind, v.outcome FROM attempt a JOIN verdict v ON v.attempt_id = a.id WHERE a.exchange_id = :e "
        "ORDER BY a.n"), {"e": exchange_id})]


def _event(c, session_id, scene_id, event, *, exchange_id=None, oov=(), hindi_share=None, data=None):
    c.execute(text("INSERT INTO scene_event (session_id, scene_id, exchange_id, event, oov_words, hindi_share, data) "
                   "VALUES (:s, :sc, :e, :ev, :oov, :hs, CAST(:d AS jsonb))"),
              {"s": session_id, "sc": scene_id, "e": exchange_id, "ev": event, "oov": list(oov), "hs": hindi_share,
               "d": json.dumps(data or {}, ensure_ascii=False)})


def _say(request, script, line):
    """The friend's line for this turn: always an approved form (a model may only pick one; see agents/friend)."""
    model = getattr(request.app.state, "friend_model", None)
    proposal = None
    if model is not None:
        try:
            proposal = model(line.telugu, {"scene_id": script.scene_id, "n": line.n})
        except Exception:  # noqa: BLE001 - any model failure falls back to the bank, like a rejected proposal
            proposal = ""
    words = set(script.vocab_required) | set(script.vocab_permitted)
    return friend.choose_line(friend.ApprovedLine(line.telugu), proposal, seen_words=set(), scene_words=words,
                              learner_band="L5")


def _create(c, request, run, script, line, step):
    task = {"activity": "scene", "scene_id": script.scene_id, "line": line.n, "step": step}
    said = _say(request, script, line) if step == "comprehend" else None
    shown = said.text if said else line.telugu
    eid = c.execute(text("INSERT INTO exchange (session_id, kind, source, shown_text, task) VALUES (:s, 'scene', :src, "
                         ":t, CAST(:task AS jsonb)) RETURNING id"),
                    {"s": run.id, "src": said.source if said else "bank", "t": shown,
                     "task": json.dumps(task)}).scalar_one()
    picker = getattr(request.app.state, "friend_model", None)
    if said and isinstance(picker, friend.ModelPicker) and picker.last is not None:
        from .routes_rules import log_call
        log_call(c, eid, "friend", picker.last, rejected=said.rejected)
    if said:
        _event(c, run.id, script.scene_id, "line_shown", exchange_id=eid, oov=said.out_of_band,
               hindi_share=said.hindi_share, data={"line": line.n, "source": said.source,
                                                   "rejected": list(said.rejected), "friend": said.version})
    return eid


def _state(c, request, run, script, lines):
    """(exchange row, line, step) for what the learner should see now, creating the next exchange if needed;
    (None, None, None) when every line is done."""
    rows = _exchanges(c, run.id)
    by_n = {x.n: x for x in lines}
    if rows:
        last = rows[-1]
        line = by_n[last.task["line"]]
        answers = _answers(c, last.id)
        if last.task["step"] == "comprehend":
            if not answers:
                return last, line, X.Step("answer", 1)
            if line.replies:
                return _reload(c, _create(c, request, run, script, line, "reply")), line, X.Step("answer", 1)
        else:
            step = X.step("own", answers, why_due=False)
            if step.name != "close":
                return last, line, step
        nxt = next((x for x in lines if x.n > line.n), None)
    else:
        nxt = lines[0]
    if nxt is None:
        return None, None, None
    return _reload(c, _create(c, request, run, script, nxt, "comprehend")), nxt, X.Step("answer", 1)


def _reload(c, eid):
    return c.execute(text("SELECT id, task, shown_text FROM exchange WHERE id = :e"), {"e": eid}).first()


def _keys(c):
    letters = c.execute(text("SELECT telugu FROM learner_letter WHERE kind IN ('vowel', 'consonant') "
                             "ORDER BY varnamala_order")).scalars().all()
    return (list(letters) + list(TELUGU_SIGNS) + [" "]) if letters else []


def _page(request, user, c, script, row, line, step, buffer=""):
    tpl = "learner/scene_comprehend.html" if row.task["step"] == "comprehend" else "learner/scene_reply.html"
    return render(request, tpl, title_key="page.scenes", user=user, script=script, line=line, step=step,
                  exchange_id=row.id, shown=row.shown_text, act=Board(f"{ROOT}/{script.scene_id}"), keys=_keys(c),
                  buffer=buffer, options=list(enumerate(line.options_hi or [])))


def _message(request, user, key):
    return render(request, "learner/message.html", title_key="page.scenes", user=user, message_key=key)


@router.get(ROOT, response_class=HTMLResponse)
def scenes(request: Request):
    user = optional_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    with request.app.state.db.tx() as c:
        rows = c.execute(text("SELECT sc.scene_id, s.title_hi, sc.prerequisites FROM learner_scene_script sc JOIN "
                              "learner_scene s ON s.id = sc.scene_id ORDER BY sc.scene_id")).all()
        if not rows:
            return _message(request, user, "scene.not_ready")
        listed = [(r, not _missing(c, user.learner_id, _script(c, r.scene_id))) for r in rows]
    return render(request, "learner/scene_list.html", title_key="page.scenes", user=user, scenes=listed, root=ROOT)


@router.get(ROOT + "/{scene_id}", response_class=HTMLResponse)
def scene(request: Request, scene_id: str):
    user = optional_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    with request.app.state.db.tx() as c:
        script = _script(c, scene_id)
        if script is None:
            return _message(request, user, "scene.not_ready")
        missing = _missing(c, user.learner_id, script)
        run = _run(c, user.learner_id, scene_id)
        if missing or run is None:
            return render(request, "learner/scene_intro.html", title_key="page.scenes", user=user, script=script,
                          missing=missing, root=ROOT, start_path=f"{ROOT}/{scene_id}/start")
        lines = _lines(c, scene_id)
        row, line, step = _state(c, request, run, script, lines)
        if row is not None:
            return _page(request, user, c, script, row, line, step)
        measures = _complete(c, run, script, lines)
    return render(request, "learner/scene_done.html", title_key="page.scenes", user=user, script=script,
                  measures=measures, root=ROOT)


@router.post(ROOT + "/{scene_id}/start")
def scene_start(request: Request, scene_id: str):
    user = optional_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    with request.app.state.db.tx() as c:
        script = _script(c, scene_id)
        if script is None or _missing(c, user.learner_id, script):
            return RedirectResponse(f"{ROOT}/{scene_id}", status_code=303)
        if _run(c, user.learner_id, scene_id) is None:
            cfg = {"activity": "scene", "scene_id": scene_id, "script_hash": script.content_hash,
                   "friend": friend.VERSION, "exchange": X.VERSION}
            sid = c.execute(text("INSERT INTO session (learner_id, mode, config_snapshot, seed) VALUES (:l, 'learn', "
                                 "CAST(:cfg AS jsonb), :s) RETURNING id"),
                            {"l": user.learner_id, "cfg": json.dumps(cfg),
                             "s": random.SystemRandom().randrange(2**31)}).scalar_one()
            _event(c, sid, scene_id, "started", data={"script_hash": script.content_hash})
    return RedirectResponse(f"{ROOT}/{scene_id}", status_code=303)


def _owned(c, user, scene_id, data):
    try:
        eid = uuid.UUID(str(data.get("exchange_id")))
    except ValueError:
        return None, None
    run = _run(c, user.learner_id, scene_id)
    if run is None:
        return None, None
    row = c.execute(text("SELECT id, task, shown_text FROM exchange WHERE id = :e AND session_id = :s"),
                    {"e": eid, "s": run.id}).first()
    return run, row


@router.post(ROOT + "/{scene_id}/key", response_class=HTMLResponse)
async def scene_key(request: Request, scene_id: str):
    """One key on the compose keyboard: rebuilds the page with the reply so far. Writes nothing."""
    user = optional_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    data = await form_data(request)
    with request.app.state.db.tx() as c:
        script = _script(c, scene_id)
        _, row = _owned(c, user, scene_id, data) if script else (None, None)
        if row is None or row.task["step"] != "reply":
            return RedirectResponse(f"{ROOT}/{scene_id}", status_code=303)
        line = next(x for x in _lines(c, scene_id) if x.n == row.task["line"])
        step = X.step("own", _answers(c, row.id), why_due=False)
        keys = _keys(c)
        buffer = str(data.get("buffer", ""))[:MAX_LEN]
        if data.get("erase"):
            buffer = buffer[:-1]
        elif str(data.get("key", "")) in keys:
            buffer = (buffer + str(data["key"]))[:MAX_LEN]
        return _page(request, user, c, script, row, line, step, buffer=buffer)


@router.post(ROOT + "/{scene_id}/answer", response_class=HTMLResponse)
async def scene_answer(request: Request, scene_id: str):
    user = optional_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    here = f"{ROOT}/{scene_id}"
    data = await form_data(request)
    with request.app.state.db.tx() as c:
        script = _script(c, scene_id)
        run, row = _owned(c, user, scene_id, data) if script else (None, None)
        if row is None:
            return RedirectResponse(here, status_code=303)
        line = next((x for x in _lines(c, scene_id) if x.n == row.task["line"]), None)
        answers = _answers(c, row.id)
        variants = _variants(c, line.id) if line else []
    if line is None:
        return RedirectResponse(here, status_code=303)
    comprehend = row.task["step"] == "comprehend"
    step = X.Step("answer", 1) if comprehend and not answers else (
        X.Step("close") if comprehend else X.step("own", answers, why_due=False))
    if step.name not in ("answer", "hint", "copy") or str(data.get("n", "1")) != str(step.n):
        return RedirectResponse(here, status_code=303)  # stale or replayed form
    attempt_id = uuid.uuid4()
    target = None
    if comprehend:
        chosen = str(data.get("choice", ""))
        result = checker.check_choice(attempt_id=attempt_id, chosen=chosen, correct=str(line.answer_index))
        raw, mode, cue, aids = chosen, "multiple_choice", 1, ["choices"]
        target = SkillTarget(scene_skill_id(scene_id, "RD"), "L5", item_ref=f"{scene_id}#{line.n}",
                             task_type="comprehension")
    else:
        if data.get("built"):
            raw, mode = str(data.get("buffer", ""))[:MAX_LEN], "onscreen_keyboard"
        else:
            raw, mode = str(data.get("typed", ""))[:MAX_LEN], "typed"
        key = checker.ItemKey(item_id=f"{scene_id}#{line.n}", target_script="telugu", correct_form=line.replies[0],
                              accepted_forms=tuple(line.replies[1:]) + tuple(variants))
        result = checker.check_own(attempt_id=attempt_id, raw=raw, item=key, response_mode=mode)
        cue, aids = {"answer": (0, []), "hint": (1, ["hint"]), "copy": (2, ["revealed_answer"])}[step.name]
        if step.name != "copy":  # copying a revealed reply is never evidence
            target = SkillTarget(scene_skill_id(scene_id, "PR"), "L5", item_ref=f"{scene_id}#{line.n}",
                                 task_type="scene_reply", production=True)
    n = result.normalised
    with request.app.state.db.tx() as c:
        inserted = c.execute(text(
            "INSERT INTO attempt (id, exchange_id, n, raw_text, normalised_text, input_script, response_mode, cue_level, "
            "assistance, hint_type, after_reveal, idempotency_key) VALUES (:id, :e, :n, :raw, :norm, :script, :mode, "
            ":cue, CAST(:aids AS jsonb), :ht, :ar, :k) ON CONFLICT (idempotency_key) DO NOTHING RETURNING id"),
            {"id": attempt_id, "e": row.id, "n": step.n, "raw": raw, "norm": n.text if n else None,
             "script": n.input_script if n else None, "mode": mode, "cue": cue, "aids": json.dumps(aids),
             "ht": "generic" if step.name == "hint" else None, "ar": step.revealed, "k": f"{row.id}:{step.n}"}).scalar()
    if inserted is None:
        return RedirectResponse(here, status_code=303)
    request.app.state.writer.record_verdict(result.verdict, skill=target, at=request.app.state.clock())
    if comprehend:
        return RedirectResponse(here, status_code=303)
    outcome = result.verdict.outcome
    with request.app.state.db.tx() as c:
        nxt = X.step("own", _answers(c, row.id), why_due=False)
        if nxt.name == "hint":
            _event(c, run.id, scene_id, "hint", exchange_id=row.id, data={"line": line.n})
        if outcome == "unsure":
            _event(c, run.id, scene_id, "fallback", exchange_id=row.id,
                   data={"line": line.n, "reason": result.verdict.reason_code})
    if nxt.name != "close":
        return RedirectResponse(here, status_code=303)
    return render(request, "learner/scene_feedback.html", title_key="page.scenes", user=user, line=line,
                  outcome=outcome, here=here, fallback=outcome == "unsure",
                  outcome_key={"correct": "fb.correct", "unsure": "fb.unsure"}.get(outcome, "fb.wrong"))


def _complete(c, run, script, lines) -> dict:
    """Close the run and record its measures (scene_event 'completed'); returns them."""
    rows = c.execute(text(
        "SELECT e.task->>'step' AS step, a.cue_level, a.after_reveal, a.normalised_text, v.outcome, v.kind "
        "FROM exchange e JOIN attempt a ON a.exchange_id = e.id JOIN verdict v ON v.attempt_id = a.id "
        "WHERE e.session_id = :s"), {"s": run.id}).all()
    events = c.execute(text("SELECT event, oov_words, hindi_share FROM scene_event WHERE session_id = :s"),
                       {"s": run.id}).all()
    shown = [r.shown_text for r in _exchanges(c, run.id) if r.task["step"] == "comprehend"]
    required = set(script.vocab_required)
    replies = [r for r in rows if r.step == "reply"]
    introduced = {w for t in shown + [f for x in lines for f in x.replies] for w in tokens(t)} & required
    recalled = {w for r in replies if r.outcome == "correct" and r.cue_level == 0 and r.normalised_text
                for w in tokens(r.normalised_text)} & required
    shares = [e.hindi_share for e in events if e.event == "line_shown" and e.hindi_share is not None]
    now = dt.datetime.now(dt.UTC)
    seconds = max(0, int((now - run.started_at).total_seconds()))
    m = {
        "comprehension": {"correct": sum(r.step == "comprehend" and r.outcome == "correct" for r in rows),
                          "asked": sum(r.step == "comprehend" for r in rows)},
        "production": {"independent_correct": sum(r.outcome == "correct" and r.cue_level == 0 for r in replies),
                       "assisted_correct": sum(r.outcome == "correct" and r.cue_level == 1 for r in replies),
                       "unsure": sum(r.outcome == "unsure" for r in replies),
                       "opportunities": sum(1 for x in lines if x.replies)},
        "hints": sum(e.event == "hint" for e in events),
        "fallbacks": sum(e.event == "fallback" for e in events),
        "out_of_band_words": sorted({w for e in events for w in e.oov_words}),
        "vocabulary_introduced": sorted(introduced),
        "vocabulary_recalled": sorted(recalled),
        "hindi_share": sum(shares) / len(shares) if shares else 0.0,
        "time_on_task_s": seconds,
    }
    _event(c, run.id, script.scene_id, "completed", data=m)
    c.execute(text("UPDATE session SET ended_at = now(), time_on_task_s = :t WHERE id = :s"),
              {"t": seconds, "s": run.id})
    return m
