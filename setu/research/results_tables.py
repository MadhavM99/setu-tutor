"""Results tables for the final report (TASKS.md tasks 20 and 23): tasks 6, 13, 14, 15 and 18, built only from the
saved reports. Rates carry Wilson 95% intervals (`stats.wilson`); paired method comparisons on the same cases use the
exact McNemar test where the report keeps per-case rows (task 15). Nothing is re-run and no number is typed by hand.

    python -m setu.research.results_tables    # writes reports/results_tables.md
"""
import json
from pathlib import Path

from .stats import mcnemar, wilson

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "reports"
OUT = REPORTS / "results_tables.md"


def _load(name: str) -> dict | None:
    p = REPORTS / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def ci(rate: float | None, n: int) -> str:
    """'0.72 [0.54, 0.85]' from a rate over n cases (k recovered as round(rate * n))."""
    if rate is None or not n:
        return "n/a"
    w = wilson(round(rate * n), n)
    return f"{w['rate']:.2f} [{w['lo']:.2f}, {w['hi']:.2f}]"


def _table(head: list[str], rows: list[list]) -> list[str]:
    return ["| " + " | ".join(head) + " |", "|" + "---|" * len(head),
            *("| " + " | ".join(str(c) for c in r) + " |" for r in rows), ""]


def generation(r: dict) -> list[str]:
    rows = []
    for m in ("prompt_only", "resample", "tool", "agentic_tools"):
        v = r["methods"][m]
        n = v["n"]
        rows.append([f"`{m}`", f"{v['evaluable']}/{v['cases']}", ci(v["valid_rate"], n), ci(v["leak_rate"], n),
                     ci(v["oov_rate"], n), f"{v['planting_precision']:.2f}", f"{v['calls_per_case']:.2f}",
                     f"{v['tokens_per_case']:.0f}"])
    c, f = r["coach"], r["friend"]
    out = ["## Task 6: generation baseline (29 frozen planting cases)", "",
           (f"Model `{r['model']}`, reasoning effort `{r['reasoning_effort']}`. Provider calls: "
           f"{r['provider_calls']['ok']} ok, {sum(r['provider_calls']['errors'].values())} errors."), "",
           *_table(["Raju method", "Evaluable", "Valid", "Answer leak", "OOV", "Planting precision", "Calls/case",
                    "Tokens/case"], rows),
           "Coach (one hint per case):", "",
           *_table(["Hint shown", "Answer leak", "Telugu in hint", "Not Hindi"],
                   [[ci(c["model_hint_shown_rate"], c["n"]), ci(c["answer_leak_rate"], c["n"]),
                     ci(c["telugu_in_hint_rate"], c["n"]), ci(c["not_hindi_rate"], c["n"])]]),
           "Friend (approved scene lines):", "",
           *_table(["Context", "Lines", "Model pick", "Learner saw only approved lines"],
                   [[k, v["cases"], ci(v.get("model_pick_rate"), v.get("n", 0)), v["learner_saw_only_approved"]]
                    for k, v in f.items()]),
           (f"Outage (invalid key): Raju fell back {r['outage']['raju_fell_back_to_bank']}, coach fell back "
           f"{r['outage']['coach_fell_back']}, friend showed the approved line {r['outage']['friend_showed_approved']}."),
           ""]
    return out


def tool_calling(r: dict) -> list[str]:
    roles = {"prompt_only": "baseline", "tool": "ablation: tools off", "agentic_tools": "method"}
    rows = []
    for m, role in roles.items():
        v = r["methods"][m]
        rows.append([f"`{m}`", role, ci(v["valid_rate"], v["n"]), ci(v["leak_rate"], v["n"]),
                     ci(v["fallback_rate"], v["n"]), f"{v['tokens_per_case']:.0f}"])
    t, h, a = r["methods"]["agentic_tools"]["tools"], r["harness_attacks"], r["injected_attacks"]
    calls = t["tool_calls"]
    return ["## Task 14: tool calling", "",
            f"Provider calls: {r['provider_calls']['ok']} ok, {sum(r['provider_calls']['errors'].values())} errors.",
            "", *_table(["Method", "Role", "Valid", "Answer leak", "Fallback", "Tokens/case"], rows),
            f"Tool use by `agentic_tools` ({calls} tool calls over {t['cases']} cases):", "",
            *_table(["Metric", "Value"], [
                ["Tool-call accuracy", ci(t["tool_call_accuracy"], calls)],
                ["Valid-argument rate", ci(t["valid_argument_rate"], calls)],
                ["Unsafe/unapproved action rate", ci(t["unsafe_action_rate"], calls)],
                ["Cases that used a tool", ci(t["used_a_tool_rate"], t["cases"])],
                ["Final sentence already approved by the tool", f"{t['verified_final_rate']:.2f}"],
                ["Cases that hit the step cap", ci(t["step_cap_rate"], t["cases"])],
                ["Recovery rate", "not measurable: no erroneous call occurred"
                 if t["recovery_rate"] is None else f"{t['recovery_rate']:.2f}"]]),
            "Attacks:", "",
            *_table(["Attack set", "n", "Result"], [
                ["Model-side tool calls, replayed into the harness (no model)", h["n"],
                 f"refused {ci(h['refusal_rate'], h['n'])}; expected error {ci(h['expected_error_rate'], h['n'])}"],
                ["Learner messages injected into Raju's task", a["evaluable"],
                 (f"unsafe attempts {ci(a['unsafe_attempt_rate'], a['evaluable'])}; executed "
                 f"{a['unsafe_actions_executed']}; learner saw only filtered text {a['learner_saw_only_filtered']}")]])]


def reasoning(r: dict) -> list[str]:
    out = ["## Task 15: diagnostic reasoning", "",
           f"Provider calls: {r['provider_calls']['ok']} ok, {sum(r['provider_calls']['errors'].values())} errors.", ""]
    roles = {"direct": "baseline", "no_self_check": "ablation", "stepwise": "method"}
    for name, res in r["results"].items():
        rows = []
        for m, role in roles.items():
            v = res[m]
            n = v["evaluable"]
            rows.append([f"`{m}`", role, ci(v["wrong_word_accuracy"], n), ci(v["rule_id_accuracy"], n),
                         ci(v["error_type_accuracy"], n), ci(v["final_accuracy"], n), ci(v["checker_agreement"], n),
                         f"{v['calls_per_case']:.0f}", f"{v['tokens_per_case']:.0f}"])
        s = res["stepwise"]
        final = {m: [x["final_correct"] for x in res[m]["rows"]] for m in roles}
        word = {m: [x["marks"]["wrong_word"] is True for x in res[m]["rows"]] for m in roles}
        tests = [["stepwise vs direct", "final", mcnemar(final["stepwise"], final["direct"])],
                 ["stepwise vs direct", "wrong word", mcnemar(word["stepwise"], word["direct"])],
                 ["stepwise vs no_self_check", "final", mcnemar(final["stepwise"], final["no_self_check"])]]
        out += [f"### Set `{name}` ({res['stepwise']['cases']} cases)", "",
                *_table(["Method", "Role", "Wrong word", "Rule", "Error type", "Final (all right)", "Agrees with checker",
                         "Calls", "Tokens/case"], rows),
                (f"Self-check (stepwise): revised {s['self_check_revised_rate']:.3f} of cases; revisions that fixed an "
                f"answer {s['revisions_fixed']}, that broke one {s['revisions_broke']}."), "",
                "Final accuracy by attempt kind: " + "; ".join(
                    f"`{m}` " + ", ".join(f"{k} {v:.2f}" for k, v in res[m]["by_kind"].items()) for m in roles), "",
                "Paired comparisons (exact McNemar, same cases):", "",
                *_table(["Comparison", "Outcome", "First only", "Second only", "p"],
                        [[a, b, t["x_only"], t["y_only"], f"{t['p_exact']:.3f}"] for a, b, t in tests])]
    return out


def judge(r: dict) -> list[str]:
    def row(name, s):
        return [name, s["n"], f"{s['kappa']:.2f} [{s['kappa_ci95'][0]:.2f}, {s['kappa_ci95'][1]:.2f}]",
                f"{s['kappa_binary']:.2f}", ci(s["accuracy"], s["n"])]
    h6 = r["h6"]
    return ["## Task 13: checker and LLM judge against the native-speaker labels (batch A)", "",
            (f"Human labels: {r['human_labels']}. Judge invalid replies: {r['judge_invalid_rate']:.2f}. "
            f"κ intervals: bootstrap 95%."), "",
            *_table(["Rater vs human", "n", "κ (4 labels)", "κ (correct vs not)", "Accuracy"],
                    [row("Deterministic checker", r["checker"]), row("Prompt-only LLM judge", r["llm_judge"])]),
            (f"H6 (checker κ ≥ 0.6 and higher than the judge): checker κ ≥ 0.6 {h6['checker_kappa_at_least_0_6']}, "
            f"checker better than judge {h6['checker_better_than_judge']}: **H6 {'holds' if h6['holds'] else 'rejected'}**."),
            ""]


def agentic(r: dict) -> list[str]:
    m, s = r["results"]["multi_agent"], r["results"]["single_agent"]
    n = m["evaluable"]
    graded = 4 * n

    def pair(key, denom=n):
        return [ci(m[key], denom), ci(s[key], denom)]

    return ["## Task 18: role separation on (multi-agent) vs off (single agent, task 11)", "",
            (f"29 frozen cases, 4 learner attempts each. Provider calls: {r['provider_calls']['ok']} ok, "
            f"{sum(r['provider_calls']['errors'].values())} errors."), "",
            *_table(["Metric", "Multi-agent (method)", "Single agent (baseline)"], [
                ["Attempts handled right", *pair("handling_accuracy", graded)],
                *[[f"… {k}", ci(m["handling_by_kind"][k], n), ci(s["handling_by_kind"][k], n)]
                  for k in m["handling_by_kind"]],
                ["Hand-off recall (romanised)", *pair("hand_off_recall")],
                ["False hand-off rate (gradable)", ci(m["false_hand_off_rate"], 2 * n),
                 ci(s["false_hand_off_rate"], 2 * n)],
                ["Verdicts decided by a model", m["model_made_state_changes"], s["model_made_state_changes"]],
                ["Injections graded correct", m["unsafe_grades"], s["unsafe_grades"]],
                ["Raju sentence valid", *pair("raju_valid_rate")],
                ["Hint shown", *pair("hint_shown_rate")],
                ["Task success", *pair("task_success_rate")],
                ["Calls per case", f"{m['calls_per_case']:.2f}", f"{s['calls_per_case']:.2f}"],
                ["Tokens per case", f"{m['tokens_per_case']:.0f}", f"{s['tokens_per_case']:.0f}"]])]


def compute(reports: dict) -> list[str]:
    rows, total_calls, total_tokens = [], 0, 0
    for name, r in reports.items():
        if not r or "provider_calls" not in r:
            continue
        calls = r["provider_calls"]["ok"]
        if name == "task 13":
            tokens = r["judge_tokens"]
        elif name == "task 15":
            tokens = sum(v["tokens_per_case"] * v["evaluable"] for res in r["results"].values() for v in res.values())
        elif name == "task 18":
            tokens = sum(v["tokens_per_case"] * v["evaluable"] for v in r["results"].values())
        else:
            ms = r["methods"].values()
            tokens = sum(v["tokens_per_case"] * v["n"] for v in ms)
            if name == "task 6":
                tokens += r["coach"]["tokens_per_case"] * r["coach"]["n"]  # friend tokens are not logged
        total_calls, total_tokens = total_calls + calls, total_tokens + tokens
        rows.append([name, r.get("model", ""), calls, f"{tokens:,.0f}"])
    rows.append(["**total**", "", f"**{total_calls}**", f"**{total_tokens:,.0f}**"])
    return ["## Compute (task 23): these runs", "",
            *_table(["Run", "Model", "Calls (ok)", "Tokens"], rows),
            ("Task 6's friend calls (24) are counted in its calls but their tokens are not logged. Madhav's RAG and "
            "fine-tuning runs are reported in `docs/submission/drafts/madhav_results.md`."), ""]


def build() -> str:
    reports = {"task 6": _load("generation_baselines.json"), "task 13": _load("judge_eval.json"),
               "task 14": _load("tool_eval.json"), "task 15": _load("reasoning_eval.json"),
               "task 18": _load("agentic_eval.json")}
    parts = {"task 6": generation, "task 13": judge, "task 14": tool_calling, "task 15": reasoning,
             "task 18": agentic}
    out = ["# Results tables (tasks 6, 13, 14, 15, 18)", "",
           ("Generated by `python -m setu.research.results_tables` from the JSON reports in `reports/`. Rates: "
           "value [Wilson 95% interval]. Small n (29 cases): read intervals, not point differences."), ""]
    for name in ("task 6", "task 14", "task 15", "task 13", "task 18"):
        r = reports[name]
        out += parts[name](r) if r and r.get("status") == "run" else [f"## {name}: no run report yet", ""]
    out += compute(reports)
    return "\n".join(out)


def main() -> int:
    OUT.write_text(build(), encoding="utf-8")
    print(OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
