"""Build the IIIT-H research poster (A1 landscape) from the supplied template, plus a PDF export.

    pip install -e ".[figures]"                 # matplotlib and python-pptx
    python -m scripts.make_figures
    python -m scripts.build_poster              # docs/submission/poster/SETU_poster.{pptx,html,pdf}

- `SETU_poster.pptx` is the editable poster: the template file itself with its text boxes filled and its image
  placeholders replaced, so the three-column layout, panel colours and fonts are the template's.
- `SETU_poster.pdf` is printed from `SETU_poster.html`, which places the same text and figures at the same positions
  (no PowerPoint renderer is installed, so the PDF is not a render of the .pptx; check the .pptx in PowerPoint or
  Google Slides before printing).
Numbers are read from reports/ at build time.
"""
import base64
import html
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "resources/A1 size Landscape Research poster - new.pptx"
OUT = ROOT / "docs/submission/poster"
FIGS = ROOT / "docs/submission/figures"
SHOTS = ROOT / "docs/submission/screenshots/audit-2026-11-15"
R = ROOT / "reports"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
W, H = 33.1007, 23.3993  # inches, from the template
PURPLE, PANEL, CENTRE, SUB = "47247B", "E1EDEB", "EFEAE4", "F2F2F2"

TITLE = "SETU: Learning Telugu by Correcting a Rule-Governed AI Classmate"
SUBTITLE = "Models write, rules decide: what held up, and what did not"
AUTHORS = "Madhav Malhotra · Kushal Karan · Faviana Noronha · Shaik Areesh  (Team Token Guessers)"
EMAIL = "[add institute email IDs]"  # not in the repository: do not guess
INSTITUTE = ("IIIT Hyderabad", "Language Models and Agents · Monsoon 2026")
ACK = ("[Add the course instructor and TAs.] One team member, a native Telugu speaker, labelled the 50 answers. "
       "An AI coding assistant was used for programming, analysis and drafting; the authors checked every number.")
REFS = [
    "Chase et al. 2009. Teachable agents and the protégé effect. J. Sci. Educ. Technol. 18(4).",
    "Alemdag, Eichelmann, Narciss 2025. Learning from erroneous examples: framework and meta-analysis. Rev. Educ. Res.",
    "Jin et al. 2024. Teach AI how to code: LLMs as teachable agents. CHI.",
    "Yuan et al. 2026. Towards valid student simulation with LLMs. arXiv:2601.05473.",
    "Debenedetti et al. 2025. Defeating prompt injections by design. arXiv:2503.18813.",
    "Ye, Su, Cao 2022. Optimizing spaced repetition scheduling (FSRS). KDD.",
    "Code and all result files: github.com/MadhavM99/setu-tutor",
]


def load(name):
    return json.loads((R / name).read_text(encoding="utf-8"))


def content() -> dict:
    tool, judge, abl = load("tool_eval.json"), load("judge_eval.json"), load("generation_ablation.json")
    s2, sens = load("simulation_v2/results.json"), load("simulation_sensitivity.json")
    reas, rag = load("reasoning_eval.json")["results"]["stage_a"], load("rag_eval.json")["conditions"]
    A = abl["summary"]["conditions"]
    c2 = s2["runs"]["main_matched_exchanges"]["conditions"]
    w = sens["without_artifact_variant"]
    ha, ia = tool["harness_attacks"], tool["injected_attacks"]
    ratio = A["agentic_tools"]["tokens_per_case"] / A["tool_history"]["tokens_per_case"]
    return {
        "abstract": [
            ("SETU teaches Telugu to Hindi speakers. At the sentence stage the learner corrects Raju, an AI classmate "
            "who makes a Hindi speaker's mistakes. Raju's knowledge is data in a database, kept one step behind the "
            "learner's."),
            ("One rule governs the design: a language model may write text, but ordinary code decides what is shown, "
            "how an answer is marked and what the learner's record says."),
            ("We built the tutor, attacked it, compared five model capabilities with simpler baselines, and checked "
            "the marker against a native speaker. No learner has used it yet: learning outcomes are simulated only."),
        ],
        "method": [
            "Ladder: letters → syllables → words → phrases → sentence rules (Raju) → scenes.",
            ("Raju's sentence, the coach's hint and the friend's line are model proposals. Each passes a filter or is "
            "replaced by teacher-approved text."),
            "A rule-based checker marks every answer: correct, partial, wrong or unsure. Unsure goes to a teacher.",
            "One writer, under a restricted database role, updates the record. Models have no write tools.",
            ("Evaluation: one hosted model (gemini-3.5-flash), frozen sets of 29–58 cases, Wilson intervals, exact "
            "McNemar tests, 50 native-speaker labels, two learner simulators."),
        ],
        "method_caption": "The running app: Raju's sentence, the coach's hint, the learner's home page.",
        "results": [
            ("Control held.", (f"{ha['n']}/{ha['n']} tool attacks refused; {ia['evaluable']} injected instructions, "
                              "no unsafe attempt. No model text reached a learner unchecked.")),
            ("The model did not need to choose.", (f"A fixed loop that shows the model its own rejected draft: "
                                                  f"{A['tool_history']['pooled_valid_rate']:.2f} valid. Model-chosen tool calls: "
                                                  f"{A['agentic_tools']['pooled_valid_rate']:.2f}, at {ratio:.1f}× the tokens.")),
            ("Most capabilities did not beat baselines.", (f"Stepwise reasoning {reas['stepwise']['final_accuracy']:.2f} vs "
                                                          f"{reas['direct']['final_accuracy']:.2f} direct. Retrieval hints "
                                                          f"{rag['b_rag']['positives']['shown_and_usable']['k']}/29 vs "
                                                          f"{rag['a_blind']['positives']['shown_and_usable']['k']}/29. Fine-tuning: stopped, too "
                                                          "little validated data.")),
            ("The checker is safe but coarse.", (f"It never accepted a wrong answer, yet agrees poorly with a native "
                                                f"speaker: κ = {judge['checker']['kappa']:.2f} (target 0.6).")),
        ],
        "arch_caption": "Purple: language model, text only. Teal: deterministic code. Dashed line: the only code that can change learner state.",
        "cap_head": "MODEL CAPABILITIES",
        "cap_text": [
            f"Prompt only: {A['prompt_only']['pooled_valid_rate']:.2f}. Old app loop (no memory): {A['tool']['pooled_valid_rate']:.2f}.",
            (f"Add memory of the rejected draft (the app now): {A['tool_history']['pooled_valid_rate']:.2f} at "
            f"{A['tool_history']['tokens_per_case']:.0f} tokens."),
            f"Model-chosen tools: {A['agentic_tools']['pooled_valid_rate']:.2f} at {A['agentic_tools']['tokens_per_case']:.0f} tokens.",
            "\"Valid\" means equal to the bank's sentence: the model adds no new sentence.",
        ],
        "chk_head": "CHECKER · SIMULATION",
        "chk_text": [
            f"Checker κ {judge['checker']['kappa']:.2f} vs model judge {judge['llm_judge']['kappa']:.2f}; one labeller, 50 answers.",
            "It rejects half the answers the native speaker accepted.",
            (f"Simulation only: correcting Raju (A) ranks last, {c2['A']['recall_day7']['mean']:.2f} vs "
            f"{c2['B']['recall_day7']['mean']:.2f} and {c2['C']['recall_day7']['mean']:.2f}, in "
            f"{w['cells_where_A_is_last']}/{w['cells']} assumption settings. An older simulator disagrees."),
        ],
        "conclusion": [
            "A model can be confined to proposing text, with marks and records owned by code.",
            "For Raju's sentence, memory of the last draft mattered; model-chosen tool calls did not add to it.",
            "Not shown: that correcting a classmate helps anyone learn. No learner data exists.",
            ("Done after the audit: the app now uses the memory loop; the filter is unchanged. Next: independent native "
            "review and a second labeller; widen accepted answers; then a small pilot with consent and clearance."),
        ],
    }


# ------------------------------------------------------------------ PPTX (the template, filled in)


def build_pptx(c: dict, path: Path):
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.util import Inches, Pt

    prs = Presentation(str(TEMPLATE))
    slide = prs.slides[0]
    by_id = {s.name.split(";")[1]: s for s in slide.shapes}

    def place(shape, x, y, w, h):
        shape.left, shape.top, shape.width, shape.height = Inches(x), Inches(y), Inches(w), Inches(h)

    def fill(shape, paras, size, bold_first=False, colour=None, space=6):
        """paras: list of str or (bold lead, rest). Rewrites the text frame keeping the template's font."""
        tf = shape.text_frame
        tf.word_wrap = True
        for extra in list(tf.paragraphs)[1:]:
            extra._p.getparent().remove(extra._p)
        for i, para in enumerate(paras):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            for r in list(p.runs):
                r._r.getparent().remove(r._r)
            parts = [(para[0] + " ", True), (para[1], False)] if isinstance(para, tuple) else [(para, bold_first)]
            for text, bold in parts:
                run = p.add_run()
                run.text = text
                run.font.size, run.font.name, run.font.bold = Pt(size), "Arial", bold
                if colour:
                    run.font.color.rgb = RGBColor.from_string(colour)
            p.space_after = Pt(space)

    def picture(placeholder_id, file: Path, x, y, w):
        ph = by_id[placeholder_id]
        ph._element.getparent().remove(ph._element)
        return slide.shapes.add_picture(str(file), Inches(x), Inches(y), width=Inches(w))

    place(by_id["108"], 0.45, 0.35, 22.2, 2.4)
    fill(by_id["108"], [TITLE, SUBTITLE], 54, bold_first=True)
    by_id["108"].text_frame.paragraphs[1].runs[0].font.size = Pt(34)
    by_id["108"].text_frame.paragraphs[1].runs[0].font.bold = False
    fill(by_id["103"], [INSTITUTE[0]], 54)
    fill(by_id["104"], [INSTITUTE[1]], 22)
    place(by_id["104"], 25.4, 4.5, 7.1, 0.6)
    place(by_id["103"], 25.4, 3.3, 7.1, 1.2)
    fill(by_id["86"], c["abstract"], 24, space=10)
    fill(by_id["91"], ["• " + m for m in c["method"]], 22, space=7)
    place(by_id["91"], 0.7, 11.85, 8.85, 5.9)
    x = 0.8
    ph = by_id["98"]
    ph._element.getparent().remove(ph._element)
    for name in ("05-raju-planted-mobile.png", "06-coach-hint-mobile.png", "01-home-mobile.png"):
        slide.shapes.add_picture(str(SHOTS / name), Inches(x), Inches(17.75), height=Inches(4.0))
        x += 2.0
    cap = slide.shapes.add_textbox(Inches(6.85), Inches(18.6), Inches(2.75), Inches(2.6))
    fill(cap, [c["method_caption"]], 18)
    # centre top: findings + architecture
    place(by_id["88"], 10.3, 4.1, 5.5, 7.8)
    fill(by_id["88"], c["results"], 21, space=9)
    picture("94", FIGS / "fig1_architecture.png", 15.95, 3.45, 8.95)
    cap = slide.shapes.add_textbox(Inches(15.95), Inches(9.05), Inches(8.95), Inches(1.5))
    fill(cap, [c["arch_caption"]], 17)
    # centre bottom panels
    fill(by_id["110"], [c["cap_head"]], 30, bold_first=True, colour=PURPLE)
    place(by_id["110"], 10.34, 12.42, 6.9, 0.64)
    picture("112", FIGS / "poster_generation.png", 10.2, 13.1, 7.0)
    place(by_id["111"], 10.3, 17.55, 6.85, 4.3)
    fill(by_id["111"], ["• " + t for t in c["cap_text"]], 19, space=5)
    fill(by_id["96"], [c["chk_head"]], 30, bold_first=True, colour=PURPLE)
    place(by_id["96"], 17.98, 12.42, 6.9, 0.64)
    picture("105", FIGS / "poster_checker_sim.png", 17.85, 13.1, 6.95)
    place(by_id["97"], 17.95, 17.55, 6.85, 4.3)
    fill(by_id["97"], ["• " + t for t in c["chk_text"]], 19, space=5)
    # right column
    place(by_id["102"], 25.45, 7.1, 6.95, 6.3)
    fill(by_id["102"], ["• " + t for t in c["conclusion"]], 21, space=8)
    place(by_id["100"], 25.45, 13.55, 6.99, 0.64)
    place(by_id["92"], 25.45, 14.15, 6.95, 2.3)
    fill(by_id["92"], [ACK], 17)
    place(by_id["101"], 25.45, 16.55, 6.99, 0.64)
    place(by_id["93"], 25.45, 17.2, 6.95, 4.7)
    fill(by_id["93"], [f"[{i}] {r}" for i, r in enumerate(REFS, 1)], 15, space=3)
    place(by_id["106"], 0.75, 22.35, 20.5, 0.64)
    fill(by_id["106"], [("Authors:", AUTHORS)], 26)
    place(by_id["107"], 21.6, 22.35, 11.0, 0.64)
    fill(by_id["107"], [("email ID:", EMAIL)], 26)
    prs.save(str(path))


# ------------------------------------------------------------------ HTML mirror -> PDF


def _img(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def build_html(c: dict) -> str:
    e = html.escape

    def box(x, y, w, h, inner, style=""):
        return f'<div style="position:absolute;left:{x}in;top:{y}in;width:{w}in;height:{h}in;{style}">{inner}</div>'

    def head(x, y, w, text):
        return box(x, y, w, 0.64, e(text), f"font-size:32pt;font-weight:700;color:#{PURPLE}")

    def bullets(items, size, gap=7):
        return "".join(f'<p style="font-size:{size}pt;margin:0 0 {gap}pt">• {e(t)}</p>' for t in items)

    def paras(items, size, gap=10):
        out = ""
        for t in items:
            body = f"<b>{e(t[0])}</b> {e(t[1])}" if isinstance(t, tuple) else e(t)
            out += f'<p style="font-size:{size}pt;margin:0 0 {gap}pt">{body}</p>'
        return out

    P = [box(23.06, 0.27, 6.48, 1.83, "", "background:#D0C4EE"),
         box(0.45, 0.35, 22.2, 2.4, f'<div style="font-size:54pt;font-weight:700;line-height:1.08">{e(TITLE)}</div>'
                                    f'<div style="font-size:34pt;margin-top:8pt">{e(SUBTITLE)}</div>'),
         box(25.26, 3.13, 7.39, 2.15, f'<div style="font-size:54pt;text-align:center;margin-top:.15in">{e(INSTITUTE[0])}</div>'
                                      f'<div style="font-size:22pt;text-align:center">{e(INSTITUTE[1])}</div>',
             "border:2.25pt solid #7030A0;box-sizing:border-box"),
         box(0.45, 3.16, 9.31, 7.52, "", f"background:#{PANEL}"), head(0.75, 3.45, 8.8, "ABSTRACT"),
         box(0.8, 4.15, 8.66, 6.4, paras(c["abstract"], 24)),
         box(0.47, 10.94, 9.31, 11.09, "", f"background:#{PANEL}"), head(0.59, 11.26, 8.7, "METHODOLOGY"),
         box(0.7, 11.85, 8.85, 5.9, bullets(c["method"], 22))]
    x = 0.8
    for name in ("05-raju-planted-mobile.png", "06-coach-hint-mobile.png", "01-home-mobile.png"):
        P.append(box(x, 17.75, 1.85, 4.0, f'<img src="{_img(SHOTS / name)}" style="height:4in;border:1px solid #bbb">'))
        x += 2.0
    P += [box(6.85, 18.6, 2.75, 2.6, f'<p style="font-size:18pt;margin:0">{e(c["method_caption"])}</p>'),
          box(10.01, 3.16, 15.02, 8.87, "", f"background:#{CENTRE}"), head(10.37, 3.45, 5.4, "RESULTS"),
          box(10.3, 4.1, 5.5, 7.8, paras(c["results"], 21, 9)),
          box(15.95, 3.45, 8.95, 5.5, f'<img src="{_img(FIGS / "fig1_architecture.png")}" style="width:100%">'),
          box(15.95, 9.05, 8.95, 1.5, f'<p style="font-size:17pt;margin:0">{e(c["arch_caption"])}</p>'),
          box(9.98, 12.24, 7.42, 9.83, "", f"background:#{SUB};border-radius:.35in"), head(10.34, 12.42, 6.9, c["cap_head"]),
          box(10.2, 13.1, 7.0, 4.4, f'<img src="{_img(FIGS / "poster_generation.png")}" style="width:100%">'),
          box(10.3, 17.55, 6.85, 4.3, bullets(c["cap_text"], 19, 5)),
          box(17.61, 12.2, 7.42, 9.83, "", f"background:#{SUB};border-radius:.35in"), head(17.98, 12.42, 6.9, c["chk_head"]),
          box(17.85, 13.1, 6.95, 4.4, f'<img src="{_img(FIGS / "poster_checker_sim.png")}" style="width:100%">'),
          box(17.95, 17.55, 6.85, 4.3, bullets(c["chk_text"], 19, 5)),
          box(25.26, 5.51, 7.32, 16.58, "", f"background:#{PANEL}"),
          box(25.45, 5.88, 7.0, 1.18, "CONCLUSION AND FUTURE WORK", f"font-size:32pt;font-weight:700;color:#{PURPLE};line-height:1.1"),
          box(25.45, 7.1, 6.95, 6.3, bullets(c["conclusion"], 21, 8)), head(25.45, 13.55, 6.9, "ACKNOWLEDGMENT"),
          box(25.45, 14.15, 6.95, 2.3, f'<p style="font-size:17pt;margin:0">{e(ACK)}</p>'), head(25.45, 16.55, 6.9, "REFERENCES"),
          box(25.45, 17.2, 6.95, 4.7, "".join(f'<p style="font-size:15pt;margin:0 0 3pt">[{i}] {e(r)}</p>' for i, r in enumerate(REFS, 1))),
          box(0.75, 22.35, 20.5, 0.64, f'<span style="font-size:26pt"><b>Authors:</b> {e(AUTHORS)}</span>'),
          box(21.6, 22.35, 11.0, 0.64, f'<span style="font-size:26pt"><b>email ID:</b> {e(EMAIL)}</span>')]
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>SETU poster</title><style>@page{{size:{W}in {H}in;margin:0}}'
            f'body{{margin:0;width:{W}in;height:{H}in;position:relative;font-family:Arial,Helvetica,sans-serif;color:#111;'
            'line-height:1.22;-webkit-print-color-adjust:exact;print-color-adjust:exact}'
            "div{overflow:hidden}</style></head><body>" + "".join(P) + "</body></html>")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    c = content()
    build_pptx(c, OUT / "SETU_poster.pptx")
    page = OUT / "SETU_poster.html"
    page.write_text(build_html(c), encoding="utf-8")
    subprocess.run([CHROME, "--headless", "--no-pdf-header-footer", f"--print-to-pdf={OUT / 'SETU_poster.pdf'}",
                    page.as_uri()], check=True, capture_output=True)
    print(*(OUT / f"SETU_poster.{x}" for x in ("pptx", "html", "pdf")), sep="\n")


if __name__ == "__main__":
    main()
