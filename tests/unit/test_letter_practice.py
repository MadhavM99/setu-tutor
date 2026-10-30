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
