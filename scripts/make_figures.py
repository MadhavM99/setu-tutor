"""Build every figure of the final paper and poster from the result files in `reports/`. Nothing is typed in by hand:
each number is read from a JSON report, and each figure names its source file in the caption text below.

    pip install matplotlib          # the only extra dependency (pip install -e ".[figures]")
    python -m scripts.make_figures  # writes docs/submission/figures/*.pdf, *.png (300 dpi), *.svg

Figures 1 and 2 are diagrams of the implementation (module and function names are the real ones). Figures 3 to 6 are
data. Colours mean the same thing everywhere: teal = deterministic code, purple = language model, orange = people
(learner, teacher, human labels), grey = baseline or reference.
"""
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
OUT = ROOT / "docs/submission/figures"
TEAL, PURPLE, ORANGE, GREY, INK, MUTED = "#0A9086", "#6B4FA0", "#C8691C", "#7A7A85", "#1F1F27", "#5B5B66"
TEAL_L, PURPLE_L, ORANGE_L, GREY_L = "#DDF1EF", "#E9E3F4", "#F8E8D8", "#EEEEF1"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9, "axes.titlesize": 10, "axes.titleweight": "bold",
    "axes.labelsize": 9, "axes.edgecolor": "#B9B9C2", "axes.linewidth": 0.8, "axes.spines.top": False,
    "axes.spines.right": False, "xtick.color": MUTED, "ytick.color": MUTED, "xtick.labelsize": 8,
    "ytick.labelsize": 8, "axes.labelcolor": INK, "text.color": INK, "legend.frameon": False, "legend.fontsize": 8,
    "figure.dpi": 100, "savefig.dpi": 300, "savefig.bbox": "tight", "pdf.fonttype": 42, "svg.fonttype": "none",
    "axes.grid": True, "grid.color": "#E6E6EB", "grid.linewidth": 0.6, "axes.axisbelow": True})


def load(name):
    p = REPORTS / name
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None


def wilson(k, n, z=1.959964):
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, (0.0 if k == 0 else max(0.0, c - h)), (1.0 if k == n else min(1.0, c + h))


def save(fig, name, svg=False):
    OUT.mkdir(parents=True, exist_ok=True)
    for ext in ("pdf", "png") + (("svg",) if svg else ()):
        fig.savefig(OUT / f"{name}.{ext}")
    plt.close(fig)
    return name


# ------------------------------------------------------------------ diagrams


def _box(ax, x, y, w, h, title, body="", face=GREY_L, edge=GREY, title_size=8.5, body_size=7):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12", fc=face, ec=edge, lw=1.1))
    if body:
        ax.text(x + w / 2, y + h - 0.16, title, ha="center", va="top", fontsize=title_size, fontweight="bold")
        ax.text(x + w / 2, y + h - 0.47, body, ha="center", va="top", fontsize=body_size, color=MUTED, linespacing=1.25)
    else:
        ax.text(x + w / 2, y + h / 2, title, ha="center", va="center", fontsize=title_size, fontweight="bold")


def _arrow(ax, a, b, label="", color=INK, style="-|>", ls="-", rad=0.0, lw=1.1, off=(0, 0.1), size=6.8):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle=style, mutation_scale=9, color=color, lw=lw, ls=ls,
                                 connectionstyle=f"arc3,rad={rad}", shrinkA=2, shrinkB=2))
    if label:
        ax.text((a[0] + b[0]) / 2 + off[0], (a[1] + b[1]) / 2 + off[1], label, ha="center", va="bottom", fontsize=size,
                color=MUTED)


def fig_architecture():
    fig, ax = plt.subplots(figsize=(11.2, 6.3))
    ax.set_xlim(0, 16)
    ax.set_ylim(-0.6, 9.3)
    ax.axis("off")
    # safety boundary
    ax.add_patch(Rectangle((8.55, 0.3), 7.3, 5.05, fc="none", ec=TEAL, lw=1.2, ls=(0, (5, 3))))
    ax.text(8.7, 5.22, "Authority boundary: only this code can change the learner's recorded state",
            fontsize=7.2, color=TEAL, va="top")

    _box(ax, 0.2, 6.1, 2.2, 1.9, "Learner", "Hindi speaker\nbrowser, Hindi pages\ntypes or taps Telugu", ORANGE_L, ORANGE)
    _box(ax, 3.1, 6.1, 2.6, 1.9, "Web app (FastAPI)", "setu/web/routes_rules.py\nroutes_learn, routes_scenes\nserver-rendered Hindi", GREY_L, GREY)
    _box(ax, 6.4, 7.35, 2.9, 1.25, "Raju (classmate)", "agents/classmate.propose\nwrites ONE sentence", PURPLE_L, PURPLE)
    _box(ax, 6.4, 5.95, 2.9, 1.25, "Coach (didi)", "agents/coach.hint\nwrites ONE Hindi hint", PURPLE_L, PURPLE)
    _box(ax, 9.75, 7.35, 2.6, 1.25, "Native friend", "agents/friend.ModelPicker\npicks an approved line", PURPLE_L, PURPLE)
    _box(ax, 12.9, 6.55, 2.9, 2.05, "Output gates", "domain/leakfilter\ncheck_sentence, check_hint\nfriend.choose_line\nfail -> approved bank text", TEAL_L, TEAL)

    _box(ax, 0.2, 3.3, 2.2, 1.6, "Normaliser", "domain/normalise\nscript, Hindi-keyboard\nforgiveness", TEAL_L, TEAL)
    _box(ax, 3.1, 3.3, 2.6, 1.6, "Checker", "domain/checker.check_fix\ncorrect / partial /\nwrong / unsure", TEAL_L, TEAL)
    _box(ax, 6.2, 3.3, 2.1, 1.6, "Verdict", "domain/verdict\nminted only by\nthe checker", TEAL_L, TEAL)
    _box(ax, 8.9, 3.3, 2.9, 1.6, "OutcomeWriter", "store/outcome_writer\nrecord_verdict, apply_forget\nDB role setu_writer", TEAL_L, TEAL)
    _box(ax, 12.4, 2.4, 3.2, 2.5, "PostgreSQL 16", "attempt, verdict, skill state\nclassmate_rule_state (Raju)\nFSRS cards + review log\nhash-chained event_ledger\ntriggers refuse unbacked changes", "#FFFFFF", TEAL)

    _box(ax, 12.4, 0.5, 3.2, 1.6, "Teacher console", "web/routes_teacher\nsettles 'unsure' answers\nsigned TeacherResolution", ORANGE_L, ORANGE)
    _box(ax, 3.1, 0.6, 2.6, 1.6, "Planner + scheduler", "domain/planner, scheduler\nnext turn, FSRS due dates,\nRaju forgets with learner", TEAL_L, TEAL)
    _box(ax, 0.2, 0.6, 2.2, 1.6, "Content bank", "25 rules, 49 items\nteacher-reviewed\nbefore any learner", GREY_L, GREY)

    _arrow(ax, (2.4, 7.05), (3.1, 7.05))
    _arrow(ax, (5.7, 7.6), (6.4, 7.95), "task")
    _arrow(ax, (5.7, 6.7), (6.4, 6.55))
    _arrow(ax, (9.3, 7.95), (9.75, 7.95))
    _arrow(ax, (12.35, 7.95), (12.9, 7.95))
    _arrow(ax, (9.3, 6.5), (12.9, 6.95), "proposal (text only)", color=PURPLE, off=(0, -0.42))
    _arrow(ax, (14.35, 8.6), (4.4, 8.0), "shown only if every check passes", color=TEAL, rad=0.13, off=(0, 0.74))
    _arrow(ax, (1.3, 6.1), (1.3, 4.9), "answer", off=(0.45, -0.1))
    _arrow(ax, (2.4, 4.1), (3.1, 4.1))
    _arrow(ax, (5.7, 4.1), (6.2, 4.1))
    _arrow(ax, (8.3, 4.1), (8.9, 4.1))
    _arrow(ax, (11.8, 4.1), (12.4, 4.1), "write")
    _arrow(ax, (12.4, 1.3), (10.6, 3.3), "signed resolution", color=ORANGE, off=(-0.75, -0.75))
    _arrow(ax, (12.4, 2.75), (5.7, 1.6), "read state", ls=(0, (3, 2)), color=MUTED, off=(-1.6, 0.12))
    _arrow(ax, (4.4, 2.2), (4.4, 3.3), "", ls=(0, (3, 2)), color=MUTED)
    _arrow(ax, (4.4, 5.0), (4.4, 6.1), "next turn", ls=(0, (3, 2)), color=MUTED, off=(0.62, -0.12))
    _arrow(ax, (2.4, 1.4), (3.1, 1.4))

    for i, (c, e, t) in enumerate(((PURPLE_L, PURPLE, "language model (proposes text)"),
                                   (TEAL_L, TEAL, "deterministic code (decides)"),
                                   (ORANGE_L, ORANGE, "people"), (GREY_L, GREY, "content / plumbing"))):
        ax.add_patch(Rectangle((0.25 + i * 3.9, -0.42), 0.3, 0.26, fc=c, ec=e, lw=1))
        ax.text(0.65 + i * 3.9, -0.29, t, va="center", fontsize=7.5)
    return save(fig, "fig1_architecture", svg=True)


def fig_raju_loop():
    tool = (load("tool_eval.json") or {}).get("methods", {})
    fig, ax = plt.subplots(figsize=(11.2, 4.4))
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 6.2)
    ax.axis("off")
    _box(ax, 0.2, 3.3, 2.5, 1.9, "1 Plan the turn", "planner.plan_session\nrule the learner knows,\nRaju does not; pick item", TEAL_L, TEAL)
    _box(ax, 3.2, 3.3, 2.7, 1.9, "2 Build the task", "classmate._prompt\nHindi meaning, rule title,\nallowed words, last sentence", GREY_L, GREY)
    _box(ax, 6.4, 3.3, 2.4, 1.9, "3 Model drafts", "one JSON sentence\n(up to 3 drafts in the app,\nmethod 'tool')", PURPLE_L, PURPLE)
    _box(ax, 9.3, 3.3, 3.0, 1.9, "4 Leak filter", "exactly the planned mistake?\nno answer, no unseen word,\none sentence, student voice", TEAL_L, TEAL)
    _box(ax, 13.2, 4.3, 2.6, 0.9, "5a Show model\nsentence", "", TEAL_L, TEAL, title_size=7.8)
    _box(ax, 13.2, 3.0, 2.6, 0.9, "5b Show approved\nbank sentence", "", GREY_L, GREY, title_size=7.8)
    _arrow(ax, (2.7, 4.25), (3.2, 4.25))
    _arrow(ax, (5.9, 4.25), (6.4, 4.25))
    _arrow(ax, (8.8, 4.25), (9.3, 4.25), "draft", off=(0, 0.08))
    _arrow(ax, (12.3, 4.75), (13.2, 4.75), "pass", color=TEAL, off=(0, 0.06))
    _arrow(ax, (12.3, 3.6), (13.2, 3.45), "3 fails", color=MUTED, off=(0, -0.42))
    _arrow(ax, (10.8, 3.3), (7.6, 3.3), "fail: reason codes sent back", color=MUTED, rad=-0.45, off=(0, -1.05))
    _box(ax, 6.4, 0.25, 6.5, 1.25, "Research variant 'agentic_tools' (not in the app)",
         "the model chooses when to call check_classmate_sentence,\nthen submits; the filter still re-checks the final sentence", PURPLE_L, PURPLE, title_size=8)
    _box(ax, 0.2, 0.25, 5.7, 1.25, "Either way", "the learner only ever sees a sentence that passed the filter,\nand nothing a model writes can grade or update state", "#FFFFFF", TEAL, title_size=8)
    if tool:
        t, a = tool["tool"], tool["agentic_tools"]
        ax.text(14.5, 1.95, f"measured on {t['n']} cases (task 14):\napp loop: {t['valid_rate']:.0%} model, {t['fallback_rate']:.0%} bank\n"
                f"agentic: {a['valid_rate']:.0%} model, {a['fallback_rate']:.0%} bank", ha="center", va="center",
                fontsize=6.8, color=MUTED, linespacing=1.35)
    ax.text(0.2, 5.75, "Raju's sentence: the model writes, the filter decides", fontsize=10.5, fontweight="bold")
    return save(fig, "fig2_raju_loop", svg=True)


# ------------------------------------------------------------------ data figures


def _dots(ax, rows, xlabel, xlim=(0, 1.02)):
    """rows: (label, rate, lo, hi, colour, note). Horizontal dot-and-interval plot, first row on top."""
    for i, (label, rate, lo, hi, colour, note) in enumerate(rows):
        y = len(rows) - 1 - i
        ax.plot([lo, hi], [y, y], color=colour, lw=2, solid_capstyle="round")
        ax.plot([rate], [y], "o", color=colour, ms=7, mec="white", mew=1.2)
        ax.text(min(hi + 0.02, xlim[1] + 0.02), y, note, va="center", fontsize=7.5, color=MUTED, clip_on=False)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r[0] for r in reversed(rows)], color=INK)
    ax.set_xlim(*xlim)
    ax.set_ylim(-0.6, len(rows) - 0.4)
    ax.set_xlabel(xlabel)
    ax.grid(axis="y", visible=False)


def fig_generation():
    base, tool, abl = load("generation_baselines.json"), load("tool_eval.json"), load("generation_ablation.json")
    have_abl = bool(abl and abl.get("summary", {}).get("conditions"))
    fig, axes = plt.subplots(1, 2 if have_abl else 1, figsize=(11.2 if have_abl else 6.2, 3.7), squeeze=False,
                             gridspec_kw={"wspace": 0.95})
    names = {"prompt_only": "Prompt only (1 draft)", "resample": "Resample (no feedback)",
             "tool": "Harness feedback (app loop)", "agentic_tools": "Model-chosen tool calls"}
    rows = []
    for run, src in (("task 6", base["methods"]), ("task 14", tool["methods"])):
        for m in ("prompt_only", "resample", "tool", "agentic_tools"):
            if m in src:
                n = src[m]["n"]
                k = round(src[m]["valid_rate"] * n)
                p, lo, hi = wilson(k, n)
                colour = PURPLE if m == "agentic_tools" else (TEAL if m == "tool" else GREY)
                rows.append((f"{names[m]} · {run}", p, lo, hi, colour,
                             f"{k}/{n} · {src[m]['tokens_per_case']:.0f} tok"))
    _dots(axes[0][0], rows, "Share of cases where a model sentence passed the filter (Wilson 95%)")
    axes[0][0].set_title("a  Earlier runs (single run each, n = 29)", loc="left")
    if have_abl:
        lab = {"prompt_only": "Prompt only", "tool": "Harness feedback, no memory (app)",
               "tool_history": "Harness feedback + memory (new)", "agentic_tools": "Model-chosen tool calls",
               "prompt_only_noex": "Prompt only, no example sentence", "agentic_noex": "Tool calls, no example sentence"}
        col = {"prompt_only": GREY, "tool": TEAL, "tool_history": TEAL, "agentic_tools": PURPLE,
               "prompt_only_noex": GREY, "agentic_noex": PURPLE}
        rows = []
        for c, v in abl["summary"]["conditions"].items():
            lo, hi = v["pooled_valid_ci95_case_bootstrap"]
            rows.append((lab[c], v["pooled_valid_rate"], lo, hi, col[c],
                         f"{v['rows']} runs · {v['tokens_per_case']:.0f} tok"))
        _dots(axes[0][1], rows, "Share valid, all repeats pooled (95% bootstrap over cases)")
        reps = max(v["repeats"] for v in abl["summary"]["conditions"].values())
        axes[0][1].set_title(f"b  Controlled re-run (29 cases × {reps} repeats)", loc="left")
        for i, (c, v) in enumerate(abl["summary"]["conditions"].items()):
            y = len(rows) - 1 - i
            axes[0][1].plot(list(v["valid_rate_by_repeat"].values()), [y - 0.24] * len(v["valid_rate_by_repeat"]), "|",
                            color=col[c], ms=7, mew=1.2, alpha=0.8)
    fig.suptitle("Raju sentence generation: valid = equals the bank's planted sentence (strict filter)", x=0.01,
                 ha="left", fontsize=10.5, fontweight="bold", y=1.03)
    return save(fig, "fig3_generation")


def fig_checker():
    j = load("judge_eval.json")
    labels, cols = ["correct", "partial", "wrong"], ["correct", "partial", "wrong", "unsure"]
    fig, axes = plt.subplots(1, 3, figsize=(11.2, 3.5), gridspec_kw={"width_ratios": [1.15, 1.15, 1.25], "wspace": 0.42})
    stats = {}
    for ax, key, title, colour in ((axes[0], "checker", "a  Deterministic checker", TEAL),
                                   (axes[1], "llm_judge", "b  Prompt-only LLM judge", PURPLE)):
        conf = j[key]["confusion"]
        m = [[conf.get(f"{h}->{c}", 0) for c in cols] for h in labels]
        cmap = matplotlib.colors.LinearSegmentedColormap.from_list("one", ["#FFFFFF", colour])
        ax.imshow(m, cmap=cmap, vmin=0, vmax=16, aspect="auto")
        for r in range(3):
            for c in range(4):
                ax.text(c, r, m[r][c], ha="center", va="center", fontsize=10,
                        color="white" if m[r][c] >= 10 else INK, fontweight="bold" if cols[c] == labels[r] else "normal")
        ax.set_xticks(range(4))
        ax.set_xticklabels(cols)
        ax.set_yticks(range(3))
        ax.set_yticklabels([f"{h} ({sum(row)})" for h, row in zip(labels, m, strict=True)], color=INK)
        ax.set_xlabel("system label")
        if ax is axes[0]:
            ax.set_ylabel("native-speaker label (n)")
        lo, hi = j[key]["kappa_ci95"]
        ax.set_title(f"{title}\nκ = {j[key]['kappa']:.2f} [{lo:.2f}, {hi:.2f}], accuracy {j[key]['accuracy']:.2f}",
                     loc="left", fontsize=9)
        ax.grid(False)
        for s in ax.spines.values():
            s.set_visible(False)
        rec = {h: m[i][cols.index(h)] / sum(m[i]) for i, h in enumerate(labels)}
        prec = {h: (m[i][cols.index(h)] / max(1, sum(row[cols.index(h)] for row in m))) for i, h in enumerate(labels)}
        f1 = {h: (2 * prec[h] * rec[h] / (prec[h] + rec[h]) if prec[h] + rec[h] else 0.0) for h in labels}
        not_correct = sum(sum(m[i]) for i in (1, 2))
        stats[key] = {"recall": rec, "precision": prec, "macro_f1": sum(f1.values()) / 3,
                      "false_accept": (m[1][0] + m[2][0]) / not_correct, "false_reject": 1 - m[0][0] / sum(m[0]),
                      "abstain": sum(row[3] for row in m) / sum(map(sum, m))}
    ax = axes[2]
    groups = [("recall: correct", "recall", "correct"), ("recall: partial", "recall", "partial"),
              ("recall: wrong", "recall", "wrong"), ("macro-F1", "macro_f1", None),
              ("false acceptance", "false_accept", None), ("false rejection", "false_reject", None),
              ("sent to teacher", "abstain", None)]
    for i, (name, k, sub) in enumerate(groups):
        y = len(groups) - 1 - i
        for dy, key, colour in ((0.17, "checker", TEAL), (-0.17, "llm_judge", PURPLE)):
            v = stats[key][k][sub] if sub else stats[key][k]
            ax.barh(y + dy, v, height=0.3, color=colour)
            ax.text(v + 0.02, y + dy, f"{v:.2f}", va="center", fontsize=7.5, color=MUTED)
    ax.set_yticks(range(len(groups)))
    ax.set_yticklabels([g[0] for g in reversed(groups)], color=INK)
    ax.set_xlim(0, 1.12)
    ax.grid(axis="y", visible=False)
    ax.set_title("c  Per-class and error rates", loc="left", fontsize=9)
    ax.legend(handles=[Rectangle((0, 0), 1, 1, color=TEAL), Rectangle((0, 0), 1, 1, color=PURPLE)],
              labels=["checker", "LLM judge"], loc="lower right")
    fig.suptitle(f"Agreement with one native speaker's labels (n = {j['labelled_rows']} answers, one labeller, "
                 "no human-human ceiling)", x=0.01, ha="left", fontsize=10.5, fontweight="bold", y=1.08)
    (OUT / "fig4_checker_stats.json").write_text(json.dumps(stats, indent=1) + "\n", encoding="utf-8")
    return save(fig, "fig4_checker")


def fig_simulation():
    s1, s2, sens = load("simulation/results.json"), load("simulation_v2/results.json"), load("simulation_sensitivity.json")
    fig, axes = plt.subplots(1, 3, figsize=(11.2, 3.6), gridspec_kw={"width_ratios": [1, 1, 1.55], "wspace": 0.38})
    colours = {"A": ORANGE, "B": GREY, "C": PURPLE}
    names = {"A": "A\ncorrect Raju", "B": "B\nsame content,\nno classmate", "C": "C\nordinary\ntutor"}
    for ax, d, run, title in ((axes[0], s1, "main", "a  sim-0.1 (half-life memory)"),
                              (axes[1], s2, "main_matched_exchanges", "b  sim-0.2 (FSRS memory)")):
        c = d["runs"][run]["conditions"]
        for i, k in enumerate("ABC"):
            v = c[k]["recall_day7"]
            ax.bar(i, v["mean"], width=0.62, color=colours[k])
            ax.errorbar(i, v["mean"], yerr=v["sd"], color=INK, lw=1, capsize=3)
            ax.text(i, v["mean"] + v["sd"] + 0.012, f"{v['mean']:.3f}", ha="center", fontsize=8)
        ax.set_xticks(range(3))
        ax.set_xticklabels([names[k] for k in "ABC"], fontsize=7.5, color=INK)
        ax.set_ylim(0, 0.45)
        ax.set_ylabel("simulated day-7 recall (mean ± SD)" if ax is axes[0] else "")
        ax.set_title(title, loc="left", fontsize=9)
        ax.grid(axis="x", visible=False)
    ax = axes[2]
    if sens:
        styles = [("-", "o"), ("--", "s"), (":", "^"), ("-.", "D"), ((0, (1, 1)), "x")]
        for (name, v), (ls, mk) in zip(sens["variants"].items(), styles, strict=False):
            rows = [r for r in v["rows"] if not isinstance(r["detect"], str)]
            artifact = "artifact" in name
            ax.plot([r["detect"] for r in rows], [r["A_minus_B"] for r in rows], ls=ls, marker=mk, ms=4, lw=1.5,
                    color=GREY if artifact else ORANGE, label=name)
        ax.axhline(0, color=INK, lw=0.8)
        ax.set_xlabel("assumed probability that the learner notices Raju's error")
        ax.set_ylabel("A − B, simulated day-7 recall")
        ax.set_title("c  sim-0.2 under changed assumptions", loc="left", fontsize=9)
        ax.legend(loc="upper left", bbox_to_anchor=(0.0, -0.2), ncols=1, fontsize=7)
        ax.text(0.98, 0.012, "A better", transform=ax.get_yaxis_transform(), ha="right", va="bottom", fontsize=7,
                color=MUTED)
        ax.text(0.98, -0.012, "B better", transform=ax.get_yaxis_transform(), ha="right", va="top", fontsize=7,
                color=MUTED)
    fig.suptitle("SIMULATED learners only (100 per condition): the two simulators order A, B, C differently",
                 x=0.01, ha="left", fontsize=10.5, fontweight="bold", y=1.04)
    return save(fig, "fig5_simulation")


def fig_capabilities():
    tool, reas, rag, ag, ft = (load("tool_eval.json"), load("reasoning_eval.json"), load("rag_eval.json"),
                               load("agentic_eval.json"), load("ft_eval.json"))
    r = reas["results"]["stage_a"]
    pos = {k: v["positives"]["shown_and_usable"] for k, v in rag["conditions"].items()}
    rows = []

    def add(group, label, k, n, colour, tokens=None):
        p, lo, hi = wilson(k, n)
        rows.append((group, label, p, lo, hi, colour, f"{k}/{n}" + (f" · {tokens:.0f} tok" if tokens else "")))

    t = tool["methods"]
    for m, lab, c in (("prompt_only", "prompt only", GREY), ("tool", "harness feedback", TEAL),
                      ("agentic_tools", "model-chosen tools", PURPLE)):
        add("Tool calling\nRaju sentence valid", lab, round(t[m]["valid_rate"] * t[m]["n"]), t[m]["n"], c,
            t[m]["tokens_per_case"])
    for m, lab, c in (("direct", "direct answer", GREY), ("no_self_check", "3 steps", PURPLE),
                      ("stepwise", "3 steps + self-check", PURPLE)):
        add("Stepwise reasoning\ndiagnosis all right", lab, round(r[m]["final_accuracy"] * r[m]["cases"]), r[m]["cases"], c,
            r[m]["tokens_per_case"])
    for m, lab, c in (("a_blind", "no retrieval", GREY), ("b_rag", "RAG (planned)", PURPLE),
                      ("c_oracle_retrieval", "oracle rule given", GREY), ("b_fixed_posthoc", "RAG, post-hoc fix*", PURPLE)):
        add("Retrieval (RAG)\nusable coach hint", lab, pos[m]["k"], pos[m]["n"], c)
    g = ag["results"]
    for m, lab, c in (("single_agent", "single agent", GREY), ("multi_agent", "separate roles + checker", TEAL)):
        add("Role separation\nwhole task right", lab, round(g[m]["task_success_rate"] * g[m]["evaluable"]), g[m]["evaluable"],
            c, g[m]["tokens_per_case"])
    for m, lab, c in (("gemini_prompted", "gemini-3.5-flash prompted", GREY), ("gemma3_1b_base", "Gemma-3-1B untuned", PURPLE)):
        v = ft["conditions"][m]["primary_all_29"]["valid"]
        add("Small model\nRaju sentence valid", lab, v["k"], v["n"], c)

    fig, ax = plt.subplots(figsize=(8.6, 6.8))
    y, ticks, last, bands = 0, [], None, []
    for group, label, p, lo, hi, colour, note in rows:
        if group != last:
            y -= 1.5 if last else 0
            bands.append((group, y + 0.85))
            last = group
        ax.plot([lo, hi], [y, y], color=colour, lw=2, solid_capstyle="round")
        ax.plot([p], [y], "o", color=colour, ms=7, mec="white", mew=1.2)
        ax.text(1.03, y, note, va="center", fontsize=7.5, color=MUTED, clip_on=False)
        ticks.append((y, label))
        y -= 1
    ax.set_yticks([t[0] for t in ticks])
    ax.set_yticklabels([t[1] for t in ticks], color=INK)
    for group, top in bands:
        ax.text(-0.52, top, group.replace("\n", " · "), transform=ax.get_yaxis_transform(), va="center", ha="left",
                fontsize=8.5, fontweight="bold")
    ax.set_xlim(0, 1.0)
    ax.set_ylim(y + 0.4, 1.4)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Success rate on the frozen cases (Wilson 95% interval)")
    ax.set_title("Each model capability against its baseline (gemini-3.5-flash, single run each)", loc="left", x=-0.52)
    ax.text(-0.52, -0.09, "grey = baseline or reference · purple = model capability under test · teal = deterministic "
            "harness.   * designed after seeing these cases (optimistic).", transform=ax.transAxes, fontsize=7, color=MUTED)
    fig.subplots_adjust(left=0.42)
    return save(fig, "fig6_capabilities")


# ------------------------------------------------------------------ poster variants (larger type, one message each)

POSTER_RC = {"font.size": 13, "axes.titlesize": 14, "axes.labelsize": 13, "xtick.labelsize": 12, "ytick.labelsize": 12.5,
             "legend.fontsize": 12}


def fig_poster_generation():
    abl, tool = load("generation_ablation.json"), load("tool_eval.json")
    with plt.rc_context(POSTER_RC):
        fig, ax = plt.subplots(figsize=(7.4, 4.6))
        rows = []
        if abl and abl.get("summary", {}).get("conditions"):
            lab = {"prompt_only": "Prompt only", "tool": "Harness check,\nno memory (app)",
                   "tool_history": "Harness check\n+ memory", "agentic_tools": "Model-chosen\ntool calls",
                   "prompt_only_noex": "Prompt only,\nno example", "agentic_noex": "Tool calls,\nno example"}
            col = {"prompt_only": GREY, "tool": TEAL, "tool_history": TEAL, "agentic_tools": PURPLE,
                   "prompt_only_noex": GREY, "agentic_noex": PURPLE}
            for c, v in abl["summary"]["conditions"].items():
                lo, hi = v["pooled_valid_ci95_case_bootstrap"]
                rows.append((lab[c], v["pooled_valid_rate"], lo, hi, col[c],
                             f"{v['pooled_valid_rate']:.2f} · {v['tokens_per_case']:.0f} tok"))
            xlabel = "Raju sentence valid (29 cases × repeats, 95% CI)"
        else:
            for m, name, c in (("prompt_only", "Prompt only", GREY), ("tool", "Harness check (app)", TEAL),
                               ("agentic_tools", "Model-chosen\ntool calls", PURPLE)):
                v = tool["methods"][m]
                k = round(v["valid_rate"] * v["n"])
                p, lo, hi = wilson(k, v["n"])
                rows.append((name, p, lo, hi, c, f"{k}/{v['n']} · {v['tokens_per_case']:.0f} tok"))
            xlabel = "Raju sentence valid (n = 29, Wilson 95%)"
        for i, (label, rate, lo, hi, colour, note) in enumerate(rows):
            y = len(rows) - 1 - i
            ax.plot([lo, hi], [y, y], color=colour, lw=4, solid_capstyle="round")
            ax.plot([rate], [y], "o", color=colour, ms=12, mec="white", mew=2)
            ax.text(1.04, y, note, va="center", fontsize=11.5, color=MUTED, clip_on=False)
        ax.set_yticks(range(len(rows)))
        ax.set_yticklabels([r[0] for r in reversed(rows)], color=INK)
        ax.set_xlim(0, 1.0)
        ax.set_ylim(-0.6, len(rows) - 0.4)
        ax.set_xlabel(xlabel)
        ax.grid(axis="y", visible=False)
        fig.subplots_adjust(left=0.27, right=0.76)
        return save(fig, "poster_generation")


def fig_poster_checker_sim():
    j, s1, s2 = load("judge_eval.json"), load("simulation/results.json"), load("simulation_v2/results.json")
    with plt.rc_context(POSTER_RC):
        fig, axes = plt.subplots(1, 2, figsize=(7.4, 4.3), gridspec_kw={"width_ratios": [1, 1.25], "wspace": 0.42})
        ax = axes[0]
        for i, (key, name, colour) in enumerate((("checker", "Rule\nchecker", TEAL), ("llm_judge", "LLM\njudge", PURPLE))):
            k, (lo, hi) = j[key]["kappa"], j[key]["kappa_ci95"]
            ax.bar(i, k, width=0.58, color=colour)
            ax.errorbar(i, k, yerr=[[k - lo], [hi - k]], color=INK, lw=1.6, capsize=5)
            ax.text(i, hi + 0.03, f"{k:.2f}", ha="center", fontsize=13, fontweight="bold")
        ax.axhline(0.6, color=INK, lw=1, ls=(0, (4, 3)))
        ax.text(-0.42, 0.615, "target 0.6", ha="left", fontsize=11, color=MUTED)
        ax.set_xticks([0, 1])
        ax.set_xticklabels(["Rule\nchecker", "LLM\njudge"], color=INK)
        ax.set_ylim(-0.08, 0.8)
        ax.set_ylabel(f"κ with native labels (n = {j['labelled_rows']})")
        ax.grid(axis="x", visible=False)
        ax.set_title("Checker agreement", loc="left")
        ax = axes[1]
        colours = {"A": ORANGE, "B": GREY, "C": PURPLE}
        for g, (d, run) in enumerate(((s1, "main"), (s2, "main_matched_exchanges"))):
            for i, k in enumerate("ABC"):
                v = d["runs"][run]["conditions"][k]["recall_day7"]["mean"]
                ax.bar(g * 4 + i, v, width=0.82, color=colours[k])
                ax.text(g * 4 + i, v + 0.008, k, ha="center", fontsize=12, fontweight="bold")
        ax.set_xticks([1, 5])
        ax.set_xticklabels(["simulator 1", "simulator 2"], color=INK)
        ax.set_ylim(0, 0.4)
        ax.set_ylabel("simulated day-7 recall")
        ax.grid(axis="x", visible=False)
        ax.set_title("Simulated learners", loc="left")
        fig.text(0.5, -0.06, "A correct Raju · B same content, no Raju · C ordinary tutor (simulation, not people)",
                 ha="center", fontsize=11, color=MUTED)
        return save(fig, "poster_checker_sim")


def main():
    made = [fig_architecture(), fig_raju_loop(), fig_generation(), fig_checker(), fig_simulation(), fig_capabilities(),
            fig_poster_generation(), fig_poster_checker_sim()]
    print("\n".join(str(OUT / f"{m}.pdf") for m in made))


if __name__ == "__main__":
    main()
