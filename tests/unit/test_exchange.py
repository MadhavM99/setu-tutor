"""Correction exchange steps, hints, own-sentence rules and the own-sentence checker (slice S5; TS-EXCH-*,
TS-COACH-*, TS-OWN-*, P-SESS-07..11, P8b-02, R-INPUT)."""
import uuid

import pytest

from setu.domain import checker
from setu.domain import exchange as X

ITEM = checker.ItemKey(item_id="HI-TE-001-a", target_script="telugu", correct_form="నువ్వు వస్తావా",
                       accepted_forms=("నువ్వు వస్తున్నావా",), wrong_form="క్యా నువ్వు వస్తావు")


def a(n, outcome, kind="fix"):
    return X.Answer(n, kind, outcome)


# ---------------------------------------------------------------- the step ladder


def test_a_fresh_exchange_asks_for_the_first_cue_free_answer():
    s = X.step("planted", [], why_due=False)
    assert (s.name, s.n, s.revealed) == ("answer", 1, False)


def test_a_first_miss_gets_a_hint_and_a_second_miss_shows_the_answer_for_copying():
    assert X.step("planted", [a(1, "wrong")], why_due=False).name == "hint"
    assert X.step("planted", [a(1, "partial")], why_due=False).n == 2
    copy = X.step("planted", [a(1, "wrong"), a(2, "wrong")], why_due=False)
    assert (copy.name, copy.n, copy.revealed) == ("copy", 3, True)
    assert X.step("planted", [a(1, "wrong"), a(2, "wrong"), a(3, "wrong")], why_due=False).name == "close"


def test_own_sentences_use_the_same_ladder():
    assert X.step("own", [a(1, "wrong", "own")], why_due=False).name == "hint"
    assert X.step("own", [a(1, "wrong", "own"), a(2, "partial", "own")], why_due=False).name == "copy"


def test_a_correct_answer_closes_and_unsure_closes_without_a_hint():
    assert X.step("planted", [a(1, "correct")], why_due=False).name == "close"
    assert X.step("planted", [a(1, "wrong"), a(2, "correct")], why_due=True).name == "close"  # hinted: no why
    assert X.step("planted", [a(1, "unsure")], why_due=False).name == "close"


def test_why_follows_a_due_cue_free_correct_fix_only_and_then_the_exchange_closes():
    why = X.step("planted", [a(1, "correct")], why_due=True)
    assert (why.name, why.n) == ("why", 2)
    assert X.step("planted", [a(1, "correct"), a(2, "unsure", "explanation")], why_due=True).name == "close"
    assert X.step("own", [a(1, "correct", "own")], why_due=True).name == "close"
    assert X.step("no_error", [a(1, "correct", "no_error")], why_due=True).name == "close"


def test_a_false_alarm_on_a_no_error_turn_closes_with_the_sentence_shown():
    s = X.step("no_error", [a(1, "wrong", "no_error")], why_due=False)
    assert s.name == "close"


@pytest.mark.parametrize("count,due", [(0, False), (1, False), (2, False), (3, True), (4, False), (6, True)])
def test_why_is_asked_after_every_third_checked_correct_fix(count, due):
    assert X.asks_why(count) is due


# ---------------------------------------------------------------- hints (fixed, never the answer)


def test_the_first_approved_hint_without_the_answer_is_used():
    hints = [("recast", "आख़िरी शब्द देखिए।"), ("l1_rule", "सवाल के लिए ఆ")]
    assert X.choose_hint(hints, ITEM) == ("recast", "आख़िरी शब्द देखिए।")


def test_a_hint_that_contains_the_answer_is_never_served():
    leaky = [("recast", "లిఖిए: నువ్వు వస్తావా"), ("l1_rule", "वस्तावा लिखिए")]
    assert X.choose_hint(leaky, ITEM) == ("generic", None)
    assert X.choose_hint([], ITEM) == ("generic", None)


def test_the_hint_type_arm_serves_only_that_type():
    hints = [("recast", "आख़िरी शब्द देखिए।"), ("contrast", "हिंदी में सवाल का शब्द शुरू में आता है।")]
    assert X.choose_hint(hints, ITEM, only="contrast")[0] == "contrast"
    assert X.choose_hint(hints, ITEM, only="l1_rule") == ("generic", None)


# ---------------------------------------------------------------- which rule an own sentence is about


def test_own_turns_introduce_unseen_rules_up_to_the_cap_then_practise_seen_ones():
    rules = [X.OwnRule("HI-TE-002", ready=False, seen=False), X.OwnRule("HI-TE-001", ready=False, seen=False),
             X.OwnRule("HI-TE-003", ready=True, seen=True)]
    assert X.own_rule(rules, new_this_session=0, seed=1, turn=0) == ("HI-TE-001", True)
    assert X.own_rule(rules, new_this_session=X.NEW_RULES_PER_SESSION, seed=1, turn=0) == ("HI-TE-003", False)
    assert X.own_rule([X.OwnRule("HI-TE-001", False, False)], new_this_session=2, seed=1, turn=0) is None


def test_own_rule_choice_is_seeded():
    rules = [X.OwnRule(f"HI-TE-00{i}", ready=True, seen=True) for i in range(1, 6)]
    assert X.own_rule(rules, new_this_session=9, seed=4, turn=2) == X.own_rule(rules, new_this_session=9, seed=4,
                                                                               turn=2)


def test_an_item_is_not_repeated_right_after_itself_when_another_exists():
    items = [X.ItemView("HI-TE-001-a", uuid.uuid4(), "HI-TE-001"), X.ItemView("HI-TE-001-b", uuid.uuid4(), "HI-TE-001"),
             X.ItemView("HI-TE-002-a", uuid.uuid4(), "HI-TE-002")]
    for seed in range(20):
        assert X.pick_item(items, "HI-TE-001", last_item="HI-TE-001-a", seed=seed, turn=0).item_id == "HI-TE-001-b"
    only = items[2:]
    assert X.pick_item(only, "HI-TE-002", last_item="HI-TE-002-a", seed=0, turn=0).item_id == "HI-TE-002-a"
    assert X.pick_item(items, "HI-TE-009", last_item=None, seed=0, turn=0) is None


# ---------------------------------------------------------------- the own-sentence checker


def own(raw, mode="typed"):
    return checker.check_own(attempt_id=uuid.uuid4(), raw=raw, item=ITEM, response_mode=mode).verdict


def test_an_own_sentence_matching_an_accepted_form_is_correct_own_evidence():
    v = own("నువ్వు వస్తున్నావా")
    assert (v.outcome, v.kind, v.reason_code) == ("correct", "own", "accepted_form")


def test_an_own_sentence_with_the_hindi_habit_is_wrong_and_flagged_as_the_planted_error():
    assert own("క్యా నువ్వు వస్తావా").reason_code == "planted_error_present"
    assert own("క్యా నువ్వు వస్తావు").outcome == "wrong"


def test_an_unseen_own_sentence_is_unsure_and_choices_are_refused():
    assert own("మీరు వస్తారా").outcome == "unsure"
    with pytest.raises(ValueError):
        own("నువ్వు వస్తావా", mode="multiple_choice")


def test_copy_reasons_name_the_planted_error():
    assert X.is_copy("planted_error_present") and X.is_copy("planted_error_unchanged")
    assert not X.is_copy("accepted_form")
