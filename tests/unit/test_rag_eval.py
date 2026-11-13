"""RAG evaluation scoring (TASKS.md task 16) and the statistics it uses. Offline: scripted fake replies only."""
import json
import math

import pytest

from setu.agents import llm, retrieval
from setu.agents.llm import Completion
from setu.research import envfile, rag_eval, stats

# ---------------------------------------------------------------- stats

def test_wilson_known_values():
    w = stats.wilson(10, 29)
    assert math.isclose(w["rate"], 10 / 29) and math.isclose(w["lo"], 0.1994, abs_tol=1e-3)
    assert math.isclose(w["hi"], 0.5265, abs_tol=1e-3)
    assert stats.wilson(0, 29)["lo"] == 0.0 and stats.wilson(29, 29)["hi"] == 1.0
    assert stats.wilson(0, 0)["rate"] is None
    with pytest.raises(ValueError):
        stats.wilson(3, 2)


def test_mcnemar_exact():
    m = stats.mcnemar([1, 1, 1, 1, 1, 1, 0, 0], [0, 0, 0, 0, 0, 0, 0, 0])
    assert (m["x_only"], m["y_only"]) == (6, 0) and math.isclose(m["p_exact"], 2 / 64)
    assert stats.mcnemar([1, 0], [1, 0])["p_exact"] == 1.0
    with pytest.raises(ValueError):
        stats.mcnemar([1], [1, 0])


# ---------------------------------------------------------------- cases

def test_cases_come_from_the_frozen_sets():
    pos, neg = list(rag_eval.positives()), list(rag_eval.negatives())
    assert len(pos) == 29 and all(c["raju"] == c["attempt"] for c in pos)
    manifest = json.loads((rag_eval.ROOT / "tests/eval_sets/manifest.json").read_text(encoding="utf-8"))
    assert [(c["item_id"], c["rule_id"], c["raju"]) for c in pos] == [
        (m["item_id"], m["rule_id"], m["wrong_form"]) for m in manifest["planting_cases"]]
    assert sum(c["kind"] == "correct_sentence" for c in neg) == 29
    assert sum(c["kind"] == "attack" for c in neg) == 11 and all(c["rule_id"] is None for c in neg)


def test_retrieval_report_is_deterministic_and_complete():
    docs = retrieval.load_rule_docs()
    a, b = rag_eval.retrieval_report(docs), rag_eval.retrieval_report(docs)
    assert a == b
    assert set(a["indexes"]) == {"all_25", "all_25_explanations_only", "hi_te_15", "hi_te_15_explanations_only",
                                 "oracle_upper_bound"}
    assert a["indexes"]["oracle_upper_bound"]["hit@1"]["k"] == 29
    m = a["rag_vs_oracle_hit@1"]
    assert m["x_only"] == 0 and m["y_only"] == 29 - a["indexes"]["all_25"]["hit@1"]["k"]
    assert a["indexes"]["all_25"]["hit@1"]["n"] == 29 and len(a["sweep"]) == len(rag_eval.SWEEP)
    assert a["sweep"][0]["abstain_planted"]["k"] == 0  # threshold 0 never abstains


# ---------------------------------------------------------------- scoring with a fake model

def _fake(reply_for):
    return llm.MockProvider(lambda msgs: reply_for(msgs))


def test_errors_are_excluded_not_counted():
    class Failing:
        model = "fail"

        def complete(self, messages, **_):
            return Completion(None, "fail", 5, error="HTTPStatusError: 429")

    docs = retrieval.load_rule_docs()
    logged = []
    rows = rag_eval.run_models(Failing(), docs, 0.5, ("a_blind",), log=logged.append)
    s = rag_eval.summarise(rows, "a_blind")
    assert s["positives"]["evaluable"] == 0 and s["positives"]["provider_errors"] == 29
    assert s["positives"]["hint_shown"]["rate"] is None and len(logged) == len(rows)


def test_scores_a_perfect_rag_coach_on_the_planted_cases():
    docs = retrieval.load_rule_docs()
    reply = json.dumps({"hint": "वाक्य के आख़िरी शब्द को ध्यान से देखिए।", "source": 1}, ensure_ascii=False)
    rows = rag_eval.run_models(_fake(lambda m: reply), docs, 0.0, ("b_rag", "c_oracle_retrieval"), log=lambda _: None)
    b, c = rag_eval.summarise(rows, "b_rag"), rag_eval.summarise(rows, "c_oracle_retrieval")
    assert c["positives"]["citation_faithful"]["rate"] == 1.0 and c["positives"]["hint_shown"]["k"] == 29
    hit1 = rag_eval.retrieval_report(docs)["indexes"]["all_25"]["hit@1"]["k"]
    assert b["positives"]["citation_faithful"]["k"] == hit1  # cites source 1 = the top hit
    cmp = rag_eval._paired(rows, "b_rag", "c_oracle_retrieval", "faithful_hint_shown")
    assert cmp["x_only"] == 0 and cmp["y_only"] == 29 - hit1
    assert b["compute"]["model_calls"] == 29 + 40 and b["negatives"]["cases"] == 40


def test_telugu_and_leak_are_counted_and_saved_as_qualitative():
    docs = retrieval.load_rule_docs()
    reply = json.dumps({"hint": "ఇంట్లో लिखिए", "source": 1}, ensure_ascii=False)
    rows = rag_eval.run_models(_fake(lambda m: reply), docs, 0.0, ("e_rag_no_threshold",), log=lambda _: None)
    s = rag_eval.summarise(rows, "e_rag_no_threshold")
    assert s["positives"]["telugu_in_hint"]["k"] == 29 and s["positives"]["hint_shown"]["k"] == 0
    q = rag_eval.qualitative(rows, rag_eval.retrieval_report(docs))
    assert q["blocked_hint"]["model_reply"] == reply and q["retrieval_miss"]["planted"]


def test_markdown_matches_the_json_numbers():
    docs = retrieval.load_rule_docs()
    rep = {"tag": "t", "threshold": 0.5, "status": "retrieval_only", "retrieval": rag_eval.retrieval_report(docs)}
    md = rag_eval.markdown(rep)
    assert rag_eval._fmt(rep["retrieval"]["indexes"]["all_25"]["hit@1"]) in md


def test_envfile_loads_without_overriding(tmp_path, monkeypatch):
    p = tmp_path / ".env"
    p.write_text("# c\nexport SETU_X_A=1\nSETU_X_B='two'\n", encoding="utf-8")
    monkeypatch.setenv("SETU_X_B", "shell")
    monkeypatch.delenv("SETU_X_A", raising=False)
    assert envfile.load(p) == ["SETU_X_A"]
    import os
    assert os.environ["SETU_X_A"] == "1" and os.environ["SETU_X_B"] == "shell"
    monkeypatch.delenv("SETU_X_A")
    assert envfile.load(tmp_path / "missing") == []


class _Quota:
    """Answers `budget` calls with a valid hint, then 429 (a free-tier quota running out)."""
    model, base_url, hosted, reasoning_effort = "fake", "local", False, None

    def __init__(self, budget):
        self.budget, self.calls = budget, 0

    def complete(self, messages, **_):
        self.calls += 1
        if self.calls > self.budget:
            return Completion(None, "fake", 1, error="HTTPStatusError: 429")
        return Completion(json.dumps({"hint": "वाक्य का आख़िरी शब्द देखिए।", "source": 1}, ensure_ascii=False),
                          "fake", 1, 5, 5)


def test_final_run_is_priority_ordered_partial_then_resumed(tmp_path, monkeypatch):
    monkeypatch.setattr(rag_eval, "REPORTS", tmp_path)
    monkeypatch.setattr(rag_eval.envfile, "load", lambda *_: None)
    monkeypatch.setenv("SETU_EVAL_INTERVAL", "0")
    assert rag_eval.PRIORITY[:3] == ("a_blind", "b_rag", "c_oracle_retrieval")
    first = _Quota(budget=50)
    monkeypatch.setattr(rag_eval.OpenAICompatible, "from_environment", classmethod(lambda cls: first))
    rag_eval.main(["--tag", "t", "--conditions", "a_blind,b_rag"])
    rep = json.loads((tmp_path / "rag_eval_t.json").read_text(encoding="utf-8"))
    assert rep["status"] == "partial (reduced-n)" and rep["conditions"]["a_blind"]["reduced_n"]
    assert rep["conditions"]["a_blind"]["evaluable_cases"] == 50
    assert "reduced-n" in (tmp_path / "rag_eval_t.md").read_text(encoding="utf-8")
    second = _Quota(budget=10_000)
    monkeypatch.setattr(rag_eval.OpenAICompatible, "from_environment", classmethod(lambda cls: second))
    rag_eval.main(["--tag", "t", "--conditions", "a_blind,b_rag"])
    rep = json.loads((tmp_path / "rag_eval_t.json").read_text(encoding="utf-8"))
    assert rep["status"] == "run" and not rep["conditions"]["a_blind"]["reduced_n"]
    assert second.calls == first.calls - 50  # only the failed cases were asked again


def test_limit_runs_the_same_first_planted_cases_under_each_condition():
    docs = retrieval.load_rule_docs()
    reply = json.dumps({"hint": "वाक्य का आख़िरी शब्द देखिए।", "source": 1}, ensure_ascii=False)
    rows = rag_eval.run_models(_fake(lambda m: reply), docs, 0.5, ("a_blind", "b_rag"), log=lambda _: None, limit=3)
    ids = [r["case_id"] for r in rows]
    assert ids[:3] == ids[3:] and len(ids) == 6 and all(r["kind"] == "planted" for r in rows)


def test_posthoc_condition_is_reported_next_to_the_primary_ones():
    docs = retrieval.load_rule_docs()
    numbered = json.dumps({"hint": "नियम 1 को फिर से पढ़िए।", "source": 1}, ensure_ascii=False)
    rows = rag_eval.run_models(_fake(lambda m: numbered), docs, 0.5, ("b_rag", "b_fixed_posthoc"), log=lambda _: None)
    b, f = rag_eval.summarise(rows, "b_rag"), rag_eval.summarise(rows, "b_fixed_posthoc")
    assert b["positives"]["hint_shown"]["k"] == 29 and b["positives"]["shown_and_usable"]["k"] == 0
    assert f["positives"]["hint_shown"]["k"] == 0 and "negatives" not in f  # rejected by the new check
    base = {"tag": "", "threshold": 0.5, "retrieval": rag_eval.retrieval_report(docs)}
    rep = rag_eval.build_report(base, rows, ["b_fixed_posthoc"])
    assert list(rep["conditions"]) == ["b_rag", "b_fixed_posthoc"]
    assert "(post-hoc)" in rag_eval.markdown(rep)
