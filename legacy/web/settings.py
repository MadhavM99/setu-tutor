"""Settings: learner switch, the AI model and its check, and demo controls. Kept off the side panel so the
learner only sees learning there."""
import streamlit as st
from setu.llm import describe_error
from setu.web import tutor, aids, learner, style

style()
t, lid, ss = tutor(), learner(), st.session_state

st.title("⚙️ Settings")

st.subheader("Learner")
name = st.text_input("नाम", value=lid, help="हर learner की अपनी progress और अपना Raju")
if name.strip() and name.strip() != lid:
    ss["learner_id"] = name.strip()
    st.rerun()

st.subheader("सीधे यहाँ से शुरू करो")
st.caption("अक्षर पहले से आते हैं? चुने हुए module से पहले का सब 'सीखा हुआ' मान लिया जाएगा और Raju को सिखाया हुआ।")
mods = t.course.modules
pick = st.selectbox("Module", list(range(len(mods))), index=next((m.index for m in mods if m.chapter == 3), 0),
                    format_func=lambda i: f"अध्याय {mods[i].chapter} · {mods[i].chapter_title} — {mods[i].label}")
if st.button("➡️ यहाँ से शुरू करो"):
    t.jump_to(lid, pick)
    for k in [k for k in ss.keys() if k not in ("learner_id",)]:
        del ss[k]
    st.success(f"अब {mods[pick].label} से। 'सीखो' page खोलो।")

st.subheader("AI")
llm, a = getattr(t.writer, "llm", None), aids()
st.caption(f"Raju और तरकीबें: **{t.writer.name}** · चित्र: **{(a.images.model or 'auto') if a.images else 'बंद'}**")
if llm is None:
    st.info("AI बंद है: terminal में `export GEMINI_API_KEY=...` करके app फिर से चलाओ।")
else:
    rec = t.store.load(lid)
    last = next((e for e in reversed(rec.log) if e.get("step") in ("raju", "reaction")), None)
    errs = [r[0] for r in (last or {}).get("rejected", []) if r and r[0].startswith("MODEL_ERROR")]
    if last and last.get("source") == "template" and errs:
        st.warning("पिछली बार AI नहीं चला, fixed line दिखी: " + errs[-1].replace("MODEL_ERROR: ", ""))
    if st.button("🔌 AI जाँचो"):
        try:
            if hasattr(llm, "attempts"):
                llm.auth = None
            reply = llm.chat("Reply in Hindi, one short line.", "नमस्ते बोलो।", max_tokens=30)
            how = f" ({' + '.join(llm.auth)})" if getattr(llm, "auth", None) else ""
            st.success(f"AI चल रहा है{how}: {reply}")
        except Exception as e:
            st.error(describe_error(e))
        for mode, variant, result in getattr(llm, "attempts", []):
            st.caption(f"{'✅' if result == 'ok' else '❌'} {mode} · {variant} → {result}")

st.subheader("🖼️ चित्र")
a = aids()
st.caption("हर अक्षर के लिए एक चित्र: पहले Google का image model, वो न चले तो आपका Gemma खुद SVG में बनाता है। "
           "अक्षर हमेशा असली font से ऊपर लिखा जाता है।")
c1, c2 = st.columns(2)
if c1.button("🖼️ चित्र जाँचो (क → कमल)"):
    sample_u = t.by_id["L0-07"]
    with st.spinner("चित्र बन रहा है… (30–60 सेकंड तक)"):
        r = a.picture(sample_u, sample_u.lesson[0], fresh=True)
    if r and r.get("path"):
        st.success(f"चित्र बना: {r.get('model')} · {r.get('check')}")
        st.image(r["path"], width=220)
    else:
        st.error("चित्र नहीं बना।")
        for x in (r or {}).get("tries", []):
            st.caption("• " + str(x))
    for m, mode, res in getattr(a.images, "attempts", []) if a.images else []:
        st.caption(f"{'✅' if res == 'ok' else '❌'} {m} · {mode} → {res}")
if c2.button("🎨 अगले module के सारे चित्र अभी बनाओ"):
    rec = t.store.load(lid)
    cur = t._current_module(rec)
    lines = [(t.by_id[u], l) for u in (cur.units if cur else []) for l in t.by_id[u].lesson]
    bar = st.progress(0.0, text="शुरू…")
    for k, (u, l) in enumerate(lines, 1):
        bar.progress(k / max(len(lines), 1), text=f"{l.telugu} = {l.hindi}")
        try:
            if a.llm is not None:
                a.trick(u, l)
            a.picture(u, l)
        except Exception as e:
            st.caption(f"{l.telugu}: {describe_error(e)}")
    st.success("हो गया। अब lesson खोलो।")

st.subheader("Demo")
c1, c2 = st.columns([1, 2])
days = c1.number_input("दिन", min_value=1, max_value=60, value=3, step=1)
if c2.button("⏩ समय आगे करो", help="देखो Raju कैसे भूलता है और फिर से पूछता है"):
    t.skip_days(lid, days)
    ss.pop("done", None)
    st.success(f"{days} दिन आगे। side panel में देखो Raju को कब सिखाना है।")
if st.checkbox("Reset this learner"):
    if st.button("🗑️ सब progress मिटाओ"):
        t.store.reset(lid)
        for k in list(ss.keys()):
            if k != "learner_id":
                del ss[k]
        st.rerun()
