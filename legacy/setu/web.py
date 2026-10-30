"""Shared pieces for the web app (Streamlit): one tutor per store folder, the learner id, styles, and the card.

The web app is only a screen. All teaching logic stays in setu.tutor, so the terminal, the web app and the
tests drive exactly the same engine. Settings come from environment variables:
    SETU_STORE     folder for progress files (default "runs")
    GEMINI_API_KEY or SETU_LLM_URL   optional model for Raju's words (see setu/llm.py)
"""
from __future__ import annotations
import base64
import html
import os
from pathlib import Path
import streamlit as st
from .aids import Aids
from .didi import Didi
from .friend import Friend, fixed_line
from .leakfilter import seen_telugu
from .llm import images_from_env
from .memory import Store
from .tutor import Tutor

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Telugu:wght@400;600&family=Noto+Sans+Devanagari:wght@400;600&display=swap');
.setu-card { border: 1px solid rgba(128,128,128,.28); border-radius: 18px; padding: 22px 26px; margin: 6px 0 14px;
             background: rgba(128,128,128,.06); }
.setu-pair { display: flex; align-items: center; gap: 28px; flex-wrap: wrap; }
.setu-te   { font-family: 'Noto Sans Telugu', sans-serif; font-size: 112px; line-height: 1.05; font-weight: 600; }
.setu-hi   { font-family: 'Noto Sans Devanagari', sans-serif; font-size: 72px; line-height: 1.1; }
.setu-eq   { font-size: 44px; opacity: .45; }
.setu-pic  { font-size: 64px; margin-left: auto; }
.setu-ex   { font-size: 22px; margin: 6px 0 12px; font-family: 'Noto Sans Telugu', 'Noto Sans Devanagari', sans-serif; }
.setu-row  { font-size: 19px; margin: 6px 0; font-family: 'Noto Sans Devanagari', sans-serif; }
.setu-row b { opacity: .7; font-weight: 600; margin-right: 6px; }
.setu-ask  { font-family: 'Noto Sans Telugu', 'Noto Sans Devanagari', sans-serif; font-size: 96px; font-weight: 600;
             text-align: center; padding: 8px 0 0; line-height: 1.15; }
.setu-sub  { text-align: center; opacity: .7; font-size: 17px; margin-bottom: 8px; }
.setu-raju { font-family: 'Noto Sans Telugu', 'Noto Sans Devanagari', sans-serif; font-size: 26px; line-height: 1.5; }
.setu-small .setu-te { font-size: 72px; } .setu-small .setu-hi { font-size: 48px; } .setu-small .setu-pic { font-size: 44px; }
.setu-art  { position: relative; display: inline-block; margin: 10px 0 6px; }
.setu-art img { width: 300px; max-width: 100%; border-radius: 16px; display: block; }
.setu-small .setu-art img { width: 200px; }
.setu-art .setu-on { position: absolute; left: 10px; top: 6px; font-family: 'Noto Sans Telugu', sans-serif;
             font-size: 64px; font-weight: 600; line-height: 1.1; color: #17203A; background: rgba(255,255,255,.88);
             border-radius: 14px; padding: 0 14px; }
.setu-small .setu-art .setu-on { font-size: 44px; }
.setu-tag  { font-size: 13px; opacity: .65; margin: 0 0 6px; }
.setu-path { display: flex; gap: 6px; flex-wrap: wrap; margin: 2px 0 14px; }
.setu-path span { padding: 4px 11px; border-radius: 999px; background: rgba(128,128,128,.12); font-size: 14px; }
.setu-path span.on { background: #3346A8; color: #fff; font-weight: 600; }
.setu-path span.done { opacity: .5; }
.setu-hi-s { font-family: 'Noto Sans Devanagari', sans-serif; font-size: 30px; line-height: 1.35; }
.setu-arrow { font-size: 15px; opacity: .6; margin: 6px 0; }
.setu-te-s { font-family: 'Noto Sans Telugu', sans-serif; font-size: 40px; font-weight: 600; line-height: 1.35; }
.setu-read { font-family: 'Noto Sans Devanagari', sans-serif; font-size: 18px; opacity: .7; margin-top: 4px; }
.setu-scene { border-left: 4px solid #F2B632; padding: 10px 16px; margin: 6px 0 12px; background: rgba(242,182,50,.10);
              border-radius: 8px; font-family: 'Noto Sans Telugu', 'Noto Sans Devanagari', sans-serif; font-size: 19px;
              line-height: 1.6; white-space: pre-line; }
.setu-ask-s { font-family: 'Noto Sans Devanagari', sans-serif; font-size: 34px; font-weight: 600; text-align: center;
              padding: 6px 0 0; line-height: 1.3; }
.setu-trick { font-size: 19px; margin: 8px 0; padding: 10px 14px; border-radius: 12px;
              background: rgba(51,70,168,.10); font-family: 'Noto Sans Telugu', 'Noto Sans Devanagari', sans-serif; }
</style>
"""

STATE_HI = {"unknown": "नहीं जानता", "learning": "सीख रहा", "taught": "जानता है", "forgotten": "भूल गया", "-": "-"}
VERDICT = {"correct": ("success", "✅"), "wrong": ("error", "❌"), "unsure": ("warning", "❓")}


@st.cache_resource
def _tutor(store_root: str) -> Tutor:
    return Tutor(Store(store_root))


def tutor() -> Tutor:
    return _tutor(os.environ.get("SETU_STORE", "runs"))


@st.cache_resource
def _aids(store_root: str) -> Aids:
    t = _tutor(store_root)
    return Aids(store_root, llm=getattr(t.writer, "llm", None), images=images_from_env())


@st.cache_resource
def _didi(store_root: str):
    t = _tutor(store_root)
    llm = getattr(t.writer, "llm", None)
    return Didi(llm, t.units) if llm is not None else None


def didi():
    """The AI teacher (None without a model)."""
    return _didi(os.environ.get("SETU_STORE", "runs"))


def learned_so_far(t: Tutor, lid: str):
    rec = t.store.load(lid)
    ids = [u for u, m in rec.units.items() if m.introduced_at is not None]
    return seen_telugu(t.units, ids), ids


@st.cache_resource
def _friend(store_root: str):
    t = _tutor(store_root)
    llm = getattr(t.writer, "llm", None)
    return Friend(llm) if llm is not None else None


PATH = [("learn", "📖 सीखो"), ("drill", "⚡ अभ्यास"), ("check", "✅ जाँच"), ("raju", "🧒 Raju की गलती ठीक करो"),
        ("why", "❓ क्यों? समझाओ"), ("review", "🔁 दोहराओ")]


def path_bar(stage: str, rules: bool) -> None:
    """The loop the learner is in, always visible (paper §5): learn -> practise -> check -> fix Raju -> explain
    why -> review. Letters have no 'why' step."""
    steps = [p for p in PATH if rules or p[0] != "why"]
    keys = [k for k, _ in steps]
    at = keys.index(stage) if stage in keys else -1
    chips = "".join(f'<span class="{"on" if i == at else "done" if i < at else ""}">{label}</span>'
                    for i, (_, label) in enumerate(steps))
    st.markdown(f'<div class="setu-path">{chips}</div>', unsafe_allow_html=True)


def sentence_card(c: dict) -> None:
    e = html.escape
    st.markdown(f'<div class="setu-card"><div class="setu-hi-s">{e(c["hindi"])}</div>'
                f'<div class="setu-arrow">↓ Telugu में</div><div class="setu-te-s">{e(c["telugu"])}</div>'
                f'<div class="setu-read">{e(c.get("note", ""))}</div></div>', unsafe_allow_html=True)


def scene_box(t: Tutor, lid: str, unit) -> None:
    """The scene and Ravi's line (native friend). Made once per lesson by the model, then kept."""
    m = t.course.of_unit.get(unit.unit_id)
    if m is None or not m.scene:
        return
    a, f = aids(), _friend(os.environ.get("SETU_STORE", "runs"))
    key = f"{unit.unit_id}:scene"
    have = a.all().get(key, {}).get("friend")
    if have is None and f is not None and not st.session_state.get(f"tried-{key}"):
        st.session_state[f"tried-{key}"] = True
        rec = t.store.load(lid)
        with st.spinner("👨 रवि आ रहा है…"):
            text, src = f.scene_line(unit, m.scene, t._seen_words(rec))
        if src == "model":
            a._put(key, "friend", {"text": text, "status": "ai", "model": getattr(f.llm, "name", "")})
            have = {"text": text}
    text = have["text"] if have else fixed_line(unit, m.scene)
    st.markdown(f'<div class="setu-scene">🎬 <b>{e_(m.title)}</b>\n{e_(text)}</div>', unsafe_allow_html=True)


def e_(x: str) -> str:
    return html.escape(x or "")


def didi_bubble(text: str) -> None:
    with st.chat_message("दीदी", avatar="👩‍🏫"):
        st.markdown(f'<div class="setu-raju" style="font-size:21px">{html.escape(text)}</div>', unsafe_allow_html=True)


def aids() -> Aids:
    """AI teaching aids (trick + picture) for lesson cards; see setu/aids.py."""
    return _aids(os.environ.get("SETU_STORE", "runs"))


def learner() -> str:
    """Kept in a plain session key (not a widget key), so it survives switching pages."""
    return (st.session_state.get("learner_id") or "me").strip() or "me"


def _when(days: float) -> str:
    if days <= 0.04:
        return "अभी"
    if days < 1:
        return f"{max(1, round(days * 24))} घंटे में"
    if days < 1.5:
        return "कल"
    return f"{round(days)} दिन में"


ICON = {"done": "✅", "now": "▶️", "open": "⬜", "locked": "🔒"}


def side_panel(t: Tutor, lid: str) -> None:
    """The course like a book: chapters -> modules -> numbered lessons, each module closed by a Raju lesson."""
    o = t.course_map(lid)
    st.markdown(f"#### 👤 {html.escape(lid)}")
    st.progress(min(1.0, o["learned"] / max(o["total"], 1)), text=f"{o['learned']} / {o['total']} lessons")
    if o["new_left_today"] == 0:
        st.caption("आज के नए lessons हो गए · कल और खुलेंगे")
    for ch in o["chapters"]:
        head = f"{ch['icon']} अध्याय {ch['no']} · {ch['title']}" + (" ✅" if ch["state"] == "done" else " 🔒" if ch["state"] == "locked" else "")
        with st.expander(head, expanded=ch["state"] == "now"):
            for m in ch["modules"]:
                if m["state"] == "locked":
                    st.markdown(f"🔒 **{html.escape(m['label'])}**")
                    continue
                tag = " ✅" if m["state"] == "done" else ""
                st.markdown(f"**{html.escape(m['label'])}**{tag}")
                lines = []
                for s_ in m["steps"]:
                    title = html.escape(s_["title"])
                    if s_["kind"] == "raju":
                        title = f"**{title}**" if s_["state"] == "now" else title
                    lines.append(f"{ICON[s_['state']]} `{s_['no']}` {title}")
                st.markdown("  \n".join(lines))
                raju = m["steps"][-1]
                if raju["state"] == "now":
                    st.progress(raju["progress"], text=raju["detail"])
                if m["review_days"] is not None:
                    st.caption("🔁 Raju भूल गया · अभी दोहराओ" if m["review_days"] == 0
                               else f"🔁 दोहराना: {_when(m['review_days'])}")
    if o["weak"]:
        st.caption(f"⚠️ {o['weak']} कमज़ोर अक्षर: Raju इन्हें पहले पूछेगा")


def style() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def card(c: dict, small: bool = False, aid: dict = None) -> None:
    """One letter/word card. `aid` = AI teaching aids for this card (setu.aids): a picture, on which the REAL
    letter is written from the font (never drawn by the model), and a memory trick. Without aids: the emoji."""
    e = html.escape
    aid = aid or {}
    rows = ""
    if c.get("shape"):
        rows += f'<div class="setu-row"><b>👀 दिखता है</b>{e(c["shape"])}</div>'
    if c.get("mnemonic"):
        rows += f'<div class="setu-row"><b>🧠 याद रखो</b>{e(c["mnemonic"])}</div>'
    trick = aid.get("trick") or {}
    if trick.get("text"):
        tag = "👩‍🏫 दीदी की तरकीब ✨" + (" · 👍" if trick.get("status") in ("liked", "approved") else "")
        rows += f'<div class="setu-trick"><b>{tag}</b><br>{e(trick["text"])}</div>'
    if c.get("note"):
        rows += f'<div class="setu-row">{e(c["note"])}</div>'
    approved = DATA / "hi-te" / c["image"] if c.get("image") else None
    pic = aid.get("picture") or {}
    art_path = approved if approved and approved.is_file() else Path(pic["path"]) if pic.get("path") else None
    art = ""
    if art_path and art_path.is_file():
        mime = {".jpg": "image/jpeg", ".svg": "image/svg+xml"}.get(art_path.suffix, "image/png")
        b64 = base64.b64encode(art_path.read_bytes()).decode()
        note = "" if art_path == approved else (
            '<div class="setu-tag">✨ AI चित्र · अक्षर असली font से लिखा है'
            + (" · ⚠️ अभी जाँचा नहीं गया" if str(pic.get("check", "")).startswith("UNCHECKED") else "") + "</div>")
        art = (f'<div class="setu-art"><img src="data:{mime};base64,{b64}" alt="{e(pic.get("object", ""))}">'
               f'<span class="setu-on">{e(c["telugu"])}</span></div>{note}')
    emoji = "" if art else e(c.get("picture", ""))
    ex = f'<div class="setu-ex">{e(c["example"])}</div>' if c.get("example") else ""
    st.markdown(
        f'<div class="setu-card{" setu-small" if small else ""}"><div class="setu-pair">'
        f'<span class="setu-te">{e(c["telugu"])}</span><span class="setu-eq">=</span>'
        f'<span class="setu-hi">{e(c["hindi"])}</span><span class="setu-pic">{emoji}</span></div>{art}{ex}{rows}</div>',
        unsafe_allow_html=True)


_STARTED: set = set()


def prepare_in_background(unit) -> None:
    """Make every card's AI picture and trick for this unit without making the learner wait."""
    import threading
    a = aids()
    if unit is None or unit.unit_id in _STARTED or (a.llm is None and a.images is None):
        return
    _STARTED.add(unit.unit_id)
    threading.Thread(target=a.prepare, args=(unit,), daemon=True).start()


def reveal(unit_id: str, telugu: str) -> None:
    """Right after a correct answer: the picture with the real letter on it, and 'letter = sound · word = meaning'.
    This is where the picture ties YOUR answer to the letter (before answering it would give the answer away)."""
    t = tutor()
    unit = t.by_id.get(unit_id)
    line = next((l for l in unit.lesson if l.telugu == telugu), None) if unit else None
    if line is None:
        return
    aid = aids().get(unit, line)
    pic = aid.get("picture") or {}
    e = html.escape
    words = f"{e(line.telugu)} = {e(line.hindi)}" + (f" · {e(line.example)}" if line.example else "")
    path = Path(pic["path"]) if pic.get("path") else None
    if path and path.is_file():
        mime = {".jpg": "image/jpeg", ".svg": "image/svg+xml"}.get(path.suffix, "image/png")
        b64 = base64.b64encode(path.read_bytes()).decode()
        art = (f'<div class="setu-art"><img src="data:{mime};base64,{b64}" style="width:180px">'
               f'<span class="setu-on" style="font-size:40px">{e(line.telugu)}</span></div>')
    else:
        art = f'<div style="font-size:72px;line-height:1">{e(line.picture or "")}</div>'
        prepare_in_background(unit)
    st.markdown(f'<div class="setu-card setu-small" style="display:flex;gap:22px;align-items:center">{art}'
                f'<div class="setu-ex" style="margin:0">{words}</div></div>', unsafe_allow_html=True)


def card_for(unit_id: str, c: dict, small: bool = False) -> None:
    """A card with whatever AI aids already exist for it (nothing new is generated)."""
    t = tutor()
    unit = t.by_id.get(unit_id)
    line = next((l for l in unit.lesson if l.telugu == c["telugu"]), None) if unit else None
    card(c, small, aids().get(unit, line) if line is not None else None)


def raju_bubble(text: str, source: str = "") -> None:
    with st.chat_message("Raju", avatar="🧒"):
        st.markdown(f'<div class="setu-raju">{html.escape(text)}</div>', unsafe_allow_html=True)
        if source == "model":
            st.caption("✨ AI ने लिखा · 5 checks pass")


def feedback(res: dict, unit_id: str = "") -> None:
    if not res or "verdict" not in res:
        if res and res.get("error"):
            st.info(res["error"])
        return
    kind, icon = VERDICT[res["verdict"]]
    getattr(st, kind)(f"{icon} {res['message']}")
    if res.get("raju_says"):                         # Raju's own reaction (written by the model when one is set)
        raju_bubble(res["raju_says"], res.get("raju_source", ""))
    if res.get("reveal"):                            # after a correct answer: the picture for that letter
        reveal(res["reveal"]["unit"], res["reveal"]["telugu"])
    if res.get("didi"):                              # the AI teacher's hint after a miss (never the answer)
        didi_bubble(res["didi"])
    if res.get("card"):
        card_for(unit_id, res["card"], small=True) if unit_id else card(res["card"], small=True)
