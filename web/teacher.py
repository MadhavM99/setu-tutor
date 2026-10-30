"""Teacher page.
1. Answers the checker could not judge ('unsure'). They changed nothing for the learner; if an answer is right,
   a teacher adds it to the unit's accepted list.
2. AI teaching aids (memory tricks and pictures). They are shown to learners marked "AI"; a teacher approves or
   rejects each one. A rejected one is never shown again and is made afresh next time."""
import streamlit as st
from setu.web import tutor, aids, style, card

style()
t, a = tutor(), aids()
q = t.store.read_queue()

st.title("🧑‍🏫 Teacher")
tab1, tab2 = st.tabs(["Unsure answers", "✨ AI तरकीबें और चित्र"])

with tab1:
    st.caption("Checker ने जिन जवाबों को 'unsure' कहा। इनसे learner की progress नहीं बदली।")
    if not q:
        st.success("Queue खाली है।")
    else:
        rows = []
        for e in q:
            found = t.items.get(e.get("item", ""))
            unit, item = found if found else (None, None)
            rows.append({"learner": e.get("learner"), "unit": unit.unit_id if unit else e.get("unit", "?"), "where": e.get("kind"),
                         "question": item.prompt if item else e.get("question", e.get("item")),
                         "answer given": e.get("answer", "(दीदी जवाब नहीं दे पाईं)" if e.get("kind") == "didi" else ""),
                         "we accept": ", ".join(item.accepted) if item else ""})
        st.dataframe(rows, hide_index=True, width="stretch")
        st.caption("अगर जवाब सही है: data/hi-te/<unit>.json में उस item के 'accepted' में जोड़ दो (status: teacher_verified)।")

with tab2:
    made = a.all()
    st.caption("AI ने हर card के लिए जो बनाया। Learner को ये 'AI' लिखकर दिखते हैं। "
               "✅ = पक्का, ❌ = हटाओ (अगली बार नया बनेगा)। 👍 = किसी learner को पसंद आया।")
    if not made:
        st.info("अभी कुछ नहीं बना। 'सीखो' page पर कोई card खोलो।")
    only_open = st.toggle("सिर्फ़ जो अभी approve नहीं हुए", value=True)
    for key in sorted(made):
        uid, te = key.split(":", 1)
        unit = t.by_id.get(uid)
        line = next((l for l in unit.lesson if l.telugu == te), None) if unit else None
        if line is None:
            continue
        entry = a.get(unit, line)
        open_items = [k for k in ("trick", "picture") if k in entry and entry[k].get("status") != "approved"]
        if only_open and not open_items:
            continue
        with st.container(border=True):
            st.markdown(f"**{uid} · {line.telugu} = {line.hindi}**")
            card(line.model_dump(), small=True, aid=entry)
            for kind in ("trick", "picture"):
                if kind not in entry:
                    continue
                e = entry[kind]
                info = (f"{'तरकीब' if kind == 'trick' else 'चित्र'} · status **{e.get('status')}** · {e.get('model', '')}"
                        + (f" · check: {e.get('check')}" if kind == "picture" else ""))
                c0, c1, c2 = st.columns([4, 1, 1])
                c0.caption(info)
                if c1.button("✅", key=f"ok-{kind}-{key}", help="approve"):
                    a.mark(key, kind, "approved"); st.rerun()
                if c2.button("❌", key=f"no-{kind}-{key}", help="reject"):
                    a.mark(key, kind, "rejected"); st.rerun()
