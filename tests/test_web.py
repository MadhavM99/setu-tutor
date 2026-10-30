"""The web app drives the same engine: start -> cards -> drill -> check -> Raju, without a browser."""
from pathlib import Path
import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest
from setu.memory import Store
from setu.tutor import Tutor

ROOT = Path(__file__).resolve().parent.parent


def press(at, label):
    b = next(b for b in at.button if b.label == label)
    b.click().run()


def type_answer(at, text):
    next(ti for ti in at.text_input if ti.label != "Learner").input(text)
    press(at, "जवाब दो")


def test_web_app_lesson_drill_check_then_raju(tmp_path, monkeypatch):
    monkeypatch.setenv("SETU_STORE", str(tmp_path))
    monkeypatch.delenv("SETU_LLM_URL", raising=False)
    t = Tutor(Store(str(tmp_path)))                       # read-only view of the same files, for the answers
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    assert not at.exception
    press(at, "शुरू करो ▶")
    n = len(t.screen("me")["lesson"])
    for _ in range(n - 1):
        press(at, "आगे →")
    press(at, "अभ्यास शुरू करो ⚡")
    type_answer(at, "ॐ")                                   # a miss: same card again
    assert any("कार्ड फिर से देखो" in e.value for e in at.error)
    while t.screen("me")["kind"] == "drill":
        s = t.screen("me")
        type_answer(at, t.items[s["item"]][1].accepted[0])
    assert t.screen("me")["kind"] == "check"
    unit = t.by_id[t.screen("me")["unit"]]
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()   # a fresh page redraws the open check
    type_answer(at, unit.check.accepted[0])
    nxt = t.screen("me")
    assert nxt["kind"] == "drill" and nxt["step"]["no"] == "1.2"    # next lesson of the module, Raju comes at 1.4
    assert not at.exception


def test_other_pages_render(tmp_path, monkeypatch):
    monkeypatch.setenv("SETU_STORE", str(tmp_path))
    for page in ("web/progress.py", "web/letters.py", "web/teacher.py", "web/settings.py"):
        at = AppTest.from_file(str(ROOT / page), default_timeout=30).run()
        assert not at.exception, page


def test_side_panel_is_a_numbered_course_without_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("SETU_STORE", str(tmp_path))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False); monkeypatch.delenv("SETU_LLM_URL", raising=False)
    t = Tutor(Store(str(tmp_path)), drill=False)
    t.next("me"); t.answer("me", t.by_id["L0-01"].check.accepted[0])          # 1.1 learned
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    side = " ".join(m.value for m in at.sidebar.markdown) + " ".join(e.label for e in at.sidebar.expander)
    assert "अध्याय 1 · अक्षर" in side and "Module 1 · स्वर (1)" in side
    assert "✅ `1.1`" in side and "`1.4` 🧒 Raju को आपकी मदद चाहिए" in side and "🔒 **Module 2" in side
    assert not any(b.label == "🔌 AI जाँचो" for b in at.sidebar.button)    # technical things are on Settings
