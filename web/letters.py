"""The letter book: every card of the units met so far (or all units), to look back at any time."""
import streamlit as st
from setu.contracts import LEVEL_NAMES
from setu.web import tutor, learner, style, card_for

style()
t, lid = tutor(), learner()
rec = t.store.load(lid)

st.title("🔤 अक्षर-पुस्तक")
show_all = st.toggle("सारे units दिखाओ (आगे के भी)", value=False)
units = [u for u in t.units if show_all or (rec.units.get(u.unit_id) and rec.units[u.unit_id].introduced_at)]
if not units:
    st.info("अभी कोई unit नहीं खुला। 'सीखो' page से शुरू करो, या ऊपर 'सारे units' चालू करो।")
    st.stop()

level = st.radio("Level", sorted({u.level for u in units}), horizontal=True,
                 format_func=lambda l: f"{l} · {LEVEL_NAMES[l]}")
units = [u for u in units if u.level == level]
pick = st.selectbox("Unit", units, format_func=lambda u: f"{u.unit_id} · {u.title}")
if pick.tip:
    st.info(f"💡 {pick.tip}")
for line in pick.lesson:
    card_for(pick.unit_id, line.model_dump(), small=True)
st.caption(f"status: {pick.status} · {pick.source}")
