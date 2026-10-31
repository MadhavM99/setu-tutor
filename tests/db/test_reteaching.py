"""Spaced re-teaching: the classmate forgets when the learner is predicted to forget, and the rule comes back as a
planted error in a later session, never the same one, with a different sentence (slice S6; F-REV, P-LSP-03,
P8b-01, TS-SCHED-*, TS-CLS-10..14)."""
import datetime as dt

from sqlalchemy import text

from .test_correction import WRONG, advance_to, answer, client, one, rule_bank  # noqa: F401  (fixture)


def teach_one(engine, c, learner):
    """Reach the first planted turn, fix it without help, and end the session. Returns (rule_id, item_id)."""
    page = advance_to(c, "planted")
    wrong = next(w for w in WRONG if w in page)
    answer(c, page, typed=WRONG[wrong])
    row = one(engine, "SELECT rv.rule_id, i.item_id FROM exchange e JOIN rule_version rv ON rv.id = e.rule_version_id "
                      "JOIN item_version i ON i.id = e.item_version_id WHERE e.shown_text = :w AND e.session_id IN "
                      "(SELECT id FROM session WHERE learner_id = :l) ORDER BY e.created_at DESC LIMIT 1",
              w=wrong, l=learner)
    with engine.begin() as x:
        x.execute(text("UPDATE session SET ended_at = now() WHERE learner_id = :l AND ended_at IS NULL"),
                  {"l": learner})
    return row.rule_id, row.item_id


def state(engine, learner, rule_id):
    return one(engine, "SELECT state FROM classmate_rule_state WHERE learner_id = :l AND rule_id = :r",
               l=learner, r=rule_id).state


def first_turn(engine, learner):
    return one(engine, "SELECT config_snapshot AS s FROM session WHERE learner_id = :l AND ended_at IS NULL",
               l=learner).s["turns"][0]


def test_a_rule_not_yet_due_is_not_forgotten(engine, rule_bank):  # noqa: F811
    c, learner = client(engine)
    rule_id, _ = teach_one(engine, c, learner)
    now = dt.datetime.now(dt.UTC)
    c.app.state.clock = lambda: now + dt.timedelta(hours=1)
    c.get("/learn/rules")
    assert state(engine, learner, rule_id) == "taught"


def test_a_forgotten_rule_is_planted_first_days_later_with_another_sentence(engine, rule_bank):  # noqa: F811
    c, learner = client(engine)
    rule_id, item_id = teach_one(engine, c, learner)
    later = dt.datetime.now(dt.UTC) + dt.timedelta(days=30)
    c.app.state.clock = lambda: later
    page = c.get("/learn/rules").text
    assert state(engine, learner, rule_id) == "forgotten"
    assert first_turn(engine, learner) == ["planted", rule_id]
    assert "राजू यह नियम पहले सीख चुका था, पर भूल गया।" in page
    shown = one(engine, "SELECT i.item_id FROM exchange e JOIN item_version i ON i.id = e.item_version_id JOIN session s "
                        "ON s.id = e.session_id WHERE s.learner_id = :l AND s.ended_at IS NULL ORDER BY e.created_at "
                        "LIMIT 1", l=learner).item_id
    assert shown != item_id

    wrong = next(w for w in WRONG if w in page)  # re-teaching makes the classmate know it again
    done = answer(c, page, typed=WRONG[wrong]).text
    assert "राजू ने सीख लिया।" in done and state(engine, learner, rule_id) == "taught"
    ev = one(engine, "SELECT count(*) AS n FROM event_ledger WHERE payload->>'learner_id' = :l AND "
                     "event_type IN ('classmate_forgot', 'classmate_taught') AND payload->>'rule_id' = :r",
             l=str(learner), r=rule_id)
    assert ev.n == 3  # taught, forgot, taught again


def test_forgetting_runs_only_when_a_session_starts(engine, rule_bank):  # noqa: F811
    c, learner = client(engine)
    rule_id, _ = teach_one(engine, c, learner)
    c.get("/learn/rules")  # a new session starts now; the rule is fresh
    c.app.state.clock = lambda: dt.datetime.now(dt.UTC) + dt.timedelta(days=30)
    c.get("/learn/rules")  # same session continues: no forgetting mid-session
    assert state(engine, learner, rule_id) == "taught"
