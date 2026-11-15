"""Controlled generation ablation (final audit), scored with scripted replies only: the harness-with-memory loop,
the exemplar removal, the row description and the paired summary. No model is contacted."""
import json
import re

from setu.agents import llm
from setu.research import generation_ablation as ga
from setu.research.generation_baselines import cases

_BANK = re.compile(r"लिखा था: (.+)")


def first_case():
    return next(iter(cases()))


def sentence(s):
    return json.dumps({"sentence": s}, ensure_ascii=False)


def test_history_loop_keeps_the_rejected_draft_and_the_check_result_in_the_conversation():
    _, it, ctx = first_case()
    provider = llm.MockProvider([sentence(it["correct_form"]), sentence(it["wrong_form"])])
    t = ga.propose_with_history(provider, ctx, rule_title="", hindi_meaning=it["l1_meaning"],
                                bank_sentence=it["wrong_form"])
    assert t.source == "model" and t.text == it["wrong_form"] and len(t.drafts) == 2
    assert t.drafts[0].reasons == ("ANSWER_LEAK",)
    second = provider.calls[1]
    assert [m["role"] for m in second] == ["system", "user", "assistant", "user"]
    assert it["correct_form"] in second[2]["content"]  # the model sees its own rejected draft
    assert "ANSWER_LEAK" in second[3]["content"] and second[3]["content"].startswith("TOOL RESULT: ")


def test_history_loop_falls_back_to_the_bank_after_three_rejected_drafts():
    _, it, ctx = first_case()
    provider = llm.MockProvider(lambda msgs: sentence(it["correct_form"]))
    t = ga.propose_with_history(provider, ctx, rule_title="", hindi_meaning=it["l1_meaning"],
                                bank_sentence=it["wrong_form"])
    assert t.source == "bank" and t.text == it["wrong_form"] and len(t.drafts) == ga.MAX_DRAFTS
    assert ga.row("tool_history", 1, it, t)["same_draft_repeated"] is True


def test_no_exemplar_removes_the_bank_sentence_and_nothing_else():
    rule, it, ctx = first_case()
    seen = []

    def reply(msgs):
        seen.append(msgs)
        return sentence("x")

    ga.run_condition(llm.MockProvider(reply), "prompt_only_noex", rule, it, ctx)
    task = seen[0][1]["content"]
    assert it["wrong_form"] not in task and "लिखा था" not in task
    assert it["l1_meaning"] in task and "सिर्फ़ इन शब्दों का इस्तेमाल करो" in task
    ga.run_condition(llm.MockProvider(reply), "prompt_only", rule, it, ctx)
    assert it["wrong_form"] in seen[1][1]["content"]


def test_agentic_no_exemplar_still_reaches_the_tool_loop():
    rule, it, ctx = first_case()
    replies = [json.dumps({"tool": "check_classmate_sentence", "args": {"item_id": it["item_id"],
                                                                        "sentence": it["wrong_form"]}},
                          ensure_ascii=False), json.dumps({"final": it["wrong_form"]}, ensure_ascii=False)]
    provider = llm.MockProvider(replies)
    t = ga.run_condition(provider, "agentic_noex", rule, it, ctx)
    assert t.source == "model" and len(t.steps) == 2
    assert all(it["wrong_form"] not in m["content"] for m in provider.calls[0] if m["role"] == "user")


def test_describe_compares_strings_only():
    _, it, _ = first_case()
    assert ga.describe(it["wrong_form"], it) == "bank_wrong_form"
    assert ga.describe(it["correct_form"], it) == "correct_form"
    wrong_only = (set(it["wrong_form"].split()) - set(it["correct_form"].split())).pop()
    assert ga.describe(f"{wrong_only} కొత్త", it) == "other_with_planted_word"
    assert ga.describe("కొత్త", it) == "other" and ga.describe(None, it) == "none"


def scripted_copy(msgs):
    """Copies the exemplar when it is there; without it, writes the correct sentence (a leak)."""
    task = next(m["content"] for m in msgs if m["role"] == "user")
    m = _BANK.search(task)
    return sentence(m.group(1).strip() if m else "అది")


def test_collect_is_resumable_and_summary_pairs_the_same_cases(tmp_path):
    path = tmp_path / "rows.jsonl"
    provider = llm.MockProvider(scripted_copy)
    conds = ("prompt_only", "prompt_only_noex")
    ga.collect(provider, repeats=2, conditions=conds, path=path, limit=4)
    rows = ga.load_rows(path)
    assert len(rows) == 2 * 2 * 4
    calls = len(provider.calls)
    ga.collect(provider, repeats=2, conditions=conds, path=path, limit=4)  # nothing left to do
    assert len(provider.calls) == calls and len(ga.load_rows(path)) == 16
    s = ga.summarise(rows)
    assert s["conditions"]["prompt_only"]["repeat1_valid"]["k"] == 4
    assert s["conditions"]["prompt_only_noex"]["pooled_valid_rate"] == 0.0
    r1 = next(p for p in s["paired"] if p["x"] == "prompt_only" and p["y"] == "prompt_only_noex"
              and p["scope"] == "repeat1")
    assert (r1["n_pairs"], r1["x_only"], r1["y_only"]) == (4, 4, 0) and r1["p_exact"] == 0.125
    pooled = next(p for p in s["paired"] if p["x"] == "prompt_only" and p["scope"] == "all_repeats")
    assert pooled["p_exact"] is None and pooled["difference_ci95_case_bootstrap"] == [1.0, 1.0]


def test_error_rows_are_not_results_and_are_retried(tmp_path):
    path = tmp_path / "rows.jsonl"

    class Down:
        def complete(self, messages, **kw):
            return llm.Completion(None, "m", 0, error="HTTPStatusError: 503")

    ga.collect(Down(), repeats=1, conditions=("prompt_only",), path=path, limit=2)
    assert all(not r["evaluable"] for r in ga.load_rows(path))
    assert ga.summarise(ga.load_rows(path))["conditions"] == {}
    ga.collect(llm.MockProvider(scripted_copy), repeats=1, conditions=("prompt_only",), path=path, limit=2)
    rows = ga.load_rows(path)
    assert len(rows) == 2 and all(r["evaluable"] and r["valid"] for r in rows)


def test_paraphrase_candidates_are_exported_for_review_but_never_accepted(tmp_path):
    _, it, ctx = first_case()
    words = it["wrong_form"].split()
    para = " ".join([words[-1], *words[:-1]]) if len(words) > 1 else it["wrong_form"] + " " + it["wrong_form"]
    rows = [{"condition": "tool", "item_id": it["item_id"], "drafts": [para, it["wrong_form"], para]},
            {"condition": "prompt_only", "item_id": it["item_id"], "drafts": [it["correct_form"]]}]
    out = tmp_path / "c.csv"
    n = ga.export_candidates(rows, out)
    lines = out.read_text(encoding="utf-8").splitlines()
    if ga.describe(para, it) == "other_with_planted_word":
        assert n == 1 and para in lines[1] and ",2,tool," in lines[1]
    else:
        assert n == 0
    from setu.domain import leakfilter
    assert leakfilter.check_sentence(para, ctx)  # the filter still rejects it
