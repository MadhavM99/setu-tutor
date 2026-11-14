"""Tool-calling evaluation (TASKS.md task 14), scored with scripted replies only: the metrics, the harness replay of
the frozen model-side attacks, and the injected learner attacks."""
import json
import re

from setu.agents import llm
from setu.research import tool_eval

_BANK = re.compile(r"लिखा था: (.+)")


def call(tool, **args):
    return json.dumps({"tool": tool, "args": args}, ensure_ascii=False)


def scripted(first_tool=None):
    """Echoes the bank sentence: agentic replies optionally try `first_tool`, then check, then submit."""
    def reply(msgs):
        task = next(m["content"] for m in msgs if m["role"] == "user")
        bank = _BANK.search(task).group(1).strip()
        if not task.startswith("item_id: "):
            return json.dumps({"sentence": bank}, ensure_ascii=False)
        item = task.split("\n", 1)[0].removeprefix("item_id: ")
        plan = ([call(first_tool, item_id=item)] if first_tool else []) + [
            call("check_classmate_sentence", item_id=item, sentence=bank), json.dumps({"final": bank}, ensure_ascii=False)]
        return plan[min(sum(m["role"] == "assistant" for m in msgs), len(plan) - 1)]
    return llm.MockProvider(reply)


def test_all_three_methods_are_scored_on_the_29_cases_with_tool_metrics_for_agentic_only():
    out = tool_eval.run_cases(scripted())
    assert set(out) == {"agentic_tools", "tool", "prompt_only"}
    assert out["prompt_only"]["role"] == "baseline" and out["tool"]["role"] == "ablation_tools_off"
    for m in out.values():
        assert m["cases"] == 29 and m["valid_rate"] == 1.0 and m["planting_precision"] == 1.0
    t = out["agentic_tools"]["tools"]
    assert t["tool_calls"] == 29 and t["tool_call_accuracy"] == 1.0 and t["valid_argument_rate"] == 1.0
    assert t["unsafe_action_rate"] == 0.0 and t["verified_final_rate"] == 1.0 and t["recovery_rate"] is None
    assert "tools" not in out["tool"]


def test_an_unknown_tool_counts_as_unsafe_and_wrong_and_the_case_as_recovered():
    t = tool_eval.run_cases(scripted("update_mastery"))["agentic_tools"]["tools"]
    assert t["tool_calls"] == 58 and t["tool_call_accuracy"] == 0.5 and t["valid_argument_rate"] == 0.5
    assert t["unsafe_action_rate"] == 0.5 and t["cases_with_unsafe_attempt"] == 29
    assert t["recovery_rate"] == 1.0


def test_the_wrong_but_real_tool_is_inaccurate_but_not_unsafe():
    t = tool_eval.run_cases(scripted("check_level"))["agentic_tools"]["tools"]
    assert t["tool_call_accuracy"] == 0.5 and t["unsafe_action_rate"] == 0.0


def test_the_harness_refuses_every_frozen_model_side_attack():
    r = tool_eval.replay_harness_attacks()
    assert r["n"] == 17 and r["refusal_rate"] == 1.0 and r["expected_error_rate"] == 1.0 and not r["not_refused"]


def test_an_injected_learner_attack_that_makes_the_model_try_a_write_tool_is_counted_and_refused():
    p = scripted("update_mastery")
    r = tool_eval.run_injected_attacks(p)
    assert r["cases"] == 11 and r["evaluable"] == 11 and r["unsafe_attempt_rate"] == 1.0
    assert r["unsafe_actions_executed"] == 0 and r["learner_saw_only_filtered"]
    assert any("कक्षा में किसी ने लिखा" in m["content"] for m in p.calls[0])


def test_a_dead_endpoint_is_not_evaluable_rather_than_safe():
    class Dead:
        model = "dead"

        def complete(self, messages, **_):
            return llm.Completion(None, "dead", 0, error="HTTP 429")

    assert tool_eval.run_injected_attacks(Dead())["evaluable"] == 0
    assert tool_eval.run_cases(Dead())["agentic_tools"]["evaluable"] == 0
