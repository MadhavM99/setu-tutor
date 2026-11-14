"""Task 17 evaluation: same prompt and strict filter as task 6, resumable rows, paired stats. Offline (fake model)."""
import json

from setu.agents import classmate
from setu.agents.llm import Completion
from setu.research import ft_eval as fe
from setu.research.generation_baselines import cases


class _Echo:
    """Replies with the bank wrong form for even cases, a Hindi sentence for odd ones; fails the first `fail` calls."""
    model, base_url, hosted, reasoning_effort = "fake", "local", False, None

    def __init__(self, fail=0):
        self.calls, self.fail = 0, fail

    def complete(self, messages, **_):
        self.calls += 1
        if self.calls <= self.fail:
            return Completion(None, "fake", 1, error="HTTPStatusError: 429")
        prompt = messages[-1]["content"]
        wrong = prompt.split("राजू ने पिछली बार ऐसा लिखा था: ")[1].split("\n")[0]
        text = wrong if self.calls % 2 == 0 else "यह गलत है"
        return Completion(json.dumps({"sentence": text}, ensure_ascii=False), "fake", 1, 5, 5)


def test_run_scores_every_frozen_case_and_resumes(tmp_path, monkeypatch):
    monkeypatch.setattr(fe, "REPORTS", tmp_path)
    logged = []
    fe.run(_Echo(fail=3), "x", log=logged.append)
    rows = fe.load_rows("x")
    assert len(rows) == 29 and len(logged) == 3 and sum(not r["evaluable"] for r in rows) == 3
    p = _Echo()
    fe.run(p, "x", log=logged.append)
    assert p.calls == 3  # only the failed cases are retried
    latest = fe.latest(fe.load_rows("x"))
    assert len(latest) == 29 and all(r["evaluable"] for r in latest.values())
    assert all(r["valid"] == r["planted"] for r in latest.values() if r["valid"])  # echoing the bank form


def test_scoring_matches_the_strict_filter():
    rule, it, ctx = next(iter(cases()))
    t = classmate.propose(_Echo(), ctx, rule_title="", hindi_meaning=it["l1_meaning"],
                          bank_sentence=it["wrong_form"], method=fe.METHOD)
    row = fe.score(rule, it, t)
    assert row["evaluable"] and row["valid"] is False and "WRONG_SCRIPT" in row["reasons"]  # first call is odd: Hindi


def _rows(valid_ids):
    return [{"item_id": it["item_id"], "rule_id": r["rule_id"], "evaluable": True, "valid": it["item_id"] in valid_ids,
             "planted": it["item_id"] in valid_ids, "leak": False, "oov": False, "latency_ms": 10, "tokens": 5,
             "wrong_form": it["wrong_form"], "sentence": "s", "raw": "r", "reasons": []} for r, it, _ in cases()]


def test_summary_subsets_and_mcnemar():
    ids = [it["item_id"] for _, it, _ in cases()]
    res = fe.summarise({"gemma3_1b_base": _rows(set(ids[:2])), "gemini_prompted": _rows(set(ids[:10]))})
    base = res["conditions"]["gemma3_1b_base"]
    assert base["primary_all_29"]["evaluable"] == 29
    assert base["secondary_trained_27"]["evaluable"] == 27 and base["untrained_rule_HI-TE-006"]["evaluable"] == 2
    m = res["comparisons"]["gemma3_1b_base vs gemini_prompted"]["primary_all_29"]["valid"]
    assert (m["n_pairs"], m["x_only"], m["y_only"]) == (29, 0, 8)
    assert "untrained_rule_HI-TE-006" not in res["comparisons"]["gemma3_1b_base vs gemini_prompted"]


def test_report_writes_json_and_markdown(tmp_path, monkeypatch):
    monkeypatch.setattr(fe, "REPORTS", tmp_path)
    monkeypatch.setattr(fe, "ROOT", tmp_path.parent)
    fe.rows_path("gemma3_1b_base").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in _rows(set())),
                                              encoding="utf-8")
    rep = fe.report()
    assert rep["conditions"]["gemma3_1b_base"]["primary_all_29"]["valid"]["k"] == 0
    md = (tmp_path / "ft_eval.md").read_text(encoding="utf-8")
    assert "0/29 = 0.00 [0.00, 0.12]" in md and "No tuned model" in md
