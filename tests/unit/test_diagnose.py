"""Diagnostic reasoning steps (TASKS.md task 8) with the mock provider only."""
import json

import pytest

from setu.agents import diagnose, llm

RULES = [("HI-TE-001", "सवाल: आख़िर में -आ"), ("HI-TE-002", "'है' के लिए ఉంది नहीं")]


def j(**kw):
    return json.dumps(kw, ensure_ascii=False)


def run(replies, method="stepwise", learner="క్యా నువ్వు వస్తావా"):
    p = llm.MockProvider(replies)
    d = diagnose.diagnose(p, hindi_meaning="क्या तुम आ रहे हो?", classmate_sentence="క్యా నువ్వు వస్తావు",
                          learner_text=learner, rules=RULES, method=method)
    return d, p


def test_stepwise_stores_every_step_separately_and_the_self_check_can_revise():
    d, p = run([j(wrong_word="క్యా"), j(rule_id="HI-TE-002"), j(error_type="habit_kept"),
                j(wrong_word="క్యా", rule_id="HI-TE-001", error_type="habit_kept")])
    assert [s.name for s in d.steps] == ["wrong_word", "rule", "error_type", "self_check"] and len(p.calls) == 4
    assert [s.answer for s in d.steps[:3]] == [{"wrong_word": "క్యా"}, {"rule_id": "HI-TE-002"},
                                               {"error_type": "habit_kept"}]
    assert (d.wrong_word, d.rule_id, d.error_type, d.revised) == ("క్యా", "HI-TE-001", "habit_kept", True)
    assert p.calls[1][-2]["role"] == "assistant" and "క్యా" in p.calls[1][-2]["content"]


def test_the_ablation_skips_the_self_check_and_direct_answers_in_one_call():
    d, p = run([j(wrong_word="క్యా"), j(rule_id="HI-TE-001"), j(error_type="habit_kept")], "no_self_check")
    assert len(p.calls) == 3 and (d.rule_id, d.revised) == ("HI-TE-001", False)
    d, p = run([j(wrong_word="క్యా", rule_id="HI-TE-001", error_type="habit_kept")], "direct")
    assert len(p.calls) == 1 and [s.name for s in d.steps] == ["direct"] and d.error_type == "habit_kept"


@pytest.mark.parametrize("bad", [j(wrong_word="ఏదో"), j(rule_id="HI-TE-099"), j(error_type="grammar"), "not json"])
def test_invalid_answers_are_kept_in_the_record_but_not_used(bad):
    replies = [j(wrong_word="క్యా"), j(rule_id="HI-TE-001"), j(error_type="habit_kept")]
    idx = 0 if "wrong_word" in bad else 1 if "rule_id" in bad else 2 if "error_type" in bad else 0
    replies[idx] = bad
    d, _ = run(replies, "no_self_check")
    assert not d.steps[idx].valid
    assert (d.wrong_word, d.rule_id, d.error_type)[idx] is None


def test_an_invalid_self_check_keeps_the_step_answers():
    d, _ = run([j(wrong_word="none"), j(rule_id="HI-TE-001"), j(error_type="correct"), "I think it is fine"],
               learner="నువ్వు వస్తావా")
    assert (d.wrong_word, d.error_type, d.revised) == ("none", "correct", False) and not d.steps[3].valid


def test_every_checker_reason_maps_to_an_error_type():
    assert set(diagnose.CHECKER_TO_TYPE.values()) <= set(diagnose.ERROR_TYPES)
