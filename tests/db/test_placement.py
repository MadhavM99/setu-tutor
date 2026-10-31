"""Placement diagnostic and the ladder view (slice S7; F-PLACE, F-LAD-UI, X-PERS-03/08, TS-PLACE-*, TS-UI-LAD)."""
import datetime as dt
import re
import uuid

import pytest
from sqlalchemy import text

from setu.domain import placement as P

from .test_aksharas import approved_aksharas  # noqa: F401  (fixture)
from .test_letters import approved_letters, client, exchange_id  # noqa: F401  (fixture)
from .test_words import approved_words  # noqa: F401  (fixture)

PATH = "/learn/placement"


def one(engine, sql, **p):
    with engine.connect() as c:
        return c.execute(text(sql), p).first()


def open_probe(engine, learner):
    return one(engine, "SELECT e.id, e.task FROM exchange e JOIN session s ON s.id = e.session_id LEFT JOIN attempt a "
                       "ON a.exchange_id = e.id WHERE s.learner_id = :l AND s.mode = 'diagnostic' AND a.id IS NULL "
                       "ORDER BY e.created_at DESC LIMIT 1", l=learner)


def run_diagnostic(engine, c, learner, right_bands, limit=40):
    """Answer every probe: correctly in `right_bands`, wrongly elsewhere. Returns the result page."""
    page = c.post(PATH + "/start").text
    for _ in range(limit):
        if "/learn/placement/answer" not in page:
            return page
        probe = open_probe(engine, learner)
        assert probe.task["band"] in ("L0", "L1", "L2", "L3")
        wrong = "ఞఞఞ" if probe.task["task_type"] == "recall" else "ञञञ"
        typed = probe.task["expected"] if probe.task["band"] in right_bands else wrong
        page = c.post(PATH + "/answer", data={"exchange_id": str(probe.id), "typed": typed}).text
    raise AssertionError("the diagnostic did not end")


def placed(engine, learner):
    return {r.skill_id: r for r in engine.connect().execute(text(
        "SELECT skill_id, status, source, due_at FROM learner_skill_state WHERE learner_id = :l"), {"l": learner})}


def test_letters_and_aksharas_right_and_words_wrong_places_l0_l1_and_leaves_l2_open(
        engine, approved_aksharas, approved_words):  # noqa: F811
    c, learner = client(engine)
    intro = c.get(PATH).text
    assert "जाँच लें आप कहाँ से शुरू करें" in intro
    result = run_diagnostic(engine, c, learner, right_bands=("L0", "L1"))
    first = one(engine, "SELECT e.task FROM exchange e JOIN session s ON s.id = e.session_id WHERE s.learner_id = :l "
                        "ORDER BY e.created_at LIMIT 1", l=learner).task
    assert first["band"] == "L2"  # the walk starts at L2
    states = placed(engine, learner)
    l0 = [s for k, s in states.items() if k.startswith(("L0.", "L1."))]
    assert l0 and all(s.status == "placed" and s.source == "placed" for s in l0)
    assert not any(k.startswith(("L2.", "L3.")) for k in states)
    soon = dt.datetime.now(dt.UTC) + dt.timedelta(days=3)
    assert all(s.due_at <= soon for s in l0)  # a confirmation review within three days
    assert "आप ये कर सकते हैं" in result and "यहाँ से शुरू करेंगे" in result and not re.search(r"[A-Za-z]{2,}<", result)
    ev = one(engine, "SELECT payload FROM event_ledger WHERE event_type = 'skill_placed' AND payload->>'learner_id' = :l",
             l=str(learner))
    assert ev.payload["bands"] == ["L0", "L1"] and ev.payload["version"] == P.VERSION
    # placed letters open their aksharas at once, without re-learning every letter
    assert "पहले अक्षर सीखिए" not in c.get("/learn/aksharas").text
    # and a finished diagnostic is not offered again
    assert "/learn/placement/start" not in c.get(PATH).text


def test_a_placed_skill_failed_at_its_confirmation_review_goes_back_to_learning(engine, approved_aksharas):  # noqa: F811
    c, learner = client(engine)
    run_diagnostic(engine, c, learner, right_bands=("L0", "L1", "L2", "L3"))
    assert placed(engine, learner)["L0.script.vowels.RCL"].status == "placed"
    with engine.begin() as x:
        x.execute(text("UPDATE learner_skill_state SET due_at = now() - interval '1 hour' WHERE learner_id = :l"),
                  {"l": learner})
    page = c.get("/learn/letters").text
    assert "/learn/letters/continue" not in page  # a confirmation review, not the intro card again
    c.post("/learn/letters/answer", data={"exchange_id": exchange_id(page), "typed": "ఞఞ", "key": "ఞ"})
    statuses = {s.status for k, s in placed(engine, learner).items() if k.startswith("L0.")}
    assert "learning" in statuses


def test_stopping_at_once_places_nothing_and_starts_from_the_letters(engine, approved_letters):  # noqa: F811
    c, learner = client(engine)
    c.post(PATH + "/start")
    result = c.post(PATH + "/stop").text
    assert placed(engine, learner) == {}
    assert "/learn/letters" in result


def test_the_writer_refuses_a_placement_without_correct_diagnostic_verdicts(engine, approved_letters):  # noqa: F811
    from setu.store.outcome_writer import OutcomeWriter, PlacementRefused

    _, learner = client(engine)
    d = P.decide(learner_id=learner, bands=("L0",), skill_ids=("L0.script.ka.RCL",),
                 verdict_ids=(uuid.uuid4(), uuid.uuid4()))
    with pytest.raises(PlacementRefused):
        OutcomeWriter(engine).apply_placement(d)
    with pytest.raises(TypeError):
        OutcomeWriter(engine).apply_placement(object())
    assert placed(engine, learner) == {}


def test_the_ladder_shows_a_beginner_path_then_placed_skills_as_still_to_confirm(engine, approved_aksharas):  # noqa: F811
    c, learner = client(engine)
    page = c.get("/ladder").text
    assert "मेरी सीढ़ी" in page and "अगला:" in page and "स्वर" in page
    body = re.sub(r"<[^>]+>", " ", page.split("<main", 1)[1].split(">", 1)[1])
    assert not re.search(r"[A-Za-z]", body) and not re.search(r"[0-9०-९]+\s*%", body)
    run_diagnostic(engine, c, learner, right_bands=("L0", "L1", "L2", "L3"))
    page = c.get("/ladder").text
    learning = page.split("अभी सीख रहे हैं", 1)[1].split("आगे", 1)[0]
    assert "पक्का करना बाकी" in learning and "क-वर्ग" in learning
