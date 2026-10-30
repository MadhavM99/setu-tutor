"""L0 letter practice and letter content (X-LAD-L0, P8b-04, R-INPUT; TS-L0-*)."""
import copy
import datetime as dt
from pathlib import Path

from setu.content import letters as L
from setu.content import validate
from setu.domain import letter_practice as LP
from setu.domain.normalise import TELU_TO_DEVA

CONTENT = Path(__file__).resolve().parents[2] / "content"
T0 = dt.datetime(2026, 11, 2, 9, tzinfo=dt.UTC)
LETTERS = [LP.LetterView(x["id"], x["telugu"], x["devanagari"], x["twin_label_hi"], x["group"], x["varnamala_order"])
           for x in L.build_letters()]


def test_letters_are_the_modern_set_in_varnamala_order_with_verified_twins():
    built = L.build_letters()
    assert len(built) == 48 and [x["varnamala_order"] for x in built] == list(range(1, 49))
    assert all(TELU_TO_DEVA[x["telugu"]] == x["devanagari"] for x in built)
    assert "ఌ" not in {x["telugu"] for x in built} and "ఴ" not in {x["telugu"] for x in built}
    assert {x["telugu"] for x in built if x["new_for_hindi"]} == {"ఎ", "ఒ", "ళ", "ఱ"}
    assert all(x["review_status"] == "draft" for x in built)


def letter_errors(tree):
    return [e.detail for e in validate.validate_tree(tree).errors if e.detail.startswith("te-letter:")]


def test_the_committed_letters_file_matches_the_generator_and_validates():
    tree = validate.load_tree(CONTENT)
    assert tree.letters_l0 == L.build_letters() and letter_errors(tree) == []


def test_a_wrong_twin_or_an_approval_claim_is_rejected():
    bad = copy.deepcopy(validate.load_tree(CONTENT))
    bad.letters_l0[0]["devanagari"] = "क"
    bad.letters_l0[1]["review_status"] = "approved"
    errors = letter_errors(bad)
    assert any(e.startswith(bad.letters_l0[0]["id"]) for e in errors)
    assert any(e.startswith(bad.letters_l0[1]["id"]) for e in errors)


def test_a_new_letter_runs_intro_choice_recognise_recall():
    t = LP.next_task(letters=LETTERS, cards=[], pending=None, now=T0, new_today=0, seed=7)
    assert (t.type, t.letter_id) == ("intro", "te-letter:అ")
    steps = [t.type]
    while t.chain:
        t = LP.next_task(letters=LETTERS, cards=[], pending=LP.after_answer(t, "correct"), now=T0, new_today=1, seed=7)
        steps.append(t.type)
    assert steps == ["intro", "choice", "recognise", "recall"] and not t.revealed


def test_choice_options_are_seeded_include_the_answer_and_prefer_the_same_group():
    pending = LP.Task("intro", "te-letter:క", chain=("choice",))
    a = LP.next_task(letters=LETTERS, cards=[], pending=pending, now=T0, new_today=0, seed=3)
    b = LP.next_task(letters=LETTERS, cards=[], pending=pending, now=T0, new_today=0, seed=3)
    assert a == b and "te-letter:క" in a.options and len(a.options) == 4
    assert all(o in {"te-letter:" + c for c in "కఖగఘఙ"} for o in a.options)


def test_after_a_wrong_answer_the_rest_of_the_chain_is_after_reveal():
    t = LP.Task("choice", "te-letter:అ", chain=("recognise", "recall"))
    nxt = LP.next_task(letters=LETTERS, cards=[], pending=LP.after_answer(t, "wrong"), now=T0, new_today=1, seed=1)
    assert nxt.type == "recognise" and nxt.revealed


def test_due_reviews_come_before_new_letters_and_new_letters_are_capped():
    cards = [LP.CardView("te-letter:అ", "RCL", T0 - dt.timedelta(hours=1)),
             LP.CardView("te-letter:ఆ", "REC", T0 + dt.timedelta(days=2))]
    due = LP.next_task(letters=LETTERS, cards=cards, pending=None, now=T0, new_today=0, seed=1)
    assert (due.type, due.letter_id) == ("recall", "te-letter:అ")
    fresh = LP.next_task(letters=LETTERS, cards=cards[1:], pending=None, now=T0, new_today=0, seed=1)
    assert (fresh.type, fresh.letter_id) == ("intro", "te-letter:అ")  # ఆ is seen, not due
    assert LP.next_task(letters=LETTERS, cards=cards[1:], pending=None, now=T0, new_today=5, seed=1) is None


def test_no_approved_letters_means_no_task():
    assert LP.next_task(letters=[], cards=[], pending=None, now=T0, new_today=0, seed=1) is None


# ---------------------------------------------------------------- L1 aksharas (slice S2)

from setu.content import aksharas as A

AKSHARAS = [LP.UnitView(x["id"], x["telugu"], x["devanagari"], x["twin_label_hi"], x["group"], x["order"],
                        confusable=x["letters"][0]) for x in A.build_aksharas()]
AKSH = {x.id: x for x in AKSHARAS}


def test_aksharas_have_bridge_twins_and_known_letters():
    built = A.build_aksharas()
    assert len({x["id"] for x in built}) == len(built) == 489
    assert all(x["devanagari"] == "".join(TELU_TO_DEVA[ch] for ch in x["telugu"]) for x in built)
    letters = {x["telugu"] for x in L.build_letters()}
    assert all(set(x["letters"]) <= letters for x in built)
    by = {x["telugu"]: x for x in built}
    assert by["కా"]["devanagari"] == "का" and by["కె"]["devanagari"] == "कॆ" and by["కం"]["family"] == "nasal_visarga"
    assert by["క్క"]["kind"] == "double" and by["క్ష"]["letters"] == ["క", "ష"]
    assert not any(ch in x["telugu"] for x in built for ch in "ఙఞఱ")
    assert [x["order"] for x in built] == list(range(1, 490)) and built[0]["group"] == "sign-aa"


def test_the_committed_aksharas_file_matches_the_generator_and_validates():
    tree = validate.load_tree(CONTENT)
    assert tree.aksharas == A.build_aksharas()
    assert [e.detail for e in validate.validate_tree(tree).errors if e.detail.startswith("te-akshara:")] == []


def test_an_akshara_with_a_wrong_twin_or_unknown_letter_is_rejected():
    bad = copy.deepcopy(validate.load_tree(CONTENT))
    bad.aksharas[0]["devanagari"] = "की"
    bad.aksharas[1]["letters"] = ["ఌ"]
    errors = [e.detail for e in validate.validate_tree(bad).errors]
    assert any(e.startswith(bad.aksharas[0]["id"]) for e in errors)
    assert any(e.startswith(bad.aksharas[1]["id"]) for e in errors)


def test_only_the_first_akshara_of_a_sign_gets_an_intro():
    first = LP.next_task(letters=AKSHARAS, cards=[], pending=None, now=T0, new_today=0, seed=1, intro_per_group=True)
    assert (first.type, first.letter_id) == ("intro", "te-akshara:కా")
    seen = [LP.CardView("te-akshara:కా", "RCL", T0 + dt.timedelta(days=1))]
    nxt = LP.next_task(letters=AKSHARAS, cards=seen, pending=None, now=T0, new_today=1, seed=1, intro_per_group=True)
    assert (nxt.type, nxt.letter_id, nxt.chain) == ("choice", "te-akshara:ఖా", ("recognise", "recall"))


def test_akshara_distractors_are_the_same_consonant_with_other_signs():
    t = LP.next_task(letters=AKSHARAS, cards=[], pending=LP.Task("intro", "te-akshara:కి", chain=("choice",)),
                     now=T0, new_today=0, seed=5)
    assert "te-akshara:కి" in t.options and len(t.options) == 4
    assert all(AKSH[o].confusable == "క" for o in t.options)
