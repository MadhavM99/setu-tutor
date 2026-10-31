"""Teacher console I: the unsure queue (slice 4.1; F3, P-ARCH-10, X-TCH-04, TS-TQ-*)."""
import re

import pytest

from .test_correction import WRONG, advance_to, answer, client, one, rule_bank  # noqa: F401  (fixture)
from .test_teacher_review import teacher

KEY = "test-resolution-key-0123456789abcdef-long"


@pytest.fixture
def resolution_key(monkeypatch):
    monkeypatch.setenv("SETU_RESOLUTION_KEY", KEY)


def unsure_fix(engine):
    c, learner = client(engine)
    page = advance_to(c, "planted")
    wrong = next(w for w in WRONG if w in page)
    answer(c, page, typed="మీరు ఎక్కడ ఉన్నారు")
    q = one(engine, "SELECT q.id FROM teacher_queue_item q JOIN verdict v ON v.id = q.verdict_id JOIN attempt a ON "
                    "a.id = v.attempt_id JOIN exchange e ON e.id = a.exchange_id JOIN session s ON s.id = e.session_id "
                    "WHERE s.learner_id = :l AND q.status = 'open'", l=learner)
    return learner, q.id, wrong


def test_learners_cannot_see_the_queue(engine, rule_bank, resolution_key):  # noqa: F811
    c, _ = client(engine)
    assert c.get("/teacher/queue").status_code == 403


def test_a_teacher_settles_an_unsure_fix_once_and_the_learner_gets_credit(engine, rule_bank,  # noqa: F811
                                                                           resolution_key):
    learner, qid, wrong = unsure_fix(engine)
    t, t_id = teacher(engine)
    page = t.get("/teacher/queue").text
    assert "మీరు ఎక్కడ ఉన్నారు" in page and wrong in page and WRONG[wrong] in page
    assert "जाँचने वाला तय नहीं कर पाया" in page  # the reason code, in Hindi
    assert not re.search(r"unknown_form", page)
    before = one(engine, "SELECT count(*) AS n FROM skill_evidence WHERE learner_id = :l", l=learner).n
    done = t.post("/teacher/queue/settle", data={"queue_item_id": str(qid), "outcome": "correct"}).text
    assert "निपटा दिया गया" in done
    assert one(engine, "SELECT status FROM teacher_queue_item WHERE id = :q", q=qid).status == "resolved"
    ev = one(engine, "SELECT count(*) AS n FROM event_ledger WHERE event_type = 'teacher_resolution' AND actor = :a",
             a=f"teacher:{t_id}")
    assert ev.n == 1
    assert one(engine, "SELECT count(*) AS n FROM skill_evidence WHERE learner_id = :l", l=learner).n == before + 1
    assert one(engine, "SELECT state FROM classmate_rule_state WHERE learner_id = :l", l=learner).state == "taught"

    again = t.post("/teacher/queue/settle", data={"queue_item_id": str(qid), "outcome": "wrong"}).text
    assert "पहले ही निपटाया गया" in again
    assert one(engine, "SELECT count(*) AS n FROM teacher_resolution WHERE queue_item_id = :q", q=qid).n == 1


def test_a_wrong_settlement_counts_as_an_error_and_teaches_nothing(engine, rule_bank, resolution_key):  # noqa: F811
    learner, qid, _ = unsure_fix(engine)
    t, _ = teacher(engine)
    t.post("/teacher/queue/settle", data={"queue_item_id": str(qid), "outcome": "wrong"})
    ev = one(engine, "SELECT e.outcome FROM skill_evidence e JOIN teacher_queue_item q ON q.verdict_id = e.verdict_id "
                     "WHERE q.id = :q", q=qid)
    assert ev.outcome == "wrong"
    assert one(engine, "SELECT count(*) AS n FROM classmate_rule_state WHERE learner_id = :l", l=learner).n == 0


def test_without_a_resolution_key_nothing_is_settled(engine, rule_bank, monkeypatch):  # noqa: F811
    monkeypatch.delenv("SETU_RESOLUTION_KEY", raising=False)
    _, qid, _ = unsure_fix(engine)
    t, _ = teacher(engine)
    page = t.post("/teacher/queue/settle", data={"queue_item_id": str(qid), "outcome": "correct"}).text
    assert "कुंजी" in page
    assert one(engine, "SELECT status FROM teacher_queue_item WHERE id = :q", q=qid).status == "open"
