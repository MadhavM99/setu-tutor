"""Didi (the AI teacher) and Raju's lesson-grounded lines. Fake models; the rules are real."""
import random
import pytest
from setu.bank import load_units
from setu.didi import Didi, UNSURE
from setu.leakfilter import check_didi, seen_telugu
from setu.memory import Store
from setu.tutor import Tutor
from setu.writer import ModelWriter

UNITS = load_units()
BY = {u.unit_id: u for u in UNITS}
SEEN = seen_telugu(UNITS, ["L0-01", "L0-07"])
PAIRS = {l.telugu: l.hindi for u in UNITS for l in u.lesson}


class Script:
    name = "script"

    def __init__(self, *lines):
        self.lines, self.prompts = list(lines), []

    def chat(self, system, user, **k):
        self.prompts.append(user)
        return self.lines.pop(0) if self.lines else "ठीक है"


# ---------- Didi's guard ----------
@pytest.mark.parametrize("text,reason", [
    ("ఖ = क है, याद रखो", "WRONG_PAIR"),               # wrong sound for a letter
    ("ఘ भी ऐसा ही दिखता है", "UNSEEN_TELUGU"),          # a letter not shown yet
    ("Kha has a line", "FORMAT"),
])
def test_didi_guard_blocks(text, reason):
    assert reason in check_didi(text, SEEN, PAIRS).reasons


def test_didi_guard_allows_a_correct_explanation():
    assert check_didi("ఖ = ख। नीचे बीच की छोटी लकीर साँस है, क में साँस डालो तो ख।", SEEN, PAIRS).ok


def test_hint_never_contains_the_answer():
    item = BY["L0-07"].items[1]                          # ఖ -> ख
    d = Didi(Script("जवाब ख है", "नीचे बीच की छोटी लकीर देखो — वो साँस है!"), UNITS)
    hint, src, rej = d.hint(BY["L0-07"], item, SEEN, ["L0-07"])
    assert src == "model" and "लकीर" in hint and "ANSWER_LEAK" in rej[0]["reasons"]


def test_didi_answers_from_the_lesson_and_says_unsure_when_she_cannot():
    d = Didi(Script("ఖ = ख। नीचे की लकीर साँस है।"), UNITS)
    ans, src, _ = d.ask(BY["L0-07"], "ఖ कैसे याद रखूँ?", SEEN, ["L0-07"])
    assert src == "model" and ans.startswith("ఖ = ख")
    assert "ఖ = ख" in d.llm.prompts[0] and "STUDENT'S QUESTION: ఖ कैसे याद रखूँ?" in d.llm.prompts[0]
    bad = Didi(Script("ఖ = क", "ఖ = क"), UNITS)
    assert bad.ask(BY["L0-07"], "?", SEEN, ["L0-07"]) [0] == UNSURE


# ---------- Raju sticks to the lesson ----------
def test_raju_mistake_prompt_has_the_lesson_shapes_but_not_the_answer(tmp_path):
    t = Tutor(Store(str(tmp_path)), seed=1, drill=False, course="singles")
    unit = BY["L0-07"]; item = unit.items[1]             # ఖ, Raju's mistake: क
    ctx = t._raju_context(unit, item, item.raju_wrong, True)
    import re
    assert unit.lesson[1].shape in ctx
    assert not re.search(r"(?<![\u0900-\u097F])ख(?![\u0900-\u097F])", ctx)                 # the answer is blanked
    assert "క" not in ctx                                                                      # no other Telugu
    assert "sounds 'क'" in ctx                                                                 # the partner card


def test_raju_lines_and_followups_come_from_the_model_with_lesson_context(tmp_path):
    model = Script(*(["दीदी ने लकीर बताई थी… पर ఆ = अ, है ना?"] + ["हम्म, पक्का?"] * 3
                     + ["ओह! घुमाव से लंबी आवाज़ — ఆ = आ!", "और ఆ = आ भी सही, है ना?", "वाह!"] * 3))
    t = Tutor(Store(str(tmp_path)), writer=ModelWriter(model, random.Random(0)), seed=3, drill=False, course="singles")
    t.next("a"); t.answer("a", t.by_id["L0-01"].check.accepted[0])
    r = t.next("a")
    assert r["kind"] == "raju" and "LESSON:" in model.prompts[0] and "TASK:" in model.prompts[0]
    assert all("cricket" not in p and "samosa" not in p for p in model.prompts)
