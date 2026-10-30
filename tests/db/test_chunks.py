"""L3 chunks inside scenes (migration 0011, slice S4; TS-L3-*, X-LAD-L3, X-BEG-04)."""
import json
import re

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from setu.content import importer, validate

from .helpers import approvals
from .test_aksharas import recall_letter
from .test_content_import import ROOT, count, fresh  # noqa: F401  (fixture)
from .test_letters import approved_letters, client, exchange_id  # noqa: F401  (fixture)
from .test_words import only_letters

TREE = validate.load_tree(ROOT / "content")


def test_chunks_are_drafts_in_four_scenes_and_marked_as_model_drafted():
    assert len(TREE.chunks) == 32 and len({c["scene_id"] for c in TREE.chunks}) == 4
    assert all(c["review_status"] == "draft" and "unreviewed" in c["provenance"][0]["source"] for c in TREE.chunks)
    assert [e for e in validate.validate_tree(TREE).errors if e.detail.startswith("te-chunk:")] == []


def test_import_creates_draft_chunks_and_the_l3_skills(fresh):  # noqa: F811
    result = importer.import_tree(fresh, TREE)
    assert result.chunks_written == 32
    assert count(fresh, "SELECT count(*) FROM chunk WHERE review_status <> 'draft'") == 0
    assert count(fresh, "SELECT count(*) FROM learner_chunk") == 0
    assert count(fresh, "SELECT count(*) FROM skill WHERE band = 'L3' AND family = 'chunk'") == 8
    with fresh.connect() as c:
        assert c.execute(text("SELECT letters FROM chunk WHERE telugu = 'ఎంత దూరం?'")).scalar_one() == \
            ["ఎ", "త", "ద", "ర"]


@pytest.fixture
def approved_chunks(engine, approved_letters):  # noqa: F811
    with engine.begin() as c:
        for s in TREE.scenes:
            c.execute(text("INSERT INTO scene (id, title_hi, setup_hi, review_status) VALUES (:i, :t, :s, "
                           "'approved') ON CONFLICT (id) DO UPDATE SET review_status = 'approved'"),
                      {"i": s["id"], "t": s["title_hi"], "s": s["setup_hi"]})
        c.execute(text("DELETE FROM chunk"))
        for ch in TREE.chunks:
            letters = importer.word_letters(re.sub(r"[ ?,]", "", ch["telugu"]))
            c.execute(text("INSERT INTO chunk (id, scene_id, telugu, hindi_meaning, register, letters, unit_order, "
                           "review_status, approvals) VALUES (:i, :s, :te, :hi, :r, CAST(:l AS jsonb), :o, "
                           "'approved', CAST(:a AS jsonb))"),
                      {"i": ch["id"], "s": ch["scene_id"], "te": ch["telugu"], "hi": ch["hindi_meaning"],
                       "r": ch["register"], "l": json.dumps(letters), "o": ch["order"], "a": approvals("s1", "s2")})
            for m in ("REC", "RCL"):
                c.execute(text("INSERT INTO skill (id, band, family, target, modality, direction) VALUES "
                               "(:s, 'L3', 'chunk', :g, :m, 'HI->TE') ON CONFLICT DO NOTHING"),
                          {"s": importer.chunk_skill_id(ch["scene_id"], m), "g": ch["scene_id"], "m": m})
    yield
    with engine.begin() as c:
        c.execute(text("DELETE FROM chunk"))
        c.execute(text("UPDATE scene SET review_status = 'draft'"))


def test_a_chunk_needs_two_approvals_and_an_approved_scene(engine, approved_chunks):
    with pytest.raises(DBAPIError), engine.begin() as c:
        c.execute(text("UPDATE chunk SET approvals = CAST(:a AS jsonb) WHERE id = 'te-chunk:01-01'"),
                  {"a": approvals("s1")})
    with engine.begin() as c:
        c.execute(text("UPDATE scene SET review_status = 'in_review' WHERE id = 'hi-te-scene-01'"))
        visible = set(c.execute(text("SELECT scene_id FROM learner_chunk")).scalars())
    assert "hi-te-scene-01" not in visible and "hi-te-scene-02" in visible


def test_a_learner_learns_a_chunk_in_its_scene(engine, approved_chunks):
    only_letters(engine, "ఎత")
    c, learner = client(engine)
    for ch in "ఎత":
        recall_letter(c, ch)
    page = c.get("/learn/chunks").text
    assert "ऑटो स्टैंड" in page and "हैदराबाद" in page and "ఎంత?" in page and "कितना?" in page
    c.post("/learn/chunks/continue", data={"exchange_id": exchange_id(page)})
    c.post("/learn/chunks/answer", data={"exchange_id": exchange_id(c.get("/learn/chunks").text),
                                         "choice": "te-chunk:01-01"})
    page = c.get("/learn/chunks").text
    assert "इस वाक्यांश का मतलब" in page
    c.post("/learn/chunks/answer", data={"exchange_id": exchange_id(page), "choice": "te-chunk:01-01"})
    page = c.get("/learn/chunks").text
    assert "खाली जगह" in page
    fb = c.post("/learn/chunks/answer", data={"exchange_id": exchange_id(page), "buffer": "ఎంత", "built": "1"})
    assert "सही" in fb.text  # the question mark is not required
    with engine.connect() as x:
        cards = dict(x.execute(text("SELECT modality, reps FROM learner_lexeme_card WHERE learner_id = :l AND "
                                    "card_kind = 'chunk'"), {"l": learner}).all())
    assert cards == {"REC": 2, "RCL": 1}


def test_the_space_key_builds_multi_word_chunks(engine, approved_chunks):
    only_letters(engine, "ఎతదర")
    c, _ = client(engine)
    for ch in "ఎతదర":
        recall_letter(c, ch)
    for _ in range(4):  # ఎంత? first; then ఎంత దూరం? reaches its recall step
        page = c.get("/learn/chunks").text
        eid = exchange_id(page)
        if "/continue" in page:
            c.post("/learn/chunks/continue", data={"exchange_id": eid})
        elif 'name="choice"' in page:
            c.post("/learn/chunks/answer", data={"exchange_id": eid, "choice": "te-chunk:01-01"})
        else:
            c.post("/learn/chunks/answer", data={"exchange_id": eid, "buffer": "ఎంత", "built": "1"})
    for _ in range(3):
        page = c.get("/learn/chunks").text
        eid = exchange_id(page)
        if "/continue" in page:
            c.post("/learn/chunks/continue", data={"exchange_id": eid})
        else:
            c.post("/learn/chunks/answer", data={"exchange_id": eid, "choice": "te-chunk:01-07"})
    page = c.get("/learn/chunks").text
    eid = exchange_id(page)
    built = c.post("/learn/chunks/key", data={"exchange_id": eid, "buffer": "ఎంత", "key": " "}).text
    assert 'name="buffer" value="ఎంత "' in built
    fb = c.post("/learn/chunks/answer", data={"exchange_id": eid, "buffer": "ఎంత దూరం", "built": "1"}).text
    assert "सही" in fb


def test_chunk_pages_are_hindi_only(engine, approved_chunks):
    from .test_ui_pages import assert_hindi_page

    only_letters(engine, "ఎత")
    c, _ = client(engine)
    for ch in "ఎత":
        recall_letter(c, ch)
    page = c.get("/learn/chunks")
    assert_hindi_page(page)
    c.post("/learn/chunks/continue", data={"exchange_id": exchange_id(page.text)})
    for answer in ({"choice": "te-chunk:01-01"}, {"choice": "te-chunk:01-02"}, {"buffer": "ఎంత", "built": "1"}):
        page = c.get("/learn/chunks")
        assert_hindi_page(page)
        assert_hindi_page(c.post("/learn/chunks/answer", data={"exchange_id": exchange_id(page.text), **answer}))
