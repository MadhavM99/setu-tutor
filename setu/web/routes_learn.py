"""Script, word and chunk practice: L0 letters (S1), L1 aksharas (S2), L2 words (S3), L3 scene chunks (S4). Every answer goes through the checker and the
OutcomeWriter; pages show only approved units (`learner_letter`, `learner_akshara`) and keep the pending task on the
server, so a learner cannot re-roll a task (E-13). Aksharas are offered only once the learner has recalled every
letter in them without help (X-PERS-04). Akshara answers are built on an on-screen keyboard that works without
JavaScript: each key is a round trip that only rebuilds the page (R-INPUT, cue-free). Words, like aksharas, are
offered only once their letters have been recalled; a false friend's meaning step includes its Hindi look-alike.
Chunks are introduced inside their scene (title and setup) and built with a space key."""
import dataclasses
import datetime as dt
import json
import random
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import text

from setu.content.aksharas import SIGNS, VIRAMA
from setu.domain import checker
from setu.domain import letter_practice as LP
from setu.domain.normalise import TELU_TO_DEVA
from setu.store.outcome_writer import CardTarget, SkillTarget

from .routes_ui import form_data, optional_user, render

router = APIRouter()
TELUGU_SIGNS = tuple(s for _, s, _, _ in SIGNS) + (VIRAMA,)


@dataclasses.dataclass(frozen=True)
class Activity:
    name: str
    card_kind: str
    units_sql: str
    new_cap: int
    intro_per_group: bool
    compose: bool
    skill: str  # format string over the unit's skill key
    chain: tuple = LP.CHAIN
    prompts: str = "learn"  # catalog group for the page prompts
    vowel_keys: bool = False  # words can start with a vowel letter
    space_key: bool = False  # chunks have more than one word
    max_len: int = 12

    @property
    def path(self) -> str:
        return f"/learn/{self.name}"

    @property
    def text(self) -> dict:
        """Catalog keys for this activity's prompts (templates may not hold literal text)."""
        return {k: f"{self.prompts}.{k}" for k in ("new", "twin_is", "choice_prompt", "meaning_prompt", "recall_prompt")}

    @property
    def view(self) -> str:
        return {"letters": "learner_letter", "aksharas": "learner_akshara", "words": "learner_lexeme",
                "chunks": "learner_chunk"}[self.name]


# every letter in the unit has had a correct, cue-free recall (X-PERS-04), or its L0 skill was placed (F-PLACE)
_RECALLED = ("WHERE NOT EXISTS (SELECT 1 FROM learner_letter x WHERE x.telugu = l.ch AND (EXISTS (SELECT 1 FROM "
             "learner_lexeme_card c JOIN fsrs_review_log r ON r.card_id = c.id AND r.rating >= 3 AND r.cue_level = 0 "
             "WHERE c.card_kind = 'letter' AND c.card_ref = x.id AND c.modality = 'RCL' AND c.learner_id = :l) OR "
             "EXISTS (SELECT 1 FROM learner_skill_state ss WHERE ss.learner_id = :l AND ss.status = 'placed' AND "
             "ss.skill_id = 'L0.script.' || x.letter_group || '.RCL'))))")

LETTERS = Activity(
    "letters", "letter", "SELECT id, telugu, devanagari, twin_label_hi AS label, letter_group AS grp, "
    "varnamala_order AS ord, NULL AS confusable, letter_group AS skill_key, note_hi, group_hi, kind, NULL AS trap, "
    "NULL AS cognate_of, NULL AS setup_hi FROM learner_letter ORDER BY varnamala_order", 5, False, False, "L0.script.{}")
AKSHARAS = Activity(
    "aksharas", "akshara", "SELECT a.id, a.telugu, a.devanagari, a.twin_label_hi AS label, a.akshara_group AS grp, "
    "a.unit_order AS ord, a.letters->>0 AS confusable, a.family AS skill_key, a.note_hi, a.group_hi, a.kind, "
    "NULL AS trap, NULL AS cognate_of, NULL AS setup_hi FROM learner_akshara a WHERE NOT EXISTS (SELECT 1 FROM "
    "jsonb_array_elements_text(a.letters) AS l(ch) " + _RECALLED + " ORDER BY a.unit_order", 10, True, True,
    "L1.akshara.{}")
WORDS = Activity(
    "words", "lexeme", "SELECT w.id, w.telugu, NULL AS devanagari, w.hindi_gloss AS label, w.word_group AS grp, "
    "w.ladder_order AS ord, w.word_group AS confusable, w.word_group AS skill_key, w.false_friend_note_hi AS note_hi, "
    "NULL AS group_hi, 'word' AS kind, w.looks_like_hi AS trap, w.cognate_of, NULL AS setup_hi FROM learner_lexeme w "
    "WHERE w.word_group IS NOT NULL AND NOT EXISTS (SELECT 1 FROM jsonb_array_elements_text(w.letters) AS l(ch) "
    + _RECALLED + " ORDER BY w.ladder_order", 5, False, True, "L2.word.{}", chain=LP.WORD_CHAIN, prompts="word",
    vowel_keys=True)
CHUNKS = Activity(
    "chunks", "chunk", "SELECT ch.id, ch.telugu, NULL AS devanagari, ch.hindi_meaning AS label, ch.scene_id AS grp, "
    "ch.unit_order AS ord, ch.scene_id AS confusable, ch.scene_id AS skill_key, NULL AS note_hi, "
    "s.title_hi AS group_hi, 'chunk' AS kind, NULL AS trap, NULL AS cognate_of, s.setup_hi FROM learner_chunk ch "
    "JOIN learner_scene s ON s.id = ch.scene_id WHERE NOT EXISTS (SELECT 1 FROM "
    "jsonb_array_elements_text(ch.letters) AS l(ch) " + _RECALLED + " ORDER BY ch.unit_order", 5, False, True,
    "L3.chunk.{}", chain=LP.WORD_CHAIN, prompts="chunk", vowel_keys=True, space_key=True, max_len=40)
ACTIVITIES = {a.name: a for a in (LETTERS, AKSHARAS, WORDS, CHUNKS)}


def _units(c, act: Activity, learner_id):
    rows = c.execute(text(act.units_sql), {"l": learner_id}).all()
    views = [LP.UnitView(r.id, r.telugu, r.devanagari, r.label, r.grp, r.ord, r.confusable, r.trap) for r in rows]
    return views, {r.id: r for r in rows}


def _placed_cards(c, act: Activity, learner_id, views, meta, cards):
    """Units of a placed skill are not new: each counts as a recall card due at the skill's confirmation date, so the
    learner gets a confirmation review instead of the intro chain (F-PLACE)."""
    due = dict(c.execute(text("SELECT skill_id, due_at FROM learner_skill_state WHERE learner_id = :l AND "
                              "status = 'placed'"), {"l": learner_id}).all())
    have = {x.letter_id for x in cards}
    return [LP.CardView(v.id, "RCL", due[sid]) for v in views if v.id not in have
            and (sid := f"{act.skill.format(meta[v.id].skill_key)}.RCL") in due]


def _any_approved(c, act: Activity) -> bool:
    return c.execute(text(f"SELECT EXISTS (SELECT 1 FROM {act.view})")).scalar_one()


def _session(c, act: Activity, learner_id):
    today = dt.datetime.now(dt.UTC).date()
    row = c.execute(text("SELECT id, seed FROM session WHERE learner_id = :l AND mode = 'learn' AND ended_at IS NULL "
                         "AND config_snapshot->>'activity' = :a AND started_at::date = :d "
                         "ORDER BY started_at DESC LIMIT 1"), {"l": learner_id, "a": act.name, "d": today}).first()
    if row:
        return row.id, row.seed
    seed = random.SystemRandom().randrange(2**31)
    cfg = {"activity": act.name, "planner": "letter-practice-1", "new_cap": act.new_cap,
           "intro_per_group": act.intro_per_group}
    sid = c.execute(text("INSERT INTO session (learner_id, mode, config_snapshot, seed) VALUES (:l, 'learn', "
                         "CAST(:cfg AS jsonb), :s) RETURNING id"),
                    {"l": learner_id, "cfg": json.dumps(cfg), "s": seed}).scalar_one()
    return sid, seed


def _last_exchange(c, act: Activity, learner_id):
    return c.execute(text(
        "SELECT e.id, e.task, a.id AS attempt_id, v.outcome FROM exchange e JOIN session s ON s.id = e.session_id "
        "LEFT JOIN attempt a ON a.exchange_id = e.id LEFT JOIN verdict v ON v.attempt_id = a.id "
        "WHERE s.learner_id = :l AND e.task->>'activity' = :a ORDER BY e.created_at DESC LIMIT 1"),
        {"l": learner_id, "a": act.name}).first()


def _task(task_json) -> LP.Task:
    return LP.Task(task_json["type"], task_json["letter_id"], tuple(task_json.get("options", ())),
                   tuple(task_json.get("chain", ())), bool(task_json.get("revealed")))


def _create_exchange(c, act: Activity, session_id, task: LP.Task) -> uuid.UUID:
    payload = {"activity": act.name, "type": task.type, "letter_id": task.letter_id, "options": list(task.options),
               "chain": list(task.chain), "revealed": task.revealed, "new": task.new}
    kind = "learn" if task.type == "intro" else "review"
    return c.execute(text("INSERT INTO exchange (session_id, kind, source, task) VALUES (:s, :k, 'bank', "
                          "CAST(:t AS jsonb)) RETURNING id"),
                     {"s": session_id, "k": kind, "t": json.dumps(payload, ensure_ascii=False)}).scalar_one()


def _keys(c, act: Activity, views, task: LP.Task):
    """The on-screen keys. Letters: one key per letter. Aksharas: every approved consonant plus every sign, in the
    target script, so the keyboard never narrows the answer down."""
    if not act.compose:
        return [v.devanagari for v in views] if task.type == "recognise" else [v.telugu for v in views]
    kinds = ("vowel", "consonant") if act.vowel_keys else ("consonant",)
    consonants = c.execute(text("SELECT telugu FROM learner_letter WHERE kind = ANY(:k) ORDER BY varnamala_order"),
                           {"k": list(kinds)}).scalars().all()
    keys = list(consonants) + list(TELUGU_SIGNS)
    if task.type == "recognise":
        keys = [TELU_TO_DEVA[k] for k in keys]
    return keys + [" "] if act.space_key else keys


def _page(request, user, act, exchange_id, task, views, meta, keys, buffer=""):
    by_id = {x.id: x for x in views}
    labels = [(o, meta[o[len(LP.TRAP):]].trap if o.startswith(LP.TRAP) else by_id[o].label)
              for o in task.options if o in by_id or o.startswith(LP.TRAP)]
    step_total = len(act.chain)
    return render(request, f"learner/practice_{task.type}.html", title_key=f"page.{act.name}", user=user, act=act,
                  step_n=step_total - len(task.chain), step_total=step_total,
                  exchange_id=exchange_id, unit=by_id[task.letter_id], meta=meta[task.letter_id],
                  options=[by_id[o] for o in task.options if o in by_id], labels=labels, keys=keys, buffer=buffer)


def _message(request, user, act, key):
    return render(request, "learner/message.html", title_key=f"page.{act.name}", user=user, message_key=key)


def _activity(name) -> Activity | None:
    return ACTIVITIES.get(name)


@router.get("/learn", response_class=HTMLResponse)
def learn_home(request: Request):
    user = optional_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    with request.app.state.db.tx() as c:
        ready = _any_approved(c, LETTERS)
    if not ready:
        return _message(request, user, LETTERS, "learn.not_ready")
    return render(request, "learner/script_intro.html", title_key="page.letters", user=user)


@router.get("/learn/{name}", response_class=HTMLResponse)
def practice(request: Request, name: str):
    act, user = _activity(name), optional_user(request)
    if act is None:
        return RedirectResponse("/learn", status_code=303)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    now = dt.datetime.now(dt.UTC)
    with request.app.state.db.tx() as c:
        if not _any_approved(c, act):
            return _message(request, user, act, "learn.not_ready")
        views, meta = _units(c, act, user.learner_id)
        last = _last_exchange(c, act, user.learner_id)
        if last is not None and last.attempt_id is None and last.task["letter_id"] in meta:
            task = _task(last.task)  # still open: show the same task again (no re-roll)
            return _page(request, user, act, last.id, task, views, meta, _keys(c, act, views, task))
        if not views:
            return _message(request, user, act, "learn.letters_first")
        pending = LP.after_answer(_task(last.task), last.outcome or "correct") if last is not None else None
        cards = [LP.CardView(r.card_ref, r.modality, r.due) for r in c.execute(text(
            "SELECT card_ref, modality, due FROM learner_lexeme_card WHERE learner_id = :l AND card_kind = :k"),
            {"l": user.learner_id, "k": act.card_kind})]
        cards += _placed_cards(c, act, user.learner_id, views, meta, cards)
        new_today = c.execute(text(
            "SELECT count(*) FROM exchange e JOIN session s ON s.id = e.session_id WHERE s.learner_id = :l "
            "AND e.task->>'activity' = :a AND (e.task->>'new')::boolean AND e.created_at::date = :d"), {"l": user.learner_id, "a": act.name, "d": now.date()}).scalar_one()
        session_id, seed = _session(c, act, user.learner_id)
        task = LP.next_task(letters=views, cards=cards, pending=pending, now=now, new_today=new_today, seed=seed,
                            new_cap=act.new_cap, intro_per_group=act.intro_per_group, chain=act.chain)
        if task is None:
            return _message(request, user, act, "learn.done_today")
        exchange_id = _create_exchange(c, act, session_id, task)
        keys = _keys(c, act, views, task)
    return _page(request, user, act, exchange_id, task, views, meta, keys)


@router.post("/learn/{name}/continue")
async def practice_continue(request: Request, name: str):
    """The intro card has no answer: moving on creates the next step of the chain without any attempt or verdict."""
    act, user = _activity(name), optional_user(request)
    if act is None or user is None:
        return RedirectResponse("/learn" if act is None else "/login", status_code=303)
    data = await form_data(request)
    with request.app.state.db.tx() as c:
        last = _last_exchange(c, act, user.learner_id)
        if last is None or str(last.id) != str(data.get("exchange_id")) or last.task["type"] != "intro":
            return RedirectResponse(act.path, status_code=303)
        views, _ = _units(c, act, user.learner_id)
        session_id, seed = _session(c, act, user.learner_id)
        task = LP.next_task(letters=views, cards=[], pending=_task(last.task), now=dt.datetime.now(dt.UTC),
                            new_today=0, seed=seed)
        if task is not None:
            _create_exchange(c, act, session_id, task)
    return RedirectResponse(act.path, status_code=303)


def _open_exchange(c, user, exchange_id):
    return c.execute(text(
        "SELECT e.id, e.task, a.id AS attempt_id FROM exchange e JOIN session s ON s.id = e.session_id "
        "LEFT JOIN attempt a ON a.exchange_id = e.id WHERE e.id = :e AND s.learner_id = :l"),
        {"e": exchange_id, "l": user.learner_id}).first()


@router.post("/learn/{name}/key", response_class=HTMLResponse)
async def practice_key(request: Request, name: str):
    """One key on the compose keyboard: rebuilds the page with the answer so far. Writes nothing."""
    act, user = _activity(name), optional_user(request)
    if act is None or user is None or not act.compose:
        return RedirectResponse("/learn" if user else "/login", status_code=303)
    data = await form_data(request)
    try:
        exchange_id = uuid.UUID(str(data.get("exchange_id")))
    except ValueError:
        return RedirectResponse(act.path, status_code=303)
    with request.app.state.db.tx() as c:
        row = _open_exchange(c, user, exchange_id)
        if row is None or row.attempt_id is not None or row.task.get("activity") != act.name:
            return RedirectResponse(act.path, status_code=303)
        task = _task(row.task)
        views, meta = _units(c, act, user.learner_id)
        if task.letter_id not in meta or task.type not in ("recognise", "recall"):  # only typing steps have keys
            return RedirectResponse(act.path, status_code=303)
        keys = _keys(c, act, views, task)
    buffer = str(data.get("buffer", ""))[:act.max_len]
    if data.get("erase"):
        buffer = buffer[:-1]
    elif str(data.get("key", "")) in keys:
        buffer = (buffer + str(data["key"]))[:act.max_len]
    return _page(request, user, act, exchange_id, task, views, meta, keys, buffer=buffer)


@router.post("/learn/{name}/answer", response_class=HTMLResponse)
async def practice_answer(request: Request, name: str):
    act, user = _activity(name), optional_user(request)
    if act is None or user is None:
        return RedirectResponse("/learn" if act is None else "/login", status_code=303)
    data = await form_data(request)
    try:
        exchange_id = uuid.UUID(str(data.get("exchange_id")))
    except ValueError:
        return RedirectResponse(act.path, status_code=303)
    with request.app.state.db.tx() as c:
        row = _open_exchange(c, user, exchange_id)
        _, meta = _units(c, act, user.learner_id)
    if (row is None or row.task is None or row.task.get("activity") != act.name or row.task["type"] == "intro"
            or row.task["letter_id"] not in meta):
        return RedirectResponse(act.path, status_code=303)
    task, unit = _task(row.task), meta[row.task["letter_id"]]
    if row.attempt_id is not None:  # already answered: show the same feedback (idempotent)
        with request.app.state.db.tx() as c:
            outcome = c.execute(text("SELECT outcome FROM verdict WHERE attempt_id = :a"),
                                {"a": row.attempt_id}).scalar()
        return _feedback(request, user, act, unit, outcome)

    attempt_id = uuid.uuid4()
    if task.type in LP.OPTION_STEPS:
        chosen = str(data.get("choice", ""))
        result = checker.check_choice(attempt_id=attempt_id, chosen=chosen, correct=unit.id)
        raw, mode, cue, aids, normalised = chosen, "multiple_choice", 1, ["choices"], None
    else:
        key, typed = str(data.get("key", "")), str(data.get("typed", ""))
        if act.compose:
            raw, mode = (str(data.get("buffer", ""))[:act.max_len], "onscreen_keyboard") if data.get("built") \
                else (typed[:act.max_len], "typed")
        else:
            raw, mode = (key, "onscreen_keyboard") if key else (typed[:act.max_len], "typed")
        target, accepted = (("devanagari", [unit.devanagari]) if task.type == "recognise"
                            else ("telugu", [unit.telugu]))
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
        return RedirectResponse(act.path, status_code=303)
    modality = LP.MODALITY[task.type]
    band = act.skill.split(".", 1)[0]
    request.app.state.writer.record_verdict(
        result.verdict, card=CardTarget(act.card_kind, unit.id, modality),
        skill=SkillTarget(f"{act.skill.format(unit.skill_key)}.{modality}", band, item_ref=unit.id,
                          task_type=task.type))
    return _feedback(request, user, act, unit, result.verdict.outcome)


def _feedback(request, user, act, unit, outcome):
    key = {"correct": "fb.correct", "unsure": "fb.unsure"}.get(outcome, "fb.wrong")
    return render(request, "learner/practice_feedback.html", title_key=f"page.{act.name}", user=user, act=act,
                  unit=unit, outcome_key=key, correct=outcome == "correct")
