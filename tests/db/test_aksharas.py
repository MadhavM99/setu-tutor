"""L1 aksharas in the database and their practice pages (migration 0009, slice S2; TS-L1-*, R-INPUT, X-PERS-04)."""
import json
import re

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from setu.content import aksharas as A
from setu.content import importer, validate

from .helpers import approvals
from .test_content_import import ROOT, count, fresh  # noqa: F401  (fixture)
from .test_letters import approved_letters, client, exchange_id  # noqa: F401  (fixture)


def test_import_creates_draft_aksharas_and_the_l1_skill_graph(fresh):  # noqa: F811
    result = importer.import_tree(fresh, validate.load_tree(ROOT / "content"))
    assert result.aksharas_written == 489
    assert count(fresh, "SELECT count(*) FROM akshara WHERE review_status <> 'draft'") == 0
    assert count(fresh, "SELECT count(*) FROM learner_akshara") == 0
    assert count(fresh, "SELECT count(*) FROM skill WHERE band = 'L1' AND family = 'akshara'") == 8
    assert count(fresh, "SELECT count(*) FROM skill_prereq WHERE skill_id = 'L1.akshara.vowel_signs.REC' "
                        "AND requires_id LIKE 'L0.script.%.REC'") == 7
    assert count(fresh, "SELECT count(*) FROM skill_prereq WHERE skill_id = 'L1.akshara.conjuncts.REC' "
                        "AND requires_id = 'L1.akshara.doubles.REC'") == 1


def insert_aksharas(c, units, status="approved"):
    for x in units:
        c.execute(text("INSERT INTO akshara (id, telugu, devanagari, twin_label_hi, kind, family, akshara_group, "
                       "group_hi, letters, unit_order, note_hi, review_status, approvals) VALUES (:id, :te, :dv, :lb, "
                       ":k, :f, :g, :gh, CAST(:l AS jsonb), :o, :n, :st, CAST(:a AS jsonb))"),
                  {"id": x["id"], "te": x["telugu"], "dv": x["devanagari"], "lb": x["twin_label_hi"], "k": x["kind"],
                   "f": x["family"], "g": x["group"], "gh": x["group_hi"], "l": json.dumps(x["letters"]),
                   "o": x["order"], "n": x["note_hi"], "st": status,
                   "a": approvals("s1", "s2") if status == "approved" else "[]"})


@pytest.fixture
def approved_aksharas(engine, approved_letters):  # noqa: F811
    with engine.begin() as c:
        c.execute(text("DELETE FROM akshara"))
        insert_aksharas(c, A.build_aksharas())
        for fam in importer.L1_FAMILIES:
            for m in ("REC", "RCL"):
                c.execute(text("INSERT INTO skill (id, band, family, target, modality, direction) VALUES "
                               "(:s, 'L1', 'akshara', :f, :m, 'HI->TE') ON CONFLICT DO NOTHING"),
                          {"s": importer.akshara_skill_id(fam, m), "f": fam, "m": m})
    yield
    with engine.begin() as c:
        c.execute(text("DELETE FROM akshara"))


def test_an_akshara_needs_two_approvals_and_approved_letters(engine, approved_letters):  # noqa: F811
    unit = A.build_aksharas()[0]
    with pytest.raises(DBAPIError), engine.begin() as c:
        c.execute(text("DELETE FROM akshara"))
        insert_aksharas(c, [unit])
        c.execute(text("UPDATE akshara SET approvals = CAST(:a AS jsonb) WHERE id = :i"),
                  {"a": approvals("s1"), "i": unit["id"]})
    with engine.begin() as c:
        c.execute(text("DELETE FROM akshara"))
        insert_aksharas(c, [unit])
        assert c.execute(text("SELECT count(*) FROM learner_akshara")).scalar_one() == 1
        c.execute(text("UPDATE letter SET review_status = 'in_review' WHERE telugu = :ch"), {"ch": unit["letters"][0]})
        assert c.execute(text("SELECT count(*) FROM learner_akshara")).scalar_one() == 0  # its letter is unapproved
        c.execute(text("DELETE FROM akshara"))
    with pytest.raises(DBAPIError), engine.begin() as c:
        c.execute(text("SET LOCAL ROLE setu_app"))
        c.execute(text("INSERT INTO akshara (id, telugu, devanagari, twin_label_hi, kind, family, akshara_group, "
                       "group_hi, letters, unit_order) VALUES ('x', 'కా', 'का', 'का', 'sign', 'vowel_signs', 'g', "
                       "'ग', '[]', 1)"))


def recall_letter(c, ch):
    """Learn the letter `ch` through the pages until its cue-free recall is done."""
    for _ in range(12):
        page = c.get("/learn/letters").text
        eid = exchange_id(page)
        if 'action="/learn/letters/continue"' in page:
            c.post("/learn/letters/continue", data={"exchange_id": eid})
        elif 'name="choice"' in page:
            c.post("/learn/letters/answer", data={"exchange_id": eid, "choice": f"te-letter:{ch}"})
        elif "हिंदी जुड़वाँ चुनिए" in page:
            from setu.domain.normalise import TELU_TO_DEVA
            c.post("/learn/letters/answer", data={"exchange_id": eid, "key": TELU_TO_DEVA[ch]})
        else:
            c.post("/learn/letters/answer", data={"exchange_id": eid, "key": ch})
            return
    raise AssertionError("letter chain did not finish")


def test_aksharas_wait_until_their_letters_are_recalled_cue_free(engine, approved_aksharas):
    c, _ = client(engine)
    assert "पहले अक्षर सीखिए" in c.get("/learn/aksharas").text


def test_a_learner_builds_an_akshara_on_the_compose_keyboard(engine, approved_aksharas):
    with engine.begin() as x:
        x.execute(text("UPDATE letter SET review_status = 'in_review', approvals = '[]' WHERE telugu <> 'క'"))
    c, learner = client(engine)
    recall_letter(c, "క")
    page = c.get("/learn/aksharas").text
    assert "आ की मात्रा" in page and "కా" in page  # the sign's intro card
    c.post("/learn/aksharas/continue", data={"exchange_id": exchange_id(page)})
    page = c.get("/learn/aksharas").text
    c.post("/learn/aksharas/answer", data={"exchange_id": exchange_id(page), "choice": "te-akshara:కా"})

    page = c.get("/learn/aksharas").text  # recognise: build का from consonant and sign keys
    eid = exchange_id(page)
    built = c.post("/learn/aksharas/key", data={"exchange_id": eid, "buffer": "", "key": "क"}).text
    built = c.post("/learn/aksharas/key", data={"exchange_id": eid, "buffer": "क", "key": "ि"}).text
    built = c.post("/learn/aksharas/key", data={"exchange_id": eid, "buffer": "कि", "erase": "1"}).text
    assert re.search(r'name="buffer" value="क"', built)
    nonsense = c.post("/learn/aksharas/key", data={"exchange_id": eid, "buffer": "क", "key": "x"}).text
    assert re.search(r'name="buffer" value="क"', nonsense)  # only real keys are accepted
    c.post("/learn/aksharas/key", data={"exchange_id": eid, "buffer": "क", "key": "ा"})
    fb = c.post("/learn/aksharas/answer", data={"exchange_id": eid, "buffer": "का", "built": "1"}).text
    assert "सही" in fb

    page = c.get("/learn/aksharas").text  # recall: build కా on Telugu keys
    fb = c.post("/learn/aksharas/answer", data={"exchange_id": exchange_id(page), "buffer": "కా", "built": "1"}).text
    assert "सही" in fb
    with engine.connect() as x:
        modes = x.execute(text(
            "SELECT a.response_mode, a.cue_level, v.outcome FROM attempt a JOIN verdict v ON v.attempt_id = a.id "
            "JOIN exchange e ON e.id = a.exchange_id WHERE e.task->>'activity' = 'aksharas' AND e.session_id IN "
            "(SELECT id FROM session WHERE learner_id = :l) ORDER BY a.created_at"), {"l": learner}).all()
        cards = dict(x.execute(text("SELECT modality, reps FROM learner_lexeme_card WHERE learner_id = :l AND "
                                    "card_kind = 'akshara' AND card_ref = 'te-akshara:కా'"), {"l": learner}).all())
        skill = x.execute(text("SELECT cuefree_successes FROM learner_skill_state WHERE learner_id = :l AND "
                               "skill_id = 'L1.akshara.vowel_signs.RCL'"), {"l": learner}).scalar_one()
    assert [tuple(m) for m in modes] == [("multiple_choice", 1, "correct"), ("onscreen_keyboard", 0, "correct"),
                                         ("onscreen_keyboard", 0, "correct")]
    assert cards == {"REC": 2, "RCL": 1} and skill == 1


def test_a_second_akshara_with_the_same_sign_skips_the_intro(engine, approved_aksharas):
    with engine.begin() as x:
        x.execute(text("UPDATE letter SET review_status = 'in_review', approvals = '[]' WHERE telugu NOT IN "
                       "('క', 'ఖ')"))
    c, _ = client(engine)
    recall_letter(c, "క")
    recall_letter(c, "ఖ")
    page = c.get("/learn/aksharas").text
    c.post("/learn/aksharas/continue", data={"exchange_id": exchange_id(page)})
    for answer in ({"choice": "te-akshara:కా"}, {"buffer": "का", "built": "1"}, {"buffer": "కా", "built": "1"}):
        c.post("/learn/aksharas/answer", data={"exchange_id": exchange_id(c.get("/learn/aksharas").text), **answer})
    page = c.get("/learn/aksharas").text
    assert 'name="choice"' in page and "te-akshara:ఖా" in page


def test_akshara_pages_are_hindi_only(engine, approved_aksharas):
    from .test_ui_pages import assert_hindi_page

    with engine.begin() as x:
        x.execute(text("UPDATE letter SET review_status = 'in_review', approvals = '[]' WHERE telugu <> 'క'"))
    c, _ = client(engine)
    assert_hindi_page(c.get("/learn/aksharas"))
    recall_letter(c, "క")
    page = c.get("/learn/aksharas")
    assert_hindi_page(page)
    c.post("/learn/aksharas/continue", data={"exchange_id": exchange_id(page.text)})
    for answer in ({"choice": "te-akshara:కా"}, {"buffer": "क", "built": "1"}):
        page = c.get("/learn/aksharas")
        assert_hindi_page(page)
        assert_hindi_page(c.post("/learn/aksharas/answer", data={"exchange_id": exchange_id(page.text), **answer}))
    page = c.get("/learn/aksharas")
    assert_hindi_page(page)
    assert_hindi_page(c.post("/learn/aksharas/key", data={"exchange_id": exchange_id(page.text), "buffer": "",
                                                          "key": "క"}))
