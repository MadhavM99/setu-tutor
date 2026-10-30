"""L0 letters in the database and the letter-practice pages (migration 0008, slice S1; TS-L0-*, R-INPUT, E-13)."""
import re
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from setu.content import importer, validate
from setu.content import letters as L

from .helpers import approvals
from .test_content_import import ROOT, count, fresh  # noqa: F401  (fixture)

PASS = "मेरा लंबा पासवर्ड"


def test_import_creates_draft_letters_the_script_skill_graph_and_rule_target_skills(fresh):  # noqa: F811
    tree = validate.load_tree(ROOT / "content")
    result = importer.import_tree(fresh, tree)
    assert result.letters_written == 48
    assert count(fresh, "SELECT count(*) FROM letter WHERE review_status <> 'draft'") == 0
    assert count(fresh, "SELECT count(*) FROM learner_letter") == 0
    assert count(fresh, "SELECT count(*) FROM skill WHERE band = 'L0' AND family = 'script'") == 14
    assert count(fresh, "SELECT count(*) FROM skill_prereq WHERE skill_id = 'L0.script.vowels.RCL' "
                        "AND requires_id = 'L0.script.vowels.REC'") == 1
    assert count(fresh, "SELECT count(*) FROM skill_prereq WHERE skill_id = 'L0.script.ka.REC' "
                        "AND requires_id = 'L0.script.vowels.REC'") == 1
    assert count(fresh, "SELECT count(*) FROM rule_version WHERE target_skill_id IS NULL") == 0
    assert count(fresh, "SELECT count(*) FROM rule_version rv LEFT JOIN skill s ON s.id = rv.target_skill_id "
                        "WHERE s.id IS NULL") == 0
    assert importer.import_tree(fresh, tree).letters_written == 0  # idempotent


def test_a_letter_needs_two_approvals_and_only_approved_letters_reach_learners(engine):
    lid = f"te-letter:test-{uuid.uuid4().hex[:6]}"
    with engine.begin() as c:
        c.execute(text("DELETE FROM letter WHERE telugu = 'ఙ'"))
        c.execute(text("INSERT INTO letter (id, telugu, devanagari, twin_label_hi, kind, letter_group, group_hi, "
                       "varnamala_order) VALUES (:i, 'ఙ', 'ङ', 'ङ', 'consonant', 'ka', 'क-वर्ग', 9005)"), {"i": lid})
    with pytest.raises(DBAPIError), engine.begin() as c:
        c.execute(text("UPDATE letter SET review_status = 'approved', approvals = CAST(:a AS jsonb) WHERE id = :i"),
                  {"a": approvals("s1"), "i": lid})
    with engine.begin() as c:
        c.execute(text("SET LOCAL ROLE setu_read"))
        assert c.execute(text("SELECT count(*) FROM learner_letter WHERE id = :i"), {"i": lid}).scalar_one() == 0
    with pytest.raises(DBAPIError), engine.begin() as c:
        c.execute(text("SET LOCAL ROLE setu_app"))
        c.execute(text("UPDATE letter SET note_hi = 'बदला' WHERE id = :i"), {"i": lid})
    with pytest.raises(DBAPIError), engine.begin() as c:
        c.execute(text("UPDATE letter SET twin_label_hi = 'nga' WHERE id = :i"), {"i": lid})  # no Latin
    with engine.begin() as c:
        c.execute(text("DELETE FROM letter WHERE id = :i"), {"i": lid})


@pytest.fixture
def approved_letters(engine):
    """The real letters, approved by two test speakers, in the shared test database."""
    with engine.begin() as c:
        c.execute(text("DELETE FROM letter"))
        for x in L.build_letters():
            c.execute(text("INSERT INTO letter (id, telugu, devanagari, twin_label_hi, kind, letter_group, group_hi, "
                           "varnamala_order, new_for_hindi, note_hi, review_status, approvals) VALUES (:id, :te, :dv, "
                           ":lb, :k, :g, :gh, :o, :n, :note, 'approved', CAST(:a AS jsonb))"),
                      {"id": x["id"], "te": x["telugu"], "dv": x["devanagari"], "lb": x["twin_label_hi"],
                       "k": x["kind"], "g": x["group"], "gh": x["group_hi"], "o": x["varnamala_order"],
                       "n": x["new_for_hindi"], "note": x["note_hi"], "a": approvals("s1", "s2")})
        for g in dict.fromkeys(x["group"] for x in L.build_letters()):
            for m in ("REC", "RCL"):
                c.execute(text("INSERT INTO skill (id, band, family, target, modality, direction) VALUES "
                               "(:s, 'L0', 'script', :g, :m, 'HI->TE') ON CONFLICT DO NOTHING"),
                          {"s": f"L0.script.{g}.{m}", "g": g, "m": m})
    yield
    with engine.begin() as c:
        c.execute(text("DELETE FROM letter"))


def client(engine):
    from setu.web import auth
    from setu.web.app import create_app

    c = TestClient(create_app(engine=engine), base_url="https://testserver")
    r = c.post("/api/auth/register", json={"invite_code": auth.create_invite(engine), "passphrase": PASS})
    return c, r.json()["learner_id"]


def exchange_id(html):
    return re.search(r'name="exchange_id" value="([^"]+)"', html).group(1)


def test_without_approved_letters_the_page_says_not_ready(engine):
    with engine.begin() as c:
        c.execute(text("DELETE FROM letter"))
    c, _ = client(engine)
    assert "तैयार किए जा रहे हैं" in c.get("/learn/letters").text


def test_a_learner_learns_a_letter_through_checked_answers_only(engine, approved_letters):
    c, learner = client(engine)
    page = c.get("/learn/letters").text
    assert "नया अक्षर" in page and "అ" in page
    first = exchange_id(page)
    assert exchange_id(c.get("/learn/letters").text) == first  # reloading does not re-roll the task
    c.post("/learn/letters/continue", data={"exchange_id": first})

    page = c.get("/learn/letters").text  # multiple choice: recognition, assisted
    c.post("/learn/letters/answer", data={"exchange_id": exchange_id(page), "choice": "te-letter:అ"})
    page = c.get("/learn/letters").text  # recognise on the full Devanagari keyboard: cue-free
    assert "हिंदी जुड़वाँ चुनिए" in page
    fb = c.post("/learn/letters/answer", data={"exchange_id": exchange_id(page), "key": "अ"}).text
    assert "सही" in fb
    page = c.get("/learn/letters").text  # recall on the on-screen Telugu keyboard: cue-free
    eid = exchange_id(page)
    c.post("/learn/letters/answer", data={"exchange_id": eid, "key": "అ"})
    again = c.post("/learn/letters/answer", data={"exchange_id": eid, "key": "ఆ"})  # resubmitting changes nothing
    assert "सही" in again.text

    with engine.connect() as x:
        modes = x.execute(text(
            "SELECT a.response_mode, a.cue_level, v.kind, v.outcome FROM attempt a JOIN verdict v ON v.attempt_id = a.id "
            "JOIN exchange e ON e.id = a.exchange_id JOIN session s ON s.id = e.session_id WHERE s.learner_id = :l "
            "ORDER BY a.created_at"), {"l": learner}).all()
        cards = dict(x.execute(text("SELECT modality, reps FROM learner_lexeme_card WHERE learner_id = :l AND "
                                    "card_kind = 'letter' AND card_ref = 'te-letter:అ'"), {"l": learner}).all())
        skill = x.execute(text("SELECT cuefree_successes FROM learner_skill_state WHERE learner_id = :l AND "
                               "skill_id = 'L0.script.vowels.RCL'"), {"l": learner}).scalar_one()
    assert [(m.response_mode, m.cue_level, m.kind, m.outcome) for m in modes] == [
        ("multiple_choice", 1, "recognition", "correct"), ("onscreen_keyboard", 0, "recall", "correct"),
        ("onscreen_keyboard", 0, "recall", "correct")]
    assert cards == {"REC": 2, "RCL": 1} and skill == 1


def test_a_wrong_answer_is_marked_and_later_steps_count_as_after_reveal(engine, approved_letters):
    c, learner = client(engine)
    c.post("/learn/letters/continue", data={"exchange_id": exchange_id(c.get("/learn/letters").text)})
    fb = c.post("/learn/letters/answer", data={"exchange_id": exchange_id(c.get("/learn/letters").text),
                                               "choice": "te-letter:ఆ"}).text
    assert "सही जवाब यह है" in fb
    c.post("/learn/letters/answer", data={"exchange_id": exchange_id(c.get("/learn/letters").text), "key": "अ"})
    with engine.connect() as x:
        rows = x.execute(text("SELECT a.after_reveal FROM attempt a JOIN exchange e ON e.id = a.exchange_id JOIN "
                              "session s ON s.id = e.session_id WHERE s.learner_id = :l ORDER BY a.created_at"),
                         {"l": learner}).scalars().all()
        st = x.execute(text("SELECT cuefree_successes FROM learner_skill_state WHERE learner_id = :l AND skill_id = "
                            "'L0.script.vowels.REC'"), {"l": learner}).scalar()
    assert rows == [False, True] and not st


def test_another_learners_exchange_cannot_be_answered(engine, approved_letters):
    a, _ = client(engine)
    a.post("/learn/letters/continue", data={"exchange_id": exchange_id(a.get("/learn/letters").text)})
    theirs = exchange_id(a.get("/learn/letters").text)
    b, _ = client(engine)
    r = b.post("/learn/letters/answer", data={"exchange_id": theirs, "choice": "te-letter:అ"},
               follow_redirects=False)
    assert r.status_code == 303
    with engine.connect() as x:
        assert x.execute(text("SELECT count(*) FROM attempt WHERE exchange_id = :e"), {"e": theirs}).scalar_one() == 0


def test_every_letter_page_is_hindi_only(engine, approved_letters):
    from .test_ui_pages import assert_hindi_page

    c, _ = client(engine)
    assert_hindi_page(c.get("/learn"))
    page = c.get("/learn/letters")
    assert_hindi_page(page)
    c.post("/learn/letters/continue", data={"exchange_id": exchange_id(page.text)})
    for answer in ({"choice": "te-letter:ఆ"}, {"key": "अ"}, {"key": "అ"}):
        page = c.get("/learn/letters")
        assert_hindi_page(page)
        assert_hindi_page(c.post("/learn/letters/answer", data={"exchange_id": exchange_id(page.text), **answer}))
