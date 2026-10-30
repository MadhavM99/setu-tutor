"""Rendered pages are Hindi-only, calm and self-contained (M-54 = 0 Latin in visible text; TS-L10N, TS-UI-CALM,
E-15). Pages are crawled through the app against real Postgres."""
import re
import unicodedata
import uuid
from html.parser import HTMLParser

import pytest
from fastapi.testclient import TestClient

PASS = "मेरा लंबा पासवर्ड"


class Visible(HTMLParser):
    VISIBLE_ATTRS = frozenset({"alt", "title", "placeholder", "aria-label", "aria-description"})

    def __init__(self):
        super().__init__()
        self.text, self.attrs, self.html_lang, self.external, self._skip = [], [], None, [], 0
        self.telugu_spans_ok = True
        self._stack = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "html":
            self.html_lang = a.get("lang")
        if tag in ("script", "style"):
            self._skip += 1
        for k, v in a.items():
            if k in self.VISIBLE_ATTRS and v:
                self.attrs.append(v)
            if k in ("src", "href", "action") and v and re.match(r"^(https?:)?//", v):
                self.external.append(v)
        if tag == "input" and a.get("type") in ("submit", "button") and a.get("value"):
            self.attrs.append(a["value"])
        self._stack.append(a.get("lang"))

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip -= 1
        if self._stack:
            self._stack.pop()

    def handle_data(self, data):
        if self._skip or not data.strip():
            return
        self.text.append(data)
        if re.search(r"[ఀ-౿]", data) and "te" not in self._stack:
            self.telugu_spans_ok = False


def crawl(response):
    v = Visible()
    v.feed(response.text)
    return v


def assert_hindi_page(response, status=200):
    assert response.status_code == status, response.text
    assert response.headers["content-type"].startswith("text/html")
    v = crawl(response)
    visible = " ".join(v.text + v.attrs)
    assert v.html_lang == "hi"
    assert not re.search(r"[A-Za-z]", visible), re.findall(r"[A-Za-z]+", visible)
    assert not any(unicodedata.category(ch) == "So" for ch in visible), "emoji or symbols in a learner page"
    assert v.external == []
    assert v.telugu_spans_ok, "Telugu text must sit inside an element with lang=te"
    return v


@pytest.fixture
def app(engine):
    from setu.web.app import create_app

    return create_app(engine=engine, cookie_secure=True)


def client(app):
    return TestClient(app, base_url="https://testserver", follow_redirects=False)


def signed_in(app, engine, role="learner"):
    from setu.web import auth

    c = client(app)
    r = c.post("/api/auth/register", json={"invite_code": auth.create_invite(engine, role=role), "passphrase": PASS})
    assert r.status_code == 201
    return c, r.json()["handle"]


def test_signed_out_pages_are_hindi(app):
    c = client(app)
    root = c.get("/")
    assert root.status_code == 303 and root.headers["location"] == "/login"
    assert_hindi_page(c.get("/login"))
    assert_hindi_page(c.get("/register"))


def test_signing_in_through_the_form(app, engine):
    _, handle = signed_in(app, engine)
    c = client(app)
    bad = c.post("/login", data={"handle": handle, "passphrase": "गलत पासवर्ड है यह"})
    v = assert_hindi_page(bad, status=401)
    assert any("सही नहीं" in t for t in v.text)
    good = c.post("/login", data={"handle": handle, "passphrase": PASS})
    assert good.status_code == 303 and good.headers["location"] == "/"
    home = assert_hindi_page(c.get("/"))
    assert any(handle in t for t in home.text)


def test_registering_through_the_form_shows_the_handle_once(app, engine):
    from setu.web import auth

    c = client(app)
    r = c.post("/register", data={"invite_code": auth.create_invite(engine), "passphrase": PASS})
    v = assert_hindi_page(r)
    assert any(re.search(r"\d{4}-\d{4}", t) for t in v.text)
    bad = client(app).post("/register", data={"invite_code": "0000-0000-0000", "passphrase": PASS})
    assert any("आमंत्रण" in t for t in assert_hindi_page(bad, status=400).text)


def test_there_is_no_consent_page_and_no_consent_link(app, engine):
    c, _ = signed_in(app, engine)
    assert c.get("/consent", headers={"accept": "text/html"}).status_code == 404
    assert 'href="/consent"' not in c.get("/").text

def test_teacher_page_is_hindi_and_needs_a_teacher(app, engine):
    learner, _ = signed_in(app, engine)
    assert learner.get("/teacher").status_code == 403
    teacher, _ = signed_in(app, engine, role="teacher")
    assert_hindi_page(teacher.get("/teacher"))


def test_fonts_are_served_by_the_app(app):
    c = client(app)
    css = c.get("/static/css/setu.css")
    assert css.status_code == 200 and "@font-face" in css.text
    for font in re.findall(r"url\(([^)]+\.woff2)\)", css.text):
        r = c.get(font.strip("'\""))
        assert r.status_code == 200 and r.content[:4] == b"wOF2", font


def test_unknown_page_is_a_hindi_404(app):
    r = client(app).get(f"/no-such-page-{uuid.uuid4().hex[:6]}", headers={"accept": "text/html"})
    assert r.status_code == 404
    v = crawl(r)
    assert v.html_lang == "hi" and not re.search(r"[A-Za-z]", " ".join(v.text))
