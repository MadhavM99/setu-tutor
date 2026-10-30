"""Progress: the learner's memory of each unit and Raju's notebook, side by side."""
import streamlit as st
from setu.web import tutor, learner, style, STATE_HI

style()
t, lid = tutor(), learner()
rec = t.store.load(lid)
rows = t.raju_notebook(lid)

st.title("📒 Progress · Raju की कॉपी")
if not rows:
    st.info("अभी कुछ नहीं सीखा। 'सीखो' page से शुरू करो।")
    st.stop()

raju = rec.raju
c = st.columns(4)
c[0].metric("Units सीखे", f"{sum(r['ready'] for r in rows)} / {len(t.units)}")
c[1].metric("Raju जानता है", sum(v == "taught" for v in raju.values()))
c[2].metric("Raju भूल गया", sum(v == "forgotten" for v in raju.values()))
c[3].metric("कमज़ोर अक्षर", len(rec.weak))
st.caption(f"Day {rec.day_offset:g} · turns {rec.turns} · model calls {rec.model_calls} · Raju's lines: {t.writer.name}")

st.subheader("हर unit")
st.dataframe(
    [{"Unit": r["unit"], "क्या": r["title"], "आपकी याद": r["recall"], "Raju": STATE_HI[r["raju"]],
      "✓": r["right"], "✗": r["wrong"], "कमज़ोर": r["weak"]} for r in rows],
    hide_index=True, width="stretch",
    column_config={"आपकी याद": st.column_config.ProgressColumn(min_value=0.0, max_value=1.0, format="%.2f")})
st.caption("आपकी याद 0.5 से नीचे गई → Raju भी वो unit भूल जाता है, और आपको उसे फिर से सिखाना पड़ता है।")

with st.expander("Last steps (log)"):
    st.json(rec.log[-15:], expanded=False)
