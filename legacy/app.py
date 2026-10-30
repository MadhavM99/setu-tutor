"""Setu web app.   Run:  streamlit run app.py

Every page is one file in web/. To add a page for a new build step, write web/<name>.py and add one line to
PAGES below. All teaching logic lives in setu/ (the same engine the terminal app and the tests use).
The side panel is only for the learner: progress of each lesson and when Raju must be taught.
Technical things (model, AI check, demo controls, learner switch) are on the Settings page."""
import streamlit as st
from setu.web import tutor, learner, style, side_panel

st.set_page_config(page_title="Setu · Telugu for Hindi speakers", page_icon="🌉", layout="centered")
style()

PAGES = [
    st.Page("web/learn.py", title="सीखो और Raju को सिखाओ", icon="🎓", default=True),
    st.Page("web/progress.py", title="Progress · Raju की कॉपी", icon="📒"),
    st.Page("web/letters.py", title="अक्षर-पुस्तक", icon="🔤"),
    st.Page("web/teacher.py", title="Teacher", icon="🧑‍🏫"),
    st.Page("web/settings.py", title="Settings", icon="⚙️"),
    # add new steps here, e.g. st.Page("web/phrases.py", title="Phrases", icon="💬"),
]
nav = st.navigation(PAGES)

with st.sidebar:
    side_panel(tutor(), learner())

nav.run()
