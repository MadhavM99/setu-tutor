"""Step 4: Raju's notebook, follow-ups, forgetting, spot checks, planner, and the 5-check leak filter."""
import random
import pytest
from setu.checker import NO_ERROR
from setu.leakfilter import check_line, seen_telugu
from setu.memory import Store
from setu.planner import choose
from setu.tutor import GOT_IT, Tutor
from setu.writer import TemplateWriter, raju_line


def tutor(tmp_path, **kw):
    kw.setdefault("drill", False)      # these tests start at the check; the drill is tested in test_drill.py
    kw.setdefault("course", "singles") # Raju right after every lesson; modules are tested in test_course.py
    return Tutor(Store(str(tmp_path)), writer=TemplateWriter(random.Random(0)), seed=1, **kw)


def right_answer(t, lid):
    p = t.store.load(lid).pending
    if p["kind"] == "check":
        return t.items[p["item"]][1].accepted[0]
    if p["kind"] == "raju":
        return t.items[p["item"]][1].accepted[0] if p["mistake"] else NO_ERROR
    rec = t.store.load(lid); fu = t._fus(rec, t.by_id[p["unit"]])[p["idx"]]
    return NO_ERROR if fu.sentence_is_correct else fu.item.accepted[0]


def play_right(t, lid, turns):
    """Answer everything correctly for `turns` turns (following any chained follow-ups)."""
    for _ in range(turns):
        r = t.next(lid)
        if r["kind"] == "done":
            return
        a = t.answer(lid, right_answer(t, lid))
        while "followup" in a:
            a = t.answer(lid, right_answer(t, lid))


# ---------- learn first ----------
def test_first_thing_is_a_lesson_never_raju(tmp_path):
    t = tutor(tmp_path)
    assert t.next("a")["kind"] == "lesson"


def test_raju_only_after_the_check_is_answered_correctly(tmp_path):
    t = tutor(tmp_path)
    t.next("a")
    a = t.answer("a", "ऊ"); assert a["verdict"] == "wrong"
    a = t.answer("a", "ऊ"); assert "सही जवाब" in a["message"]          # 2nd miss: answer shown, check stays open
    assert t.next("a")["kind"] == "waiting"
    assert t.store.load("a").raju == {}                                  # Raju has nothing yet
    t.answer("a", right_answer(t, "a"))
    assert t.store.load("a").raju == {"L0-01": "unknown"}
    assert t.next("a")["kind"] == "raju"


# ---------- one fix is not enough ----------
def test_fix_makes_raju_learning_then_followups_make_him_know(tmp_path):
    t = tutor(tmp_path)
    t.next("a"); t.answer("a", right_answer(t, "a"))
    r = t.next("a"); assert r["kind"] == "raju"
    a = t.answer("a", right_answer(t, "a"))
    assert a["raju_state"] == "learning" and "followup" in a
    while "followup" in a:
        a = t.answer("a", right_answer(t, "a"))
    assert a["message"] == GOT_IT and a["raju_says"] and t.store.load("a").raju["L0-01"] == "taught"


def test_wrong_followup_keeps_raju_learning(tmp_path):
    t = tutor(tmp_path)
    t.next("a"); t.answer("a", right_answer(t, "a")); t.next("a")
    a = t.answer("a", right_answer(t, "a"))
    wrong = "<NO_ERROR>" if right_answer(t, "a") != NO_ERROR else t.items[t._fus(t.store.load("a"), t.by_id["L0-01"])[0].item.item_id][1].raju_wrong
    a = t.answer("a", wrong); a = t.answer("a", wrong)
    assert a["verdict"] == "wrong" and t.store.load("a").raju["L0-01"] == "learning"


# ---------- forgetting ----------
def test_raju_forgets_when_the_learner_would_and_the_mistake_comes_back(tmp_path):
    t = tutor(tmp_path, new_per_day=1)
    play_right(t, "a", 3)
    assert t.store.load("a").raju["L0-01"] == "taught"
    t.skip_days("a", 30)
    r = t.next("a")
    rec = t.store.load("a")
    assert rec.raju["L0-01"] == "forgotten" and r["kind"] == "raju" and rec.pending["mistake"] is True


# ---------- spot checks ----------
def test_spot_check_only_on_units_raju_knows(tmp_path):
    t = tutor(tmp_path, new_per_day=1)
    play_right(t, "a", 3)                                       # L0-01 taught, nothing else left today
    r = t.next("a")
    assert r["kind"] == "raju" and t.store.load("a").pending["mistake"] is False
    assert t.answer("a", NO_ERROR)["verdict"] == "correct"


def test_changing_a_correct_line_is_a_false_alarm(tmp_path):
    t = tutor(tmp_path, new_per_day=1)
    play_right(t, "a", 3); t.next("a")
    item = t.items[t.store.load("a").pending["item"]][1]
    assert t.answer("a", item.raju_wrong)["verdict"] == "wrong"


# ---------- planner ----------
def test_planner_priority_and_no_back_to_back():
    rng = random.Random(0)
    st = {"a": "forgotten", "b": "learning", "c": "unknown", "d": "taught"}
    assert choose(st, rng, p_spot=0) == ("mistake", "a")
    st["a"] = "taught"
    assert choose(st, rng, p_spot=0) == ("followup", "b")
    st["b"] = "taught"
    assert choose(st, rng, p_spot=0) == ("mistake", "c")
    st["c"] = "taught"
    assert choose(st, rng, p_spot=0, can_learn_new=True) == ("lesson", None)
    kind, u = choose(st, rng, last_unit="a", p_spot=0)
    assert kind == "spot" and u != "a"


def test_new_lessons_per_day_limit_then_done(tmp_path):
    t = tutor(tmp_path, new_per_day=2, p_spot=0)
    kinds = []
    for _ in range(40):
        r = t.next("a"); kinds.append(r["kind"])
        if r["kind"] == "done":
            break
        a = t.answer("a", right_answer(t, "a"))
        while "followup" in a:
            a = t.answer("a", right_answer(t, "a"))
    assert kinds.count("lesson") == 2


def test_unsure_changes_nothing(tmp_path):
    t = tutor(tmp_path, p_spot=0)
    rec = t.store.load("a")
    for u in t.units:                                          # pretend every lesson up to L1-06 was had
        rec.mem(u.unit_id).introduced_at = rec.now(); rec.mem(u.unit_id).ready = True
    rec.raju = {"L1-06": "unknown"}
    rec.modules_done = [m.index for m in t.course.modules if "L1-06" not in m.units]; t.store.save(rec)
    t.next("a")
    a = t.answer("a", "मांग")                                   # a synonym the bank does not list
    assert a["verdict"] == "unsure" and t.store.load("a").raju["L1-06"] == "unknown"


# ---------- the leak filter: 5 checks ----------
@pytest.fixture
def ctx(tmp_path):
    t = tutor(tmp_path)
    item = t.items["L0-07-b"][1]                                # ఖ ; right ख ; Raju's mistake क
    seen = seen_telugu(t.units, [f"L0-{k:02d}" for k in range(1, 8)])
    return t, item, seen


def decide(t, item, seen, line, mistake=True, raju=None):
    claim = item.raju_wrong if mistake else item.accepted[0]
    return check_line(line, item, claim, mistake, t.units, raju or {"L0-07": "unknown"}, seen, "L0-07")


def test_template_lines_pass(ctx):
    t, item, seen = ctx
    assert decide(t, item, seen, "मुझे लगता है ఖ = क … सही है?").ok


@pytest.mark.parametrize("line,reason", [
    ("मुझे लगता है ఖ = क … और జ?", "UNSEEN_TELUGU"),           # జ: lesson L0-04 not had yet
    ("मुझे लगता है ఖ = ग … सही है?", "NOT_ONE_CLAIM"),          # wrong claim
    ("ఖ = क और క = क ?", "NOT_ONE_CLAIM"),                        # a second claim
    ("ఖ = क … या ఖ = ख ?", "ANSWER_LEAK"),                        # gives the right answer away
    ("ఖ = क क्योंकि ह की आवाज़ नहीं", "EXPLANATION"),              # explains
    ("I think ఖ = क", "FORMAT"),                                   # English
])
def test_each_leak_is_blocked(ctx, line, reason):
    t, item, seen = ctx
    d = decide(t, item, seen, line)
    assert not d.ok and reason in d.reasons, d.reasons


def test_raju_cannot_state_a_correct_form_he_was_not_taught(ctx):
    t, item, seen = ctx
    d = decide(t, item, seen, "ఖ = ख … सही है?", mistake=False, raju={"L0-07": "unknown"})
    assert "UNKNOWN_UNIT" in d.reasons


class LeakyModel:
    name = "leaky"
    def __init__(self): self.calls = 0
    def draft(self, prompt, claim, mistake, feedback="", **_):
        self.calls += 1
        return f"{prompt} = {claim}, पर असल में {prompt} = ख क्योंकि नियम है"


class GoodModel:
    name = "good"
    def draft(self, prompt, claim, mistake, feedback="", **_):
        return f"यार, {prompt} = {claim} ना?"


class DownModel:
    name = "down"
    def draft(self, *a, **k):
        raise TimeoutError("server not reachable")


def test_a_leaky_model_never_reaches_the_learner(ctx):
    t, item, seen = ctx
    m = LeakyModel()
    line, source, rejected, calls = raju_line(m, TemplateWriter(random.Random(0)), item, "क", True,
                                              t.units, {"L0-07": "unknown"}, seen, "L0-07")
    assert source == "template" and calls == 3 and len(rejected) == 3
    assert "ख" not in line


def test_a_good_model_line_is_used(ctx):
    t, item, seen = ctx
    line, source, _, calls = raju_line(GoodModel(), TemplateWriter(), item, "क", True, t.units, {"L0-07": "unknown"}, seen, "L0-07")
    assert source == "model" and calls == 1 and line == "यार, ఖ = क ना?"


def test_model_server_down_falls_back_without_waiting(ctx):
    t, item, seen = ctx
    line, source, rejected, _ = raju_line(DownModel(), TemplateWriter(), item, "क", True, t.units, {}, seen, "L0-07")
    assert source == "template" and rejected[0]["reasons"][0].startswith("MODEL_ERROR")


def test_no_model_configured_means_templates(monkeypatch, tmp_path):
    monkeypatch.delenv("SETU_LLM_URL", raising=False)
    t = Tutor(Store(str(tmp_path)))
    assert t.writer.name == "template"


def test_spot_checks_are_capped_when_nothing_else_is_left(tmp_path):
    t = tutor(tmp_path, new_per_day=1, p_spot=0, max_variety=3)
    kinds = []
    for _ in range(20):
        r = t.next("a"); kinds.append(r["kind"])
        if r["kind"] == "done":
            break
        a = t.answer("a", right_answer(t, "a"))
        while "followup" in a:
            a = t.answer("a", right_answer(t, "a"))
    assert kinds[-1] == "done" and kinds.count("raju") <= 1 + 3     # 1 mistake turn + at most 3 spot checks
