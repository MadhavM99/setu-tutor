"""The course: chapters -> modules -> numbered lessons; each module ends with a Raju lesson on that module only."""
import random
from setu.bank import load_units
from setu.checker import NO_ERROR
from setu.course import load_course
from setu.memory import Store
from setu.tutor import Tutor
from setu.writer import TemplateWriter


def tutor(tmp_path, **kw):
    return Tutor(Store(str(tmp_path)), writer=TemplateWriter(random.Random(0)), seed=1, drill=False, p_spot=0, **kw)


def right(t, lid="a"):
    p = t.store.load(lid).pending
    if p["kind"] == "check":
        return t.items[p["item"]][1].accepted[0]
    if p["kind"] == "raju":
        return t.items[p["item"]][1].accepted[0] if p["mistake"] else NO_ERROR
    fu = t._fus(t.store.load(lid), t.by_id[p["unit"]])[p["idx"]]
    return NO_ERROR if fu.sentence_is_correct else fu.item.accepted[0]


def run(t, n, lid="a"):
    """Play n turns correctly; return the steps seen."""
    seen = []
    for _ in range(n):
        r = t.next(lid)
        if r["kind"] == "done":
            seen.append(("done", None, None)); break
        seen.append((r["kind"], r["step"]["no"], r["unit"]))
        a = t.answer(lid, right(t, lid))
        while "followup" in a:
            seen.append(("followup", a["followup"]["step"]["no"], a["followup"]["unit"]))
            a = t.answer(lid, right(t, lid))
    return seen


def test_course_map_numbers_lessons_and_closes_each_module_with_raju():
    c = load_course(load_units())
    m1 = c.modules[0]
    assert [(s.no, s.kind) for s in m1.steps] == [("1.1", "lesson"), ("1.2", "lesson"), ("1.3", "lesson"), ("1.4", "raju")]
    assert c.modules[1].steps[0].no == "1.5"
    words = next(m for m in c.modules if m.chapter == 2)
    assert words.steps[0].no == "2.1" and words.chapter_title == "शब्द"


def test_three_lessons_then_raju_only_on_those_then_module_two(tmp_path):
    t = tutor(tmp_path, new_per_day=10)
    seen = run(t, 20)
    kinds = [k for k, _, _ in seen]
    first_raju = kinds.index("raju")
    assert [s[1] for s in seen[:3]] == ["1.1", "1.2", "1.3"] and first_raju == 3      # no Raju before 1.4
    raju_part = [s for s in seen if s[0] in ("raju", "followup") and s[1] == "1.4"]
    assert raju_part and {u for _, _, u in raju_part} <= {"L0-01", "L0-02", "L0-03"}  # only module 1
    m2 = next(i for i, s in enumerate(seen) if s[1] == "1.5")
    assert all(s[1] == "1.4" for s in seen[first_raju:m2])                         # Raju lesson until module done
    assert t.store.load("a").modules_done[0] == 0


def test_module_done_is_announced_once(tmp_path):
    t = tutor(tmp_path, new_per_day=10)
    for _ in range(3):
        t.next("a"); t.answer("a", right(t))
    done = None
    for _ in range(30):
        r = t.next("a")
        a = t.answer("a", right(t))
        while "followup" in a and "module_done" not in a:
            a = t.answer("a", right(t))
        if "module_done" in a:
            done = a["module_done"]; break
    assert done == {"module": "Module 1 · स्वर (1)", "chapter": "अध्याय 1 · अक्षर", "next": "Module 2 · स्वर (2)"}


def test_daily_limit_stops_new_lessons_but_not_the_raju_lesson(tmp_path):
    t = tutor(tmp_path, new_per_day=3)
    seen = run(t, 40)
    assert "1.5" not in {s[1] for s in seen}                                   # 3 new lessons a day
    assert t.store.load("a").modules_done == [0]                               # but module 1 could be finished


def test_forgotten_lesson_of_a_finished_module_is_revised_first(tmp_path):
    t = tutor(tmp_path, new_per_day=10)
    run(t, 20)
    t.skip_days("a", 30)                                                       # everything is forgotten
    r = t.next("a")
    assert r["kind"] == "raju" and r["step"]["no"] == "🔁" and r["unit"] in {"L0-01", "L0-02", "L0-03"}


def test_course_map_states(tmp_path):
    t = tutor(tmp_path)
    t.next("a"); t.answer("a", right(t))
    o = t.course_map("a")
    m1, m2 = o["chapters"][0]["modules"][:2]
    assert [s["state"] for s in m1["steps"]] == ["done", "open", "open", "locked"] and m2["state"] == "locked"
    assert o["chapters"][1]["state"] == "locked" and o["learned"] == 1 and o["total"] == 45
