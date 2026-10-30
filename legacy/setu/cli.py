"""Terminal app: learn letters and words, and teach Raju. Progress is saved in runs/<learner>.json.

    python -m setu.cli                    learner "me"
    python -m setu.cli --learner priya    another learner (own progress, own Raju)
    python -m setu.cli --list             list all units

Type your answer and press Enter.
  /ok        Raju's line is correct (no mistake)
  /skip N    jump N days ahead (watch Raju forget)
  /status    your memory and Raju's notebook
  /q         quit (progress is saved)
Raju's words come from a model if GEMINI_API_KEY (Gemma 4 on Google AI Studio) or SETU_LLM_URL (your own
server) is set, otherwise from fixed sentences. If the model is slow or down, fixed sentences are used.
"""
from __future__ import annotations
import argparse
from .bank import load_units
from .checker import NO_ERROR
from .contracts import LEVEL_NAMES
from .memory import Store
from .tutor import Tutor

MARK = {"correct": "✅", "wrong": "❌", "unsure": "❓"}
STATE = {"unknown": "नहीं जानता", "learning": "सीख रहा", "taught": "जानता है", "forgotten": "भूल गया", "-": "-"}


def card(c: dict) -> None:
    """One letter card. Images can't show in a terminal: the emoji stands in (the web app shows the image)."""
    print(f"\n        {c['telugu']}    =    {c['hindi']}\n")
    if c.get("example"):
        print(f"   {c.get('picture', '')}  {c['example']}")
    if c.get("image"):
        print(f"   🖼️  picture: data/hi-te/{c['image']}")
    if c.get("shape"):
        print(f"   👀 दिखता है: {c['shape']}")
    if c.get("mnemonic"):
        print(f"   🧠 याद रखो: {c['mnemonic']}")
    if c.get("note"):
        print(f"   {c['note']}")


def cards(r: dict) -> None:
    """Lesson: the unit's pattern, then one card per letter (press Enter)."""
    st = r.get("step") or {}
    where = f"{st['chapter']} · {st['module']}\n{st['no']}  " if st else f"NEW · {r['unit']} · {LEVEL_NAMES[r['level']]} · "
    print("\n" + "=" * 62 + f"\n{where}{r['title']}")
    if r.get("tip"):
        print(f"💡 {r['tip']}")
    n = len(r["lesson"])
    for k, c in enumerate(r["lesson"], 1):
        print("\n" + "-" * 22 + f" कार्ड {k}/{n} " + "-" * 22)
        card(c)
        _pause()
    if r.get("drill"):
        print("\n⚡ अब हर अक्षर याद करो (गिनती नहीं होगी — गलत हुआ तो कार्ड फिर दिखेगा):")


def drill_prompt(d: dict) -> None:
    print(f"\n   {d['prompt']} = ?   ({d['how']} · बाकी {d['left']})")


def check_prompt(c: dict) -> None:
    print("\n" + "-" * 62 + f"\nCHECK (गिनती होगी): {c['question']}   ({c['how']})")


def _pause() -> None:
    try:
        input("   (Enter ↵)")
    except (EOFError, KeyboardInterrupt):
        pass


def show(t: Tutor, r: dict) -> None:
    k = r["kind"]
    if k == "lesson":
        cards(r)
        if r.get("drill"):
            drill_prompt(r["drill"])
        elif r.get("check"):
            check_prompt(r["check"])
    elif k in ("raju", "followup"):
        st = r.get("step") or {}
        if k == "raju" and st:
            print("\n" + "=" * 62 + f"\n{st['no']}  {st['title']}   ({st['module']})")
        tag = f"RAJU ({r['number']}/{r['of']})" if k == "followup" else "RAJU"
        extra = "   [model]" if r.get("source") == "model" else ""
        print(f"\n{tag}: {r['raju']}{extra}\n      ({r['how']})")
    elif k in ("done", "waiting"):
        print("\n" + r["message"])


def main() -> None:
    ap = argparse.ArgumentParser(description="Setu Tutor")
    ap.add_argument("--learner", default="me"); ap.add_argument("--store", default="runs")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    if a.list:
        for u in load_units():
            print(f"{u.unit_id}  level {u.level} ({LEVEL_NAMES[u.level]:<7})  {u.title}")
        return
    t = Tutor(Store(a.store))
    print(f"Setu Tutor · learner: {a.learner} · Raju's lines: {t.writer.name}\n"
          "Commands: /ok = no mistake · /skip N = jump days · /status · /q = quit")
    pending = t.store.load(a.learner).pending
    if not pending:
        show(t, t.next(a.learner))
    elif pending["kind"] == "drill":
        print("\n(drill चल रहा है)")
        drill_prompt(t._drill_prompt(pending["queue"][0], len(pending["queue"])))
    else:
        print("\n(पिछला सवाल अभी खुला है — जवाब लिखो)")
    while True:
        try:
            cmd = input("  > ").strip()
        except (EOFError, KeyboardInterrupt):
            print(); break
        if cmd in ("/q", "q"):
            break
        if cmd.startswith("/skip"):
            n = float(cmd.split()[1]) if len(cmd.split()) > 1 else 3
            t.skip_days(a.learner, n); print(f"  … {n:g} दिन बाद"); show(t, t.next(a.learner)); continue
        if cmd == "/status":
            s = t.status(a.learner)
            print(f"  day {s['day']} · turns {s['turns']} · model calls {s['model_calls']}")
            for uid, m in s["units"].items():
                print(f"  {uid}: आपकी याद {m['recall']:.2f} · Raju: {STATE[m['raju']]:<9} · ✓{m['right']} ✗{m['wrong']}")
            if s["weak"]:
                print("  कमज़ोर अक्षर (Raju पहले यही पूछेगा): " + " ".join(t.items[i][1].prompt for i in s["weak"]))
            continue
        if not cmd:
            continue
        res = t.answer(a.learner, NO_ERROR if cmd == "/ok" else cmd)
        if "error" in res:
            print("  " + res["error"]); continue
        print(f"  {MARK[res['verdict']]} {res['message']}")
        if res.get("raju_says"):
            print(f"  RAJU: {res['raju_says']}" + ("   [AI]" if res.get("raju_source") == "model" else ""))
        if res.get("card"):                      # drill miss: the same card again
            card(res["card"])
        if res.get("module_done"):
            md = res["module_done"]
            print(f"\n  🎉 {md['module']} पूरा!" + (f"  अब: {md['next']}" if md.get("next") else ""))
        if res.get("next"):                      # drill: next letter (or the same one again)
            drill_prompt(res["next"]); continue
        if res.get("check"):                     # drill finished: the scored check
            check_prompt(res["check"]); continue
        if res.get("followup"):
            show(t, res["followup"]); continue
        if t.store.load(a.learner).pending:      # same question still open (first miss)
            continue
        show(t, t.next(a.learner))
    print("Progress saved. फिर मिलेंगे!")


if __name__ == "__main__":
    main()
