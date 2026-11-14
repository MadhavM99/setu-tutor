"""LLM-judge validation (TASKS.md task 13) and the reasoning evaluation (task 15), with scripted replies only."""
import json

import pytest

from setu.agents import diagnose, llm
from setu.research import judge_eval, label_sheet, reasoning_eval

# ---------------------------------------------------------------- task 13: judge vs human


def labelled(tmp_path, label_for):
    """The real sheet, with every row labelled by `label_for(sheet_row | key_row)`."""
    sheet, key = label_sheet.build()
    by_id = {k["row_id"]: k for k in key}
    rows = [r | {"label": label_for(r | by_id[r["row_id"]])} for r in sheet]
    for name, cols, data in (("sheet.csv", label_sheet.SHEET_COLS, rows), ("key.csv", label_sheet.KEY_COLS, key)):
        label_sheet._write(tmp_path / name, cols, data)
    return judge_eval.load(tmp_path / "sheet.csv", tmp_path / "key.csv")


def test_unlabelled_rows_are_skipped_and_an_unknown_label_is_an_error(tmp_path):
    rows = labelled(tmp_path, lambda k: "correct" if k["batch"] == "A" else "")
    assert len(rows) == 50 and {r["human"] for r in rows} == {"correct"}
    with pytest.raises(ValueError, match="not one of"):
        labelled(tmp_path, lambda k: "maybe")


def test_a_human_who_agrees_with_the_checker_gives_kappa_1_without_a_model(tmp_path):
    out = judge_eval.run(labelled(tmp_path, lambda k: k["checker_outcome"]))
    assert out["labelled_rows"] == 145 and out["checker_all_rows"]["kappa"] == pytest.approx(1.0)
    assert out["checker_all_rows"]["kappa_ci95"] == [1.0, 1.0] and out["judge"].startswith("not_run")


def test_h6_compares_checker_and_judge_on_the_same_rows(tmp_path):
    rows = labelled(tmp_path, lambda k: k["checker_outcome"])
    out = judge_eval.run(rows, llm.MockProvider(lambda m: '{"label": "wrong"}'))
    assert out["judged_rows"] == 145 and out["llm_judge"]["kappa"] == pytest.approx(0.0)
    assert out["h6"] == {"checker_kappa_at_least_0_6": True, "checker_better_than_judge": True, "holds": True}
    assert all(r["judge"] == "wrong" for r in out["disagreements"])


def test_an_unusable_judge_reply_counts_as_invalid_and_a_dead_endpoint_as_not_evaluable(tmp_path):
    rows = labelled(tmp_path, lambda k: k["checker_outcome"])[:20]
    out = judge_eval.run(rows, llm.MockProvider(lambda m: "I think it's fine"))
    assert out["judge_invalid_rate"] == 1.0

    class Dead:
        def complete(self, messages, **_):
            return llm.Completion(None, "dead", 0, error="HTTP 429")

    out = judge_eval.run(rows, Dead())
    assert out["judged_rows"] == 0 and out["not_evaluable"] == 20 and out["h6"] is None


def test_the_judge_gets_the_labellers_instructions_and_no_checker_verdict(tmp_path):
    p = llm.MockProvider(lambda m: '{"label": "correct"}')
    row = labelled(tmp_path, lambda k: "wrong")[0]
    judge_eval.judge(p, row)
    sent = json.dumps(p.calls[0], ensure_ascii=False)
    assert "partial: the main mistake is fixed" in sent and row["learner_correction"] in sent
    assert row["checker_outcome"] not in sent.replace("correct:", "").replace("partial:", "").replace(
        "wrong:", "").replace("unsure:", "").split("Learner's correction")[0].split("Hindi meaning")[1]
    assert row["attempt_kind"] not in sent


# ---------------------------------------------------------------- task 15: reasoning


def test_the_case_sets_have_ground_truth_by_construction():
    a, e = reasoning_eval.stage_a_cases(), reasoning_eval.extended_cases()
    assert len(a) == 58 and {c["kind"] for c in a} == {"planted_unchanged", "fragment"}
    assert {c["direction"] for c in a + e} == {"HI->TE"}
    first = next(c for c in a if c["id"] == "HI-TE-001-a:planted_unchanged")
    assert first["truth"] == {"wrong_word": ["క్యా", "వస్తావు"], "rule_id": "HI-TE-001", "error_type": "habit_kept"}
    ok = next(c for c in e if c["id"] == "HI-TE-001-a:correct_form")
    assert ok["truth"] == {"wrong_word": ["none"], "rule_id": None, "error_type": "correct"}


def oracle(case, revise_from=None):
    """Replies with the true answers; with `revise_from`, steps 1-3 say that instead and the self-check fixes it."""
    t = case["truth"]
    right = {"wrong_word": (t["wrong_word"] or ["none"])[0], "rule_id": t["rule_id"] or "HI-TE-001",
             "error_type": t["error_type"]}
    first = right | (revise_from or {})
    steps = [{"wrong_word": first["wrong_word"]}, {"rule_id": first["rule_id"]}, {"error_type": first["error_type"]},
             right]

    def reply(msgs):
        if "all three at once" in msgs[-1]["content"]:
            return json.dumps(right, ensure_ascii=False)
        return json.dumps(steps[sum(m["role"] == "assistant" for m in msgs)], ensure_ascii=False)
    return llm.MockProvider(reply)


def run_one(case, provider):
    out = {}
    for method in diagnose.METHODS:
        d = diagnose.diagnose(provider, hindi_meaning=case["hindi_meaning"],
                              classmate_sentence=case["classmate_sentence"], learner_text=case["learner_text"],
                              rules=reasoning_eval.rules_for("HI->TE"), method=method)
        out[method] = reasoning_eval.summarise([reasoning_eval.row(case, d)])
    return out


def test_a_perfect_diagnosis_scores_1_on_every_step_and_agrees_with_the_checker():
    case = reasoning_eval.stage_a_cases()[0]
    out = run_one(case, oracle(case))
    for m in diagnose.METHODS:
        assert out[m]["final_accuracy"] == 1.0 and out[m]["valid_step_rate"] == 1.0
        assert out[m]["checker_agreement"] == 1.0
    assert out["stepwise"]["calls_per_case"] == 4 and out["direct"]["calls_per_case"] == 1
    assert out["stepwise"]["self_check_revised_rate"] == 0.0


def test_a_self_check_that_fixes_a_wrong_type_is_counted_as_a_fixing_revision():
    case = next(c for c in reasoning_eval.stage_a_cases() if c["kind"] == "planted_unchanged")
    out = run_one(case, oracle(case, revise_from={"error_type": "spelling_slip"}))
    s = out["stepwise"]
    assert s["final_accuracy"] == 1.0 and s["self_check_revised_rate"] == 1.0
    assert s["revisions_fixed"] == 1 and s["revisions_broke"] == 0
    assert out["no_self_check"]["error_type_accuracy"] == 0.0 and out["no_self_check"]["final_accuracy"] == 0.0


def test_a_correct_sentence_is_not_scored_on_its_rule():
    case = next(c for c in reasoning_eval.extended_cases() if c["kind"] == "correct_form")
    out = run_one(case, oracle(case))
    assert out["stepwise"]["rule_id_accuracy"] is None and out["stepwise"]["final_accuracy"] == 1.0


def test_run_writes_both_sets_and_all_three_methods_with_their_roles():
    cases = reasoning_eval.stage_a_cases()[:2]
    out = reasoning_eval.run(oracle(cases[0]), {"stage_a": cases})
    assert {m: out["stage_a"][m]["role"] for m in diagnose.METHODS} == {
        "stepwise": "method", "no_self_check": "ablation", "direct": "baseline"}
    assert len(out["stage_a"]["stepwise"]["rows"]) == 2
