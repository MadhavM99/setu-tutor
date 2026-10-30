"""AI teaching aids: the model teaches each card (trick + picture), inside guards."""
import base64
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import pytest
from setu.aids import Aids, picture_object
from setu.bank import load_units
from setu.leakfilter import check_trick
from setu.llm import GeminiImages

UNITS = {u.unit_id: u for u in load_units()}
KA_UNIT = UNITS["L0-07"]
KA, KHA = KA_UNIT.lesson
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")


class Teacher:
    """A fake Gemma: writes scripted tricks and answers the picture check."""
    name = "fake-gemma"

    def __init__(self, tricks=(), looks=()):
        self.tricks, self.looks, self.prompts = list(tricks), list(looks), []

    def chat(self, system, user, **k):
        self.prompts.append(user)
        return self.tricks.pop(0)

    def see(self, image, mime, question, **k):
        return self.looks.pop(0)


class Painter:
    model = "fake-image"

    def __init__(self, n=5):
        self.calls, self.prompts = 0, []

    def draw(self, prompt):
        self.calls += 1; self.prompts.append(prompt)
        return PNG, "image/png"


# ---------- tricks ----------
@pytest.mark.parametrize("text,reason", [
    ("ఖ = क, याद रखो!", "WRONG_PAIR"),                     # wrong sound for the letter
    ("ఖ और క जुड़वाँ हैं, ख", "OTHER_TELUGU"),              # another Telugu letter sneaks in
    ("नीचे की लकीर साँस है", "MISSING"),                    # doesn't name the letter or its sound
    ("ఖ = ख, like a sword", "FORMAT"),
])
def test_trick_guard_blocks(text, reason):
    assert reason in check_trick(text, KHA).reasons


def test_good_trick_passes_and_is_kept_for_everyone(tmp_path):
    good = "ఖ के नीचे की लकीर = साँस! क में साँस डालो तो ख 💨"
    a = Aids(str(tmp_path), llm=Teacher(tricks=[good]))
    t = a.trick(KA_UNIT, KHA)
    assert t["text"] == good and t["status"] == "ai"
    assert Aids(str(tmp_path)).get(KA_UNIT, KHA)["trick"]["text"] == good      # stored: no second model call
    assert "checked, use ONLY these features" in a.llm.prompts[0] and KHA.shape in a.llm.prompts[0]


def test_bad_tricks_are_retried_with_reasons_then_given_up(tmp_path):
    a = Aids(str(tmp_path), llm=Teacher(tricks=["ఖ = क", "ఖ = क", "ఖ = क"]))
    r = a.trick(KA_UNIT, KHA)
    assert r["status"] == "failed" and len(r["rejected"]) == 3 and "WRONG_PAIR" in a.llm.prompts[1]
    assert "trick" not in a.get(KA_UNIT, KHA)                                    # nothing bad is stored


def test_another_trick_must_differ_from_the_old_one(tmp_path):
    first, second = "ఖ की पूँछ में साँस, तो ख!", "ఖ नीचे से फूँक मारता है: ख!"
    a = Aids(str(tmp_path), llm=Teacher(tricks=[first, second]))
    a.trick(KA_UNIT, KHA)
    assert a.trick(KA_UNIT, KHA, fresh=True)["text"] == second and first in a.llm.prompts[1]


# ---------- pictures ----------
def test_picture_object_comes_from_the_example_word():
    assert picture_object(KA) == "कमल"
    assert picture_object(UNITS["L0-22"].lesson[0]) == ""                       # no example word: no picture


def test_picture_is_checked_for_stray_writing_and_redrawn(tmp_path):
    p = Painter()
    a = Aids(str(tmp_path), llm=Teacher(looks=["TEXT=YES OBJECT=YES", "TEXT=NO OBJECT=YES"]), images=p)
    r = a.picture(KA_UNIT, KA)
    assert p.calls == 2 and r["check"] == "TEXT=NO OBJECT=YES" and (tmp_path / "ai" / r["file"]).read_bytes() == PNG
    assert "no text, letters" in p.prompts[0] and "कमल" in p.prompts[0]
    assert KA.telugu not in p.prompts[0]                                         # the model is never asked to draw the letter


def test_picture_with_writing_twice_is_not_shown(tmp_path):
    a = Aids(str(tmp_path), llm=Teacher(looks=["TEXT=YES OBJECT=YES"] * 2), images=Painter())
    assert a.picture(KA_UNIT, KA)["status"] == "failed" and "picture" not in a.get(KA_UNIT, KA)


def test_teacher_reject_hides_it_and_next_time_it_is_made_again(tmp_path):
    a = Aids(str(tmp_path), llm=Teacher(tricks=["ఖ में साँस: ख!", "ఖ फूँक वाला ख!"]))
    a.trick(KA_UNIT, KHA)
    k = a.key(KA_UNIT, KHA)
    a.mark(k, "trick", "rejected")
    assert "trick" not in a.get(KA_UNIT, KHA)
    assert a.trick(KA_UNIT, KHA)["text"] == "ఖ फूँक वाला ख!"


def test_without_a_model_nothing_is_made(tmp_path):
    a = Aids(str(tmp_path))
    assert a.trick(KA_UNIT, KHA) is None and a.picture(KA_UNIT, KA) is None


# ---------- the image client against a fake Google server ----------
class Fake(BaseHTTPRequestHandler):
    seen = []

    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"]))
        Fake.seen.append(self.path)
        if "old-model" in self.path:
            data = json.dumps({"error": {"message": "models/old-model is not found"}}).encode()
            self.send_response(404); self.end_headers(); self.wfile.write(data); return
        out = {"candidates": [{"content": {"parts": [{"text": "here"},
                                                     {"inlineData": {"mimeType": "image/png", "data": base64.b64encode(PNG).decode()}}]}}]}
        data = json.dumps(out).encode()
        self.send_response(200); self.end_headers(); self.wfile.write(data)

    def log_message(self, *a):
        pass


def test_image_client_tries_models_until_one_draws():
    srv = HTTPServer(("127.0.0.1", 0), Fake)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        img = GeminiImages("K", "old-model,new-model", endpoint=f"http://127.0.0.1:{srv.server_port}/v1beta/models/{{model}}:generateContent")
        data, mime = img.draw("a lotus")
        assert data == PNG and mime == "image/png" and img.model == "new-model"
        assert [a[2][:3] for a in img.attempts] == ["404", "ok"]
    finally:
        srv.shutdown()


# ---------- Gemma draws the picture itself (SVG), when no image model is available ----------
from setu.aids import clean_svg

GOOD_SVG = '<svg viewBox="0 0 256 256"><circle cx="128" cy="140" r="60" fill="#f7b2c8"/><path d="M60 200 Q128 120 196 200" fill="#6bb36b"/></svg>'


@pytest.mark.parametrize("bad", [
    '<svg viewBox="0 0 256 256"><text x="10" y="20">क</text></svg>',                  # writing: never allowed
    '<svg viewBox="0 0 256 256"><script>alert(1)</script></svg>',
    '<svg viewBox="0 0 256 256"><image href="http://x/y.png"/></svg>',
    '<svg viewBox="0 0 256 256"><rect onclick="x()" width="9" height="9"/></svg>',
    'here is a lotus!',
])
def test_svg_with_text_scripts_or_links_is_rejected(bad):
    assert clean_svg(bad) is None


def test_shapes_only_svg_is_accepted_even_inside_chatter():
    out = clean_svg("Sure! ```svg\n" + GOOD_SVG + "\n```")
    assert out and out.startswith("<svg") and "xmlns" in out


def test_without_an_image_model_gemma_draws_and_it_is_kept(tmp_path):
    class Drawer(Teacher):
        def chat(self, system, user, **k):
            self.prompts.append(user)
            return GOOD_SVG if "SVG" in system else self.tricks.pop(0)
    a = Aids(str(tmp_path), llm=Drawer(), images=None)
    r = a.picture(KA_UNIT, KA)
    assert r["file"].endswith(".svg") and "SVG" in r["model"] and (tmp_path / "ai" / r["file"]).read_text() == clean_svg(GOOD_SVG)
    assert "कमल" in a.llm.prompts[0]


def test_when_the_image_model_fails_gemma_draws_instead(tmp_path):
    class Broken:
        model, attempts = None, []
        def draw(self, prompt):
            raise RuntimeError("no free tier")
    class Drawer(Teacher):
        def chat(self, system, user, **k):
            return GOOD_SVG
    r = Aids(str(tmp_path), llm=Drawer(), images=Broken()).picture(KA_UNIT, KA)
    assert r["file"].endswith(".svg")
