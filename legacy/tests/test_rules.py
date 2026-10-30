"""The paper's core loop on the team's rule bank (paper §5, §6.2): learn a rule in a scene -> check ->
Raju writes the planted Hindi-speaker mistake -> learner fixes it (Hindi keyboard is fine) -> explains WHY
(scored on key ideas, no model) -> fixes the rule's other sentence -> Raju knows the rule."""
import random
import pytest
from setu.bank import load_units, all_items
from setu.checker import NO_ERROR, check, check_why
from setu.course import load_course
from setu.didi import Didi
from setu.leakfilter import check_line, seen_telugu
from setu.memory import Store
from setu.text import deva_to_telugu, telugu_to_deva
from setu.tutor import Tutor
from setu.writer import TemplateWriter

UNITS = load_units()
RULES = [u for u in UNITS if u.level == 3]
ITEMS = all_items(UNITS)


def test_the_team_rule_bank_is_loaded_with_hindi_explanations():
    assert len(RULES) == 15 and sum(len(u.items) for u in RULES) == 29
    for u in RULES:
        assert u.title and u.tip and len(u.key_ideas) >= 2 and u.status == "draft_unverified"
        for it in u.items:
            assert check(it, it.accepted[0]).verdict == "correct", it.item_id
            assert check(it, it.raju_wrong).verdict == "wrong", it.item_id                  # the planted mistake


@pytest.mark.parametrize("u", RULES, ids=lambda u: u.unit_id)
def test_every_right_sentence_can_be_typed_on_a_hindi_keyboard(u):
    for it in u.items:
        typed = telugu_to_deva(it.accepted[0]).replace("ॆ", "े").replace("ॊ", "ो")       # what the reading aid shows
        assert check(it, typed).verdict == "correct", (it.item_id, typed)


def test_scenes_chapter_holds_every_rule_once():
    c = load_course(UNITS)
    scenes = [m for m in c.modules if m.chapter == 3]
    assert [m.title for m in scenes][:3] == ["🛺 ऑटो स्टैंड", "🍛 मेस में", "🏠 मकान-मालिक"]
    assert sorted(u for m in scenes for u in m.units) == sorted(u.unit_id for u in RULES)
    assert all(m.scene for m in scenes) and scenes[0].steps[-1].no == "3.4"


@pytest.mark.parametrize("rid,answer,verdict", [
    ("HI-TE-001", "पता नहीं", "wrong"),
    ("HI-TE-001", "telugu में क्या नहीं लगता, आख़िर में आ जोड़ते हैं", "correct"),
    ("HI-TE-002", "telugu में है (ఉంది) नहीं लगाते", "correct"),
    ("HI-TE-006", "మనం में सुनने वाला भी शामिल है", "correct"),
])
def test_why_is_scored_on_key_ideas(rid, answer, verdict):
    assert check_why(next(u for u in RULES if u.unit_id == rid).key_ideas, answer).verdict == verdict


def test_raju_sentence_lines_keep_to_the_learners_words_and_never_give_the_answer():
    item = ITEMS["HI-TE-001-a"][1]                         # planted: క్యా నువ్వు వస్తావు ; right: నువ్వు వస్తావా
    seen = seen_telugu(UNITS, [u.unit_id for u in UNITS])
    words = {"నువ్వు", "వస్తావా", "ఇది", "పుస్తకమా"}
    ok = check_line("मुझे कहना था “क्या तुम आ रहे हो”, तो मैंने लिखा: క్యా నువ్వు వస్తావు — ठीक?", item, item.raju_wrong,
                    True, UNITS, {}, seen, "HI-TE-001", words)
    assert ok.ok, ok.reasons
    leak = check_line("“क्या तुम आ रहे हो” = క్యా నువ్వు వస్తావు या వస్తావా?", item, item.raju_wrong, True, UNITS, {},
                      seen, "HI-TE-001", words)
    assert "ANSWER_LEAK" in leak.reasons
    unseen = check_line("“क्या तुम आ रहे हो” = క్యా నువ్వు వస్తావు, అమ్మా?", item, item.raju_wrong, True, UNITS, {},
                        seen, "HI-TE-001", words)
    assert "UNSEEN_TELUGU" in unseen.reasons                                              # TMR must be 0


def test_coach_hint_for_a_sentence_never_has_an_answer_word():
    class Leaky:
        name = "x"
        def __init__(self): self.n = 0
        def chat(self, *a, **k):
            self.n += 1
            return "आख़िर में వస్తావా लिखो" if self.n == 1 else "Hindi में सवाल 'क्या' से शुरू होता है; Telugu में आख़िर देखो।"
    d = Didi(Leaky(), UNITS)
    unit = next(u for u in RULES if u.unit_id == "HI-TE-001")
    hint, src, rej = d.hint(unit, unit.items[0], seen_telugu(UNITS, [u.unit_id for u in UNITS]), [unit.unit_id])
    assert src == "model" and "ANSWER_LEAK" in rej[0]["reasons"] and "వస్తావా" not in hint


def test_engine_hint_for_a_sentence_names_the_rule_not_the_answer(tmp_path):
    t = Tutor(Store(str(tmp_path)), drill=False)
    unit = t.by_id["HI-TE-001"]
    h = t._hint(unit, unit.items[0])
    assert unit.title in h and "వస్తావా" not in h


def play(t, lid):
    p = t.store.load(lid).pending
    while p and p["kind"] == "drill":
        t.answer(lid, t.items[p["queue"][0]][1].accepted[0]); p = t.store.load(lid).pending
    if p and p["kind"] == "check":
        t.answer(lid, t.by_id[p["unit"]].check.accepted[0])


def test_the_whole_loop_for_one_scene(tmp_path):
    t = Tutor(Store(str(tmp_path)), writer=TemplateWriter(random.Random(0)), seed=4, new_per_day=10, p_spot=0)
    scene = next(m for m in t.course.modules if m.chapter == 3)
    t.jump_to("a", scene.index)
    for no in ("3.1", "3.2", "3.3"):                       # three rule lessons first, no Raju yet
        r = t.next("a"); assert r["kind"] == "lesson" and r["step"]["no"] == no
        play(t, "a")
    r = t.next("a")
    assert r["kind"] == "raju" and r["step"]["no"] == "3.4" and r["unit"] in scene.units
    item = t.items[t.store.load("a").pending["item"]][1]
    assert item.kind == "sentence" and item.raju_wrong in r["raju"] and item.accepted[0] not in r["raju"]
    a = t.answer("a", telugu_to_deva(item.accepted[0]).replace("ॆ", "े").replace("ॊ", "ो"))   # fixed, Hindi keyboard
    assert a["verdict"] == "correct" and "क्यों" in a["followup"]["raju"]                       # then: WHY?
    a = t.answer("a", "पता नहीं")
    assert a["verdict"] == "wrong"
    unit = t.by_id[r["unit"]]
    a = t.answer("a", " ".join(g[0] for g in unit.key_ideas))                                  # a real explanation
    assert a["verdict"] == "correct" and "followup" in a                                        # then the other sentence
    fu = t._fus(t.store.load("a"), unit)[1]
    a = t.answer("a", NO_ERROR if fu.sentence_is_correct else fu.item.accepted[0])
    assert a["verdict"] == "correct" and t.store.load("a").raju[unit.unit_id] == "taught"
