"""The one lesson to do next (home screen; X-PERS-06/08, P-LSP-03). Reads state only; writes nothing.

Order, from the learner's real state:
1. a due review (FSRS cards of approved units whose due time has passed, placed skills awaiting confirmation)
   in ladder order — reviews come before new learning;
2. a rule Raju has forgotten (re-teaching, P8b-01);
3. the first activity, in ladder order (letters → aksharas → words → chunks), that has an unlocked unit the learner
   has not met yet and whose daily new-item cap is not reached; units unlock only through the existing gates;
4. Raju's correction practice, once approved rules exist;
5. a conversation scene whose prerequisites are mastered or placed;
6. otherwise nothing new today: the home screen says so and offers the progress page.
"""
import dataclasses
import datetime as dt

from sqlalchemy import text

from . import routes_learn as RL
from .routes_ladder import ladder

MINUTES = {"letters": 5, "aksharas": 6, "words": 6, "chunks": 7, "rules": 10, "scenes": 8}
STAGE = {"L0": "stage.L0", "L1": "stage.L1", "L2": "stage.L2", "L3": "stage.L3", "L4": "stage.L4", "L5": "stage.L5"}


@dataclasses.dataclass(frozen=True)
class Lesson:
    activity: str
    path: str
    title_key: str
    reason_key: str
    minutes: int
    review: bool = False
    reason_args: dict = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True)
class Home:
    lesson: Lesson | None
    stage_key: str
    done: int
    total: int


def _due(c, act, learner_id, now) -> int:
    views, meta = RL._units(c, act, learner_id)
    ids = [v.id for v in views]
    if not ids:
        return 0
    n = c.execute(text("SELECT count(*) FROM learner_lexeme_card WHERE learner_id = :l AND card_kind = :k AND "
                       "card_ref = ANY(:ids) AND due <= :now"),
                  {"l": learner_id, "k": act.card_kind, "ids": ids, "now": now}).scalar_one()
    cards = [RL.LP.CardView(r.card_ref, r.modality, r.due) for r in c.execute(text(
        "SELECT card_ref, modality, due FROM learner_lexeme_card WHERE learner_id = :l AND card_kind = :k"),
        {"l": learner_id, "k": act.card_kind})]
    placed = [x for x in RL._placed_cards(c, act, learner_id, views, meta, cards) if x.due and x.due <= now]
    return n + len(placed)


def _fresh(c, act, learner_id, now) -> bool:
    views, _ = RL._units(c, act, learner_id)
    if not views:
        return False
    seen = set(c.execute(text("SELECT DISTINCT card_ref FROM learner_lexeme_card WHERE learner_id = :l AND "
                              "card_kind = :k"), {"l": learner_id, "k": act.card_kind}).scalars())
    seen |= {x.letter_id for x in RL._placed_cards(c, act, learner_id, views, RL._units(c, act, learner_id)[1], [])}
    new_today = c.execute(text(
        "SELECT count(*) FROM exchange e JOIN session s ON s.id = e.session_id WHERE s.learner_id = :l "
        "AND e.task->>'activity' = :a AND (e.task->>'new')::boolean AND e.created_at::date = :d"),
        {"l": learner_id, "a": act.name, "d": now.date()}).scalar_one()
    return any(v.id not in seen for v in views) and new_today < act.new_cap


def _scene_open(c, learner_id) -> bool:
    for s in c.execute(text("SELECT prerequisites FROM learner_scene_script")).scalars():
        statuses = [c.execute(text("SELECT status FROM learner_skill_state WHERE learner_id = :l AND skill_id = :s"),
                              {"l": learner_id, "s": k}).scalar() for k in s]
        if all(x in ("mastered", "placed") for x in statuses):
            return True
    return False


def recommend(c, learner_id, now: dt.datetime | None = None) -> Lesson | None:
    now = now or dt.datetime.now(dt.UTC)
    order = [RL.LETTERS, RL.AKSHARAS, RL.WORDS, RL.CHUNKS]
    for act in order:
        n = _due(c, act, learner_id, now)
        if n:
            return Lesson(act.name, act.path, f"page.{act.name}", "home.why_review", 4, True, {"n": n})
    forgot = c.execute(text("SELECT count(*) FROM classmate_rule_state cs JOIN learner_rule_version rv ON "
                            "rv.rule_id = cs.rule_id WHERE cs.learner_id = :l AND cs.state = 'forgotten'"),
                       {"l": learner_id}).scalar_one()
    if forgot:
        return Lesson("rules", "/learn/rules", "page.rules", "home.why_raju_forgot", MINUTES["rules"], True)
    for i, act in enumerate(order):
        if _fresh(c, act, learner_id, now):
            reason = "home.why_start" if i == 0 else "home.why_next"
            prev = f"page.{order[i - 1].name}" if i else None
            return Lesson(act.name, act.path, f"page.{act.name}", reason, MINUTES[act.name],
                          reason_args={"prev_key": prev} if prev else {})
    if c.execute(text("SELECT EXISTS (SELECT 1 FROM learner_rule_version)")).scalar_one():
        return Lesson("rules", "/learn/rules", "page.rules", "home.why_rules", MINUTES["rules"])
    if _scene_open(c, learner_id):
        return Lesson("scenes", "/learn/scenes", "page.scenes", "home.why_scenes", MINUTES["scenes"])
    return None


def home(c, learner_id, now=None) -> Home:
    can, now_learning, later, _ = ladder(c, learner_id)
    total = len(can) + len(now_learning) + len(later)
    first_open = next((t for t in now_learning + later), None)
    stage = STAGE.get(first_open["band"] if first_open else "L5", "stage.L0")
    return Home(recommend(c, learner_id, now), stage, len(can) + sum(1 for t in now_learning if t["placed"]), total)
