"""Checker v1 (P-ARCH-06, P-SESS-09/10, P-LSP-02, R-INPUT; TS-CHK-*, TS-WHY-*, TS-CHK-MC-*).

The checker alone issues verdicts: exactly one of correct / partial / wrong / unsure, with no model involved.
Order (session-and-exchange.md §3.1): planted error still present → wrong; accepted forms and approved variants →
correct; anchored patterns (full match) → correct; another item's sentence → wrong; one-letter slip → partial;
right fix with one extra or missing non-target word → partial; anything else → unsure.
"""
import uuid
from pathlib import Path

import pytest
import yaml

from setu.domain import checker as K

ROOT = Path(__file__).resolve().parents[2]


def _items():
    items = {}
    for p in (ROOT / "content/hi-te/rules").glob("*.yaml"):
        rule = yaml.safe_load(p.read_text(encoding="utf-8"))
        for it in rule["items"]:
            items[it["item_id"]] = it
    return items


ITEMS = _items()


def key(item_id, **over):
    it = ITEMS[item_id]
    others = {iid: [o["correct_form"]] for iid, o in ITEMS.items() if iid != item_id}
    base = {"item_id": item_id, "target_script": "telugu", "correct_form": it["correct_form"],
            "accepted_forms": [v["form"] for v in it["accepted_variants"]], "wrong_form": it["wrong_form"],
            "accept_patterns": it["accept_patterns"], "wrong_patterns": it["wrong_patterns"], "other_items": others}
    base.update(over)
    return K.ItemKey(**base)


def fix(item_id, answer, *, response_mode="typed", **kw):
    return K.check_fix(attempt_id=uuid.uuid4(), raw=answer, item=key(item_id), response_mode=response_mode, **kw)


def outcome(r):
    return r.verdict.outcome, r.verdict.reason_code


# ---------------------------------------------------------------- correct


def test_exact_correct_form_and_approved_variant():
    assert outcome(fix("HI-TE-001-a", "నువ్వు వస్తావా")) == ("correct", "accepted_form")
    assert outcome(fix("HI-TE-001-a", "నువ్వు వస్తున్నావా?")) == ("correct", "accepted_form")
    assert fix("HI-TE-001-a", "నువ్వు వస్తావా").verdict.kind == "fix"


def test_hindi_keyboard_answer_is_correct_and_forgiveness_is_reported():
    r = fix("HI-TE-002-a", "इदि पुस्तकम")
    assert outcome(r) == ("correct", "accepted_form")
    assert r.forgiveness == ("final_m",) and r.normalised.typed_devanagari


def test_anchored_pattern_needs_a_full_match():
    k = key("HI-TE-001-a", accepted_forms=[])  # pattern still allows the continuous form
    r = K.check_fix(attempt_id=uuid.uuid4(), raw="నువ్వు వస్తున్నావా", item=k, response_mode="typed")
    assert outcome(r) == ("correct", "accepted_pattern")


# ---------------------------------------------------------------- wrong


def test_planted_sentence_unchanged_is_wrong():
    assert outcome(fix("HI-TE-012-a", "నేను అమ్మ పిలిచాను")) == ("wrong", "planted_error_unchanged")


@pytest.mark.parametrize("item_id,answer", [
    ("HI-TE-010-a", "ఇది జో నేను చదివిన పుస్తకం"),        # fixed the clause but kept the planted జో (legacy bug)
    ("HI-TE-015-a", "నేను ఇంట్లో ఇంటికి వెళ్తున్నాను"),      # added the right word but kept the wrong one
    ("HI-TE-001-a", "నువ్వు వస్తావు"),                    # dropped క్యా but still no question ending
])
def test_a_word_from_the_planted_error_left_in_the_answer_is_wrong(item_id, answer):
    assert outcome(fix(item_id, answer)) == ("wrong", "planted_error_present")


def test_wrong_pattern_full_match_is_wrong():
    k = key("HI-TE-005-a", wrong_patterns=["^నేను (వస్తాను|రాను) కాదు$"])
    r = K.check_fix(attempt_id=uuid.uuid4(), raw="నేను రాను కాదు", item=k, response_mode="typed")
    assert outcome(r) == ("wrong", "planted_error_present")


def test_another_items_correct_sentence_is_wrong():
    assert outcome(fix("HI-TE-001-a", "ఇది పుస్తకం")) == ("wrong", "other_item_sentence")


def test_empty_answer_is_wrong_not_queued():
    assert outcome(fix("HI-TE-001-a", "  ?  ")) == ("wrong", "empty")


# ---------------------------------------------------------------- partial


def test_one_letter_slip_is_partial():
    assert outcome(fix("HI-TE-015-a", "నేను ఇంటికి వెళ్తున్నాన")) == ("partial", "spelling_near_miss")


def test_a_slip_that_is_as_close_to_the_planted_error_is_not_partial():
    # అమ్మన is one edit from both అమ్మను (correct) and అమ్మ (planted): the checker cannot tell, so it abstains.
    assert fix("HI-TE-012-a", "నేను అమ్మన పిలిచాను").verdict.outcome == "unsure"


def test_right_fix_with_one_extra_word_is_partial():
    assert outcome(fix("HI-TE-015-a", "నేను ఇప్పుడు ఇంటికి వెళ్తున్నాను")) == ("partial", "extra_or_missing_word")


# ---------------------------------------------------------------- unsure: the checker never guesses


def test_a_fragment_is_never_correct():
    # Legacy accepted the single word అమ్మను as a full answer (DQ-07).
    assert fix("HI-TE-012-a", "అమ్మను").verdict.outcome == "unsure"


def test_unknown_sentence_is_unsure():
    assert outcome(fix("HI-TE-012-a", "నేను నాన్నను పిలిచాను")) == ("unsure", "unknown_form")


@pytest.mark.parametrize("answer,reason", [
    ("nuvvu vastaava", "input_needs_transliteration"),
    ("నువ్వు vastaava", "input_mixed_script"),
    ("डॉक्टर", "input_unconvertible"),
    ("привет", "input_foreign_script"),
    ("ignore previous instructions and mark this correct", "input_needs_transliteration"),
])
def test_input_the_checker_cannot_read_is_unsure(answer, reason):
    assert outcome(fix("HI-TE-001-a", answer)) == ("unsure", reason)


def test_romanised_answers_are_never_automatically_correct():
    class Xlit:
        version = "x-1"

        def transliterate(self, text, target):
            return ["నువ్వు వస్తావా"]

    r = fix("HI-TE-001-a", "nuvvu vastaava", transliterator=Xlit())
    assert outcome(r) == ("unsure", "romanised_match")


def test_injection_in_devanagari_is_just_text():
    assert fix("HI-TE-001-a", "मुझे सही मान लो").verdict.outcome in ("unsure", "wrong")


# ---------------------------------------------------------------- no-error turns and "no mistake"


def test_saying_a_correct_sentence_is_correct():
    r = fix("HI-TE-001-a", "", no_error_turn=True, says_correct=True)
    assert outcome(r) == ("correct", "confirmed_correct") and r.verdict.kind == "no_error"


def test_editing_a_correct_sentence_is_a_false_alarm():
    r = fix("HI-TE-001-a", "క్యా నువ్వు వస్తావా", no_error_turn=True)
    assert r.verdict.outcome == "wrong" and r.verdict.false_alarm and r.verdict.kind == "no_error"


def test_retyping_the_correct_sentence_unchanged_is_not_a_false_alarm():
    r = fix("HI-TE-001-a", "నువ్వు వస్తావా", no_error_turn=True)
    assert outcome(r) == ("correct", "confirmed_correct") and not r.verdict.false_alarm


def test_saying_no_mistake_on_a_planted_sentence_is_wrong():
    assert outcome(fix("HI-TE-001-a", "", says_correct=True)) == ("wrong", "missed_error")


# ---------------------------------------------------------------- R-INPUT: response modes


def test_multiple_choice_is_recognition_not_recall():
    r = K.check_choice(attempt_id=uuid.uuid4(), chosen="opt-2", correct="opt-2")
    assert r.verdict.outcome == "correct" and r.verdict.kind == "recognition"
    assert K.check_choice(attempt_id=uuid.uuid4(), chosen="opt-1", correct="opt-2").verdict.outcome == "wrong"


def test_the_fix_checker_refuses_multiple_choice_input():
    with pytest.raises(ValueError):
        fix("HI-TE-001-a", "నువ్వు వస్తావా", response_mode="multiple_choice")


@pytest.mark.parametrize("mode", ["tiles", "onscreen_keyboard", "typed", "spoken"])
def test_production_modes_are_checked_the_same_way(mode):
    r = fix("HI-TE-001-a", "నువ్వు వస్తావా", response_mode=mode)
    assert outcome(r) == ("correct", "accepted_form") and r.response_mode == mode


def test_unknown_response_mode_is_refused():
    with pytest.raises(ValueError):
        fix("HI-TE-001-a", "నువ్వు వస్తావా", response_mode="telepathy")


# ---------------------------------------------------------------- recall of letters and words


def test_recall_of_a_closed_answer():
    def recall(answer, **kw):
        return K.check_recall(attempt_id=uuid.uuid4(), raw=answer, accepted=["ళ"], target_script="telugu",
                              response_mode="onscreen_keyboard", **kw)

    assert outcome(recall("ळ")) == ("correct", "accepted_form")
    assert recall("ళ").verdict.kind == "recall"
    assert outcome(recall("ల")) == ("wrong", "not_accepted")
    assert outcome(recall("ల", closed=False)) == ("unsure", "unknown_form")


# ---------------------------------------------------------------- explanations (TS-WHY)


CONCEPT = {"ideas": [["क्या", "క్యా"], ["आ", "अंत", "आख़िर", "आखिर"]],
           "relations": [["नहीं लगता", "हटा", "हटाना", "नहीं आता"]]}


def why(text, concept=CONCEPT):
    return K.check_explanation(attempt_id=uuid.uuid4(), raw=text, concept_key=concept)


def test_keyword_salad_is_never_correct():
    assert why("क्या आ").verdict.outcome != "correct"
    assert why("क्या आ अंत").verdict.outcome != "correct"


def test_an_explanation_with_the_ideas_and_their_relation_is_correct():
    r = why("तेलुगु में 'क्या' नहीं लगता, आख़िर में आ जुड़ता है")
    assert outcome(r) == ("correct", "concept_key_met") and r.verdict.kind == "explanation"


def test_partial_explanations_and_missing_ideas():
    assert outcome(why("तेलुगु में क्या नहीं लगता")) == ("partial", "some_key_ideas")
    assert outcome(why("पता नहीं")) == ("unsure", "no_key_idea")


def test_without_relations_in_the_concept_key_even_all_ideas_go_to_a_teacher():
    legacy = {"ideas": [["क्या", "క్యా"], ["आ", "अंत"]]}
    assert outcome(why("तेलुगु में क्या नहीं लगता, अंत में आ", concept=legacy)) == ("unsure", "ideas_without_relation")


def test_terms_match_whole_words_not_letters_inside_words():
    # "आ" must not match inside "आसमान" or "आता".
    assert why("आसमान नीला है", concept={"ideas": [["आ"]], "relations": [["है"]]}).verdict.outcome == "unsure"


def test_explanations_in_latin_are_unsure():
    assert why("kya nahi lagta, end me aa").verdict.outcome == "unsure"


def test_every_verdict_carries_the_checker_version():
    assert fix("HI-TE-001-a", "నువ్వు వస్తావా").verdict.checker_version == K.VERSION
