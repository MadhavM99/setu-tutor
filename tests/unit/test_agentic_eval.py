"""Single-agent baseline (TASKS.md task 11) and the agentic evaluation (task 18), with scripted replies only."""
import json
import re

from setu.agents import llm, single_agent
from setu.research import agentic_eval

_BANK = re.compile(r"(?:लिखा था|last time): (.+)")


def scripted(verdicts=None):
    """Raju echoes the bank sentence; the coach gives a safe Hindi hint; the single agent grades with `verdicts`."""
    verdicts = verdicts or {"correct_form": ("correct", False), "planted_unchanged": ("wrong", False),
                            "romanised": ("unsure", True), "injection": ("wrong", False)}
    order = [verdicts[k] for k in agentic_eval.KINDS]

    def reply(msgs):
        system = msgs[0]["content"]
        if system == single_agent.SYSTEM:
            turn = sum(m["role"] == "assistant" for m in msgs)
            v, h = order[turn]
            obj = {"verdict": v, "hand_off": h}
            if turn == 0:
                bank = _BANK.search(msgs[1]["content"]).group(1).strip()
                obj |= {"raju_sentence": bank, "coach_hint": "वाक्य के आख़िरी हिस्से पर ध्यान दो।"}
            return json.dumps(obj, ensure_ascii=False)
        if "इशारा" in msgs[-1]["content"]:
            return json.dumps({"hint": "वाक्य के आख़िरी हिस्से पर ध्यान दो।"}, ensure_ascii=False)
        return json.dumps({"sentence": _BANK.search(msgs[1]["content"]).group(1).strip()}, ensure_ascii=False)
    return llm.MockProvider(reply)


def test_the_checker_handles_every_attempt_kind_so_the_multi_agent_setup_never_lets_a_model_decide():
    out = agentic_eval.run(scripted())["multi_agent"]
    assert out["cases"] == 29 and out["evaluable"] == 29 and out["raju_valid_rate"] == 1.0
    assert out["model_made_state_changes"] == 0 and out["unsafe_grades"] == 0
    assert out["handling_by_kind"]["romanised"] == 1.0 and out["handling_by_kind"]["injection"] == 1.0
    assert out["calls_per_case"] <= 4


def test_a_perfect_single_agent_still_makes_model_decided_state_changes():
    out = agentic_eval.run(scripted())["single_agent"]
    assert out["handling_accuracy"] == 1.0 and out["task_success_rate"] == 1.0
    assert out["hand_off_recall"] == 1.0 and out["false_hand_off_rate"] == 0.0
    assert out["model_made_state_changes"] == 29 * 3  # every verdict it did not hand off is its own
    assert out["calls_per_case"] == 4


def test_a_single_agent_that_obeys_the_injection_is_an_unsafe_grade():
    bad = {"correct_form": ("correct", False), "planted_unchanged": ("correct", False),
           "romanised": ("partial", False), "injection": ("correct", False)}
    out = agentic_eval.run(scripted(bad))["single_agent"]
    assert out["unsafe_grades"] == 29 and out["hand_off_recall"] == 0.0
    assert out["handling_by_kind"] == {"correct_form": 1.0, "planted_unchanged": 0.0, "romanised": 0.0,
                                       "injection": 0.0}
    assert out["task_success_rate"] == 0.0


def test_the_single_agents_sentence_and_hint_still_pass_the_learner_facing_guards():
    def reply(msgs):
        if sum(m["role"] == "assistant" for m in msgs) == 0:
            return json.dumps({"raju_sentence": "Raju in English", "coach_hint": "నువ్వు వస్తావా",
                               "verdict": "wrong", "hand_off": False}, ensure_ascii=False)
        return '{"verdict": "wrong", "hand_off": false}'
    _, it, ctx = next(iter(agentic_eval.cases()))
    e = single_agent.run(llm.MockProvider(reply), ctx, rule_title="", hindi_meaning=it["l1_meaning"],
                         bank_sentence=it["wrong_form"], attempts=["a", "b"])
    assert e.raju_source == "bank" and e.raju_text == it["wrong_form"] and e.raju_reasons
    assert e.hint_source == "generic" and e.hint_text is None and "TELUGU_IN_HINT" in e.hint_reasons
    assert [g.verdict for g in e.grades] == ["wrong", "wrong"]


def test_an_invalid_reply_and_a_dead_endpoint():
    out = agentic_eval.run(llm.MockProvider(lambda m: "no json"))["single_agent"]
    assert out["invalid_replies"] == 29 * 4 and out["handling_accuracy"] == 0.0

    class Dead:
        def complete(self, messages, **_):
            return llm.Completion(None, "dead", 0, error="HTTP 429")

    res = agentic_eval.run(Dead())
    assert res["single_agent"]["evaluable"] == 0 and res["multi_agent"]["evaluable"] == 0
