"""Placement diagnostic and the ladder view (slice S7; F-PLACE, F-LAD-UI, X-PERS-03/08).

`/learn/placement` probes approved L0–L3 units without the letter gates (it is a test, not practice), in the order
the placement walk asks for; it shows no feedback and no answer. Every answer goes through the checker and the
OutcomeWriter as a card review only (no skill evidence); when the walk ends, or the learner stops, the diagnostic
issues one placement decision and the OutcomeWriter applies it after re-checking the verdicts. The diagnostic runs
once per learner. `/ladder` reads `learner_skill_state` and shows what the learner can do, what is in progress and
what comes later, with one recommendation that explains itself. No scores or percentages are shown.
"""
import json
import random
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import text

from setu.domain import checker
from setu.domain import placement as P
from setu.domain.normalise import to_devanagari
from setu.store.outcome_writer import CardTarget

from .routes_ui import form_data, optional_user, render

router = APIRouter()
PATH = "/learn/placement"
MAX_LEN = 40
UNITS = {
    "L0": ("letter", ("SELECT id, telugu, devanagari AS reading, twin_label_hi AS prompt FROM learner_letter "
                     "ORDER BY varnamala_order")),
    "L1": ("akshara", ("SELECT id, telugu, devanagari AS reading, twin_label_hi AS prompt FROM learner_akshara "
                      "ORDER BY unit_order")),
    "L2": ("lexeme", ("SELECT id, telugu, NULL AS reading, hindi_gloss AS prompt FROM learner_lexeme "
                     "WHERE word_group IS NOT NULL ORDER BY ladder_order")),
    "L3": ("chunk", ("SELECT ch.id, ch.telugu, NULL AS reading, ch.hindi_meaning AS prompt FROM learner_chunk ch "
                    "JOIN learner_scene s ON s.id = ch.scene_id ORDER BY ch.unit_order")),
}
FAMILIES = {"L0": "script", "L1": "akshara", "L2": "word", "L3": "chunk"}
START_AFTER = {None: "letters", "L0": "aksharas", "L1": "words", "L2": "chunks", "L3": "rules"}


def _units(c):
    return {band: (kind, c.execute(text(sql)).all()) for band, (kind, sql) in UNITS.items()}


def _session(c, learner_id):
    return c.execute(text("SELECT id, seed, ended_at FROM session WHERE learner_id = :l AND mode = 'diagnostic' "
                          "ORDER BY started_at DESC LIMIT 1"), {"l": learner_id}).first()


def _probes(c, session_id):
    rows = c.execute(text(
        "SELECT e.id, e.task, v.id AS verdict_id, v.outcome FROM exchange e LEFT JOIN attempt a ON a.exchange_id = e.id "
        "LEFT JOIN verdict v ON v.attempt_id = a.id WHERE e.session_id = :s ORDER BY e.created_at"),
        {"s": session_id}).all()
    done = [r for r in rows if r.outcome is not None]
    open_ = next((r for r in rows if r.outcome is None), None)
    return [P.Probe(r.task["band"], r.task["unit"], r.task["task_type"], r.outcome) for r in done], done, open_


def _walk(c, units, session_id):
    probes, done, open_ = _probes(c, session_id)
    available = [b for b, (_, rows) in units.items() if rows]
    return P.walk(probes, available), probes, done, open_


def _expected(unit, task_type) -> str:
    if task_type == "recall":
        return unit.telugu
    return unit.reading or to_devanagari(unit.telugu)


def _probe_page(request, user, row, unit):
    return render(request, "learner/placement_probe.html", title_key="page.placement", user=user,
                  exchange_id=row.id, task=row.task, unit=unit, max_len=MAX_LEN)


def _result(request, user, c, session_id):
    units = _units(c)
    state, *_ = _walk(c, units, session_id)
    bands = state.placed_bands
    start = START_AFTER[bands[-1] if bands else None]
    return render(request, "learner/placement_result.html", title_key="page.placement", user=user, bands=bands,
                  start=start)


def _finish(request, user):
    """Issue the placement decision for the walk so far, apply it, and end the diagnostic."""
    with request.app.state.db.tx() as c:
        session = _session(c, user.learner_id)
        if session is None or session.ended_at is not None:
            return
        state, _, done, _ = _walk(c, _units(c), session.id)
        bands = state.placed_bands
        skills = c.execute(text("SELECT id FROM skill WHERE band = ANY(:b) AND family = ANY(:f) ORDER BY id"),
                           {"b": list(bands), "f": [FAMILIES[b] for b in bands]}).scalars().all()
        verdicts = [r.verdict_id for r in done if r.outcome == "correct" and r.task["band"] in state.passed]
    decision = P.decide(learner_id=user.learner_id, bands=bands, skill_ids=skills, verdict_ids=verdicts)
    if decision is not None:
        request.app.state.writer.apply_placement(decision, at=request.app.state.clock())
    with request.app.state.db.tx() as c:
        c.execute(text("UPDATE session SET ended_at = now() WHERE id = :s"), {"s": session.id})


@router.get(PATH, response_class=HTMLResponse)
def placement_page(request: Request):
    user = optional_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    with request.app.state.db.tx() as c:
        units = _units(c)
        if not any(rows for _, rows in units.values()):
            return render(request, "learner/message.html", title_key="page.placement", user=user,
                          message_key="learn.not_ready")
        session = _session(c, user.learner_id)
        if session is None:
            return render(request, "learner/placement_intro.html", title_key="page.placement", user=user)
        if session.ended_at is not None:
            return _result(request, user, c, session.id)
        state, probes, _, open_ = _walk(c, units, session.id)
        if open_ is not None:  # still unanswered: the same probe again (no re-roll)
            unit = next(u for u in units[open_.task["band"]][1] if u.id == open_.task["unit"])
            return _probe_page(request, user, open_, unit)
        nxt = None if state.done else P.next_probe(state.band, probes, [u.id for u in units[state.band][1]],
                                                    seed=session.seed)
        if nxt is not None:
            unit_id, task_type = nxt
            unit = next(u for u in units[state.band][1] if u.id == unit_id)
            task = {"activity": "placement", "version": P.VERSION, "band": state.band, "unit": unit_id,
                    "card_kind": units[state.band][0], "task_type": task_type,
                    "expected": _expected(unit, task_type)}
            eid = c.execute(text("INSERT INTO exchange (session_id, kind, source, task) VALUES (:s, 'review', 'bank', "
                                 "CAST(:t AS jsonb)) RETURNING id"),
                            {"s": session.id, "t": json.dumps(task, ensure_ascii=False)}).scalar_one()
            row = c.execute(text("SELECT id, task FROM exchange WHERE id = :e"), {"e": eid}).first()
            return _probe_page(request, user, row, unit)
    _finish(request, user)  # the walk is over (or a band ran out of units)
    with request.app.state.db.tx() as c:
        return _result(request, user, c, _session(c, user.learner_id).id)


@router.post(PATH + "/start")
def placement_start(request: Request):
    user = optional_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    with request.app.state.db.tx() as c:
        if _session(c, user.learner_id) is None:  # the diagnostic runs once
            cfg = {"activity": "placement", "version": P.VERSION, "start": P.START,
                   "max_probes_per_band": P.MAX_PROBES_PER_BAND}
            c.execute(text("INSERT INTO session (learner_id, mode, config_snapshot, seed) VALUES (:l, 'diagnostic', "
                           "CAST(:cfg AS jsonb), :s)"),
                      {"l": user.learner_id, "cfg": json.dumps(cfg), "s": random.SystemRandom().randrange(2**31)})
    return RedirectResponse(PATH, status_code=303)


@router.post(PATH + "/stop")
def placement_stop(request: Request):
    """'Start from here': the walk ends now and places only the bands already passed."""
    user = optional_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    _finish(request, user)
    return RedirectResponse(PATH, status_code=303)


@router.post(PATH + "/answer")
async def placement_answer(request: Request):
    user = optional_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    data = await form_data(request)
    try:
        exchange_id = uuid.UUID(str(data.get("exchange_id")))
    except ValueError:
        return RedirectResponse(PATH, status_code=303)
    with request.app.state.db.tx() as c:
        row = c.execute(text(
            "SELECT e.id, e.task, a.id AS attempt_id FROM exchange e JOIN session s ON s.id = e.session_id LEFT JOIN "
            "attempt a ON a.exchange_id = e.id WHERE e.id = :e AND s.learner_id = :l AND s.mode = 'diagnostic' "
            "AND s.ended_at IS NULL"), {"e": exchange_id, "l": user.learner_id}).first()
    if row is None or row.attempt_id is not None:
        return RedirectResponse(PATH, status_code=303)
    task, attempt_id = row.task, uuid.uuid4()
    raw = str(data.get("typed", ""))[:MAX_LEN]
    target = "telugu" if task["task_type"] == "recall" else "devanagari"
    result = checker.check_recall(attempt_id=attempt_id, raw=raw, accepted=[task["expected"]], target_script=target,
                                  response_mode="typed", closed=True)
    n = result.normalised
    with request.app.state.db.tx() as c:
        inserted = c.execute(text(
            "INSERT INTO attempt (id, exchange_id, n, raw_text, normalised_text, input_script, response_mode, cue_level, "
            "idempotency_key) VALUES (:id, :e, 1, :raw, :norm, :script, 'typed', 0, :k) ON CONFLICT (idempotency_key) "
            "DO NOTHING RETURNING id"),
            {"id": attempt_id, "e": row.id, "raw": raw, "norm": n.text if n else None,
             "script": n.input_script if n else None, "k": f"{row.id}:1"}).scalar()
    if inserted is not None:
        modality = "RCL" if task["task_type"] == "recall" else "REC"
        request.app.state.writer.record_verdict(result.verdict, card=CardTarget(task["card_kind"], task["unit"], modality),
                                                at=request.app.state.clock())
    return RedirectResponse(PATH, status_code=303)


# ---------------------------------------------------------------- the ladder view

_TARGETS = """
SELECT s.band, s.family, s.target, s.id, s.modality, st.status,
       CASE s.family
         WHEN 'script' THEN (SELECT min(group_hi) FROM learner_letter WHERE letter_group = s.target)
         WHEN 'akshara' THEN (SELECT min(family) FROM learner_akshara WHERE family = s.target)
         WHEN 'word' THEN (SELECT string_agg(telugu, ' · ' ORDER BY ladder_order) FROM (SELECT telugu, ladder_order
                            FROM learner_lexeme WHERE word_group = s.target ORDER BY ladder_order LIMIT 3) w)
         WHEN 'chunk' THEN (SELECT title_hi FROM learner_scene sc WHERE sc.id = s.target
                             AND EXISTS (SELECT 1 FROM learner_chunk ch WHERE ch.scene_id = sc.id))
         WHEN 'rule' THEN (SELECT title_hi FROM learner_rule_version rv WHERE rv.target_skill_id = s.id)
       END AS name,
       CASE s.family WHEN 'script' THEN (SELECT min(varnamala_order) FROM learner_letter WHERE letter_group = s.target)
                     WHEN 'akshara' THEN array_position(ARRAY['vowel_signs', 'nasal_visarga', 'doubles', 'conjuncts'],
                                                        s.target)
                     ELSE 0 END AS ord
  FROM skill s LEFT JOIN learner_skill_state st ON st.skill_id = s.id AND st.learner_id = :l
 WHERE s.active AND s.direction = 'HI->TE'
"""
LEARNING = ("learning", "due", "relearning", "placed")


def ladder(c, learner_id):
    rows = [r for r in c.execute(text(_TARGETS), {"l": learner_id}) if r.name]
    targets: dict = {}
    for r in rows:
        t = targets.setdefault((r.band, r.family, r.target), {"band": r.band, "family": r.family, "name": r.name,
                                                             "ord": r.ord, "statuses": set(), "skills": set()})
        t["statuses"].add(r.status)
        t["skills"].add(r.id)
    owner = {sid: key for key, t in targets.items() for sid in t["skills"]}
    prereqs: dict = {}
    for p in c.execute(text("SELECT skill_id, requires_id FROM skill_prereq")):
        if p.skill_id in owner and p.requires_id in owner and owner[p.requires_id] != owner[p.skill_id]:
            prereqs.setdefault(owner[p.skill_id], set()).add(owner[p.requires_id])
    for t in targets.values():
        t["done"] = "mastered" in t["statuses"]
        t["placed"] = "placed" in t["statuses"] and not t["done"]
        t["learning"] = not t["done"] and bool(t["statuses"] & set(LEARNING))
        if t["family"] == "akshara":
            t["name_key"] = f"ladder.family.{t['name']}"
    ordered = sorted(targets.items(), key=lambda kv: (kv[1]["band"], kv[1]["family"], kv[1]["ord"], kv[0][2]))

    def ok(key):
        return targets[key]["done"] or targets[key]["placed"]

    for key, t in ordered:
        missing = [targets[k] for k in sorted(prereqs.get(key, ())) if not ok(k)]
        t["needs"] = missing[0] if missing else None
        t["after"] = next((targets[k] for k in sorted(prereqs.get(key, ())) if ok(k)), None)
    can = [t for _, t in ordered if t["done"]]
    now = [t for _, t in ordered if t["learning"]]
    later = [t for _, t in ordered if not t["done"] and not t["learning"]]
    nxt = next((t for t in now if not t["placed"]), None) or next((t for t in later if t["needs"] is None), None)
    return can, now, later, nxt


@router.get("/ladder", response_class=HTMLResponse)
def ladder_page(request: Request):
    user = optional_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    with request.app.state.db.tx() as c:
        can, now, later, nxt = ladder(c, user.learner_id)
    return render(request, "learner/ladder.html", title_key="page.ladder", user=user, can=can, now=now, later=later,
                  nxt=nxt, nav="progress")
