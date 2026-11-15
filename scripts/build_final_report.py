"""Build the final report (HTML + PDF) from the team's drafts and result files.

    python -m scripts.build_final_report     # docs/submission/report/SETU_final_report.{html,pdf}

The text comes from docs/submission/drafts/*.md (which cite reports/ for every number); the recall chart is reused from
the mid-submission report; screenshots are optional (docs/submission/screenshots/final-*.png). PDF via Playwright's
Chromium if installed, else headless Chrome.
"""
import base64
import re
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "docs/submission/drafts"
OUT = ROOT / "docs/submission/report"
MD = ["extra", "sane_lists"]


def read(name):
    return (D / name).read_text(encoding="utf-8")


def section(text, start, end=None):
    i = text.index(start)
    j = text.index(end, i + len(start)) if end else len(text)
    return text[i:j].strip()


def demote(text, by=1):
    return re.sub(r"^(#+) ", lambda m: "#" * (len(m.group(1)) + by) + " ", text, flags=re.MULTILINE)


def render(text):
    # python-markdown needs a blank line before a list that follows a paragraph
    text = re.sub(r"([^\n-][^\n]*)\n(?=(?:- |\d+\. ))", r"\1\n\n", text)
    return markdown.markdown(text, extensions=MD)


def main():
    css = re.search(r"<style>(.*?)</style>", (OUT / "SETU_mid_submission_report.html").read_text(encoding="utf-8"), re.DOTALL).group(1)
    mid = (OUT / "SETU_mid_submission_report.html").read_text(encoding="utf-8")
    chart = re.search(r'<div class="legend">.*?</div>', mid, re.DOTALL).group(0) + re.search(r'<svg viewBox="0 0 760 300".*?</svg>', mid, re.DOTALL).group(0)
    ana, goals, ui = read("faviana_analysis_20_23.md"), read("faviana_goals_alignment.md"), read("faviana_final_report_sections.md")
    team = read("team_contribution_faviana.md")

    parts = []
    parts.append("""<header><p class="kicker">Final report · 15 November 2026 · Token Guessers (LMA course project)</p>
<h1>SETU: a Hindi-first Telugu tutor in which the learner teaches an AI classmate</h1>
<p class="sub">Rule: <i>models write, rules decide.</i> What we built, what we measured on five model capabilities, where it failed, and what it cost.</p>
<p class="meta">Team: Madhav Malhotra, Kushal Karan, Faviana Noronha, Shaik Areesh · Code: github.com/MadhavM99/setu-tutor (branch <code>faviana-noronha</code>) ·
mid-submission report: <code>docs/submission/report/SETU_mid_submission_report.pdf</code></p></header>""")
    parts.append("""<section class="summary"><h2>Summary</h2><ul>
<li><b>Built:</b> a working Hindi-interface tutor (FastAPI, PostgreSQL) with a six-level path from Telugu letters to conversations, a classmate (Raju) who writes sentences with one planted Hindi habit, a hint-only coach, and a teacher console. 1,287 tests pass.</li>
<li><b>Control held:</b> no model decided a grade or changed memory (0 model-decided verdicts in the multi-agent setup against 65 in the single agent); the checker was not fooled by 25 tricks. One check failed: the unsure rate was 0.18 against a ceiling of 0.15.</li>
<li><b>Capabilities:</b> tool calling made Raju's sentences valid 0.93–0.97 of the time against 0.72 for prompting alone, at about 7.5 times the tokens. Stepwise reasoning, retrieval (RAG) and multi-agent roles did not improve accuracy; fine-tuning was a no-go for lack of data (23 usable pairs, 200 needed).</li>
<li><b>Honest limits:</b> no learner has used the system, the two simulations disagree on whether correcting Raju helps, the checker agrees with native labels less than a prompt-only judge (κ 0.15 against 0.46), and no native speaker has reviewed the Telugu.</li></ul></section>""")

    parts.append("<h2>1. Problem statement and goals</h2>")
    parts.append(render(demote(section(goals, "## Problem statement (paste-ready)", "## What has to change"), 0).replace("## Problem statement (paste-ready)", "### Problem statement").replace("## Goals", "### Goals").replace("## Research questions, and what we can answer today", "### Research questions and what we can answer today")))

    parts.append("<h2>2. The system and the interface additions</h2>")
    parts.append(render(demote(section(ui, "## A. The beginner on-ramp and interface (UI work)", "## B."), 0).replace("## A. The beginner on-ramp and interface (UI work)", "").strip()))
    shots = [(ROOT / f"docs/submission/screenshots/final-{n}.png", c) for n, c in
             [("home", "Home: path map, Raju card"), ("ladder", "Progress: what Raju learned"), ("en-word", "English under the word"), ("match", "Match game")]]
    imgs = [(p, c) for p, c in shots if p.exists()]
    if imgs:
        cells = "".join(f'<figure><img src="data:image/png;base64,{base64.b64encode(p.read_bytes()).decode()}" style="width:100%;border:1px solid #e6dfd3;border-radius:6px"><figcaption>{c}</figcaption></figure>' for p, c in imgs)
        parts.append(f'<div style="display:grid;grid-template-columns:repeat({len(imgs)},1fr);gap:8px">{cells}</div>')

    t20 = section(ana, "## Task 20: results tables (summary)", "## Task 21")
    parts.append("<h2>3. Results (task 20)</h2><p class=\"note\">Rates are k/n with Wilson 95% intervals. The frozen sets are small (29, 58 and 50 cases), so read the intervals, not the point differences. Full tables: <code>reports/results_tables.md</code>.</p>")
    parts.append(render(demote(t20.split("\n", 1)[1], 0)))
    parts.append("<h3>Simulated learners (not evidence about people)</h3>" + chart +
                 "<p class=\"note\">Day-7 recall by condition: in the first simulation correcting Raju (A) beat matched examples (B) but not a conventional tutor (C); in the improved one, which shares the app's memory model, A finished last (A 0.253, B 0.329, C 0.306). The two disagree because they model memory differently.</p>")

    parts.append("<h2>4. Qualitative examples (task 21)</h2>")
    parts.append(render(section(ana, "## Task 21: qualitative examples", "## Task 22").split("\n", 1)[1]))
    parts.append("<h2>5. Failure analysis (task 22)</h2>")
    parts.append(render(section(ana, "## Task 22: failure analysis per capability", "## Task 23").split("\n", 1)[1]))
    parts.append("<h2>6. Compute report (task 23)</h2>")
    parts.append(render(section(ana, "## Task 23: compute report", "## Before this goes").split("\n", 1)[1]))
    parts.append("<h2>7. Results by team member</h2>")
    parts.append(render(demote(section(ana, "## Appendix: results by team member (taken from their branches)").split("\n", 1)[1], -0).replace("### ", "### ")))
    parts.append("<h2>8. Team contribution</h2>")
    parts.append(render(section(team, "## Faviana's contribution").replace("## Faviana's contribution", "### Faviana Noronha") + "\n\n" +
                        section(team, "## Others (from the git history", "## Process notes").replace("## Others (from the git history; each person should confirm and correct their own row)", "### Others (from the git history; each person should confirm their own row)") + "\n\n" +
                        section(team, "## Process notes (for the honesty section)").replace("## Process notes (for the honesty section)", "### Process notes")))
    parts.append("<h2>9. Limitations</h2>")
    parts.append(render(section(ui, "## D. Limitations to state plainly").split("\n", 1)[1]))
    parts.append("<h2>10. Reproducibility</h2><p>Every number is in a file under <code>reports/</code>; <code>python -m setu.research.results_tables</code> regenerates the tables from the saved JSON, and <code>python -m scripts.build_final_report</code> rebuilds this report. Hosted-model runs used gemini-3.5-flash with reasoning off; the one local model run was Gemma-3-1B on CPU. Run the demo with <code>scripts/run_demo.sh</code>.</p>")

    body = "\n".join(parts)
    html = f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>SETU final report</title><style>{css}</style></head><body>{body}</body></html>'
    (OUT / "SETU_final_report.html").write_text(html, encoding="utf-8")
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch(); pg = b.new_page()
            pg.goto((OUT / "SETU_final_report.html").as_uri()); pg.pdf(path=str(OUT / "SETU_final_report.pdf"), format="A4", print_background=True,
                                                                          margin={"top": "16mm", "bottom": "16mm", "left": "14mm", "right": "14mm"})
            b.close()
    except ImportError:
        import subprocess
        subprocess.run(["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "--headless", "--no-pdf-header-footer",
                        f"--print-to-pdf={OUT / 'SETU_final_report.pdf'}", (OUT / "SETU_final_report.html").as_uri()], check=True)


if __name__ == "__main__":
    main()
