"""L4 correction exchanges with the mock classmate (slice S5; TS-EXCH-*, TS-COACH-*, TS-OWN-*, TS-SESS-*, P8b-02)."""
import json
import re

import pytest
from sqlalchemy import text

from .helpers import approvals
from .test_letters import client, exchange_id

GOOD_HINT = "सवाल का निशान आख़िरी शब्द में होता है।"
BANK = {
    "HI-TE-901": [("तुम आ रहे हो क्या", "క్యా నువ్వు వస్తావు", "నువ్వు వస్తావా"),
                  ("यह किताब है क्या", "క్యా ఇది పుస్తకం", "ఇది పుస్తకమా")],
    "HI-TE-902": [("मैं नहीं जाऊँगा", "నేను నహీ వెళ్తాను", "నేను వెళ్ళను"),
                  ("वह नहीं आएगा", "అతను నహీ వస్తాడు", "అతను రాడు")],
    "HI-TE-903": [("यह घर है", "ఇది ఇల్లు ఉంది", "ఇది ఇల్లు"),
                  ("वह पेड़ है", "అది చెట్టు ఉంది", "అది చెట్టు")],
}
MEANING = {m: ok for items in BANK.values() for m, _, ok in items}
WRONG = {w: ok for items in BANK.values() for _, w, ok in items}
CORRECT = {ok for items in BANK.values() for _, _, ok in items}
CONCEPT = {"ideas": [["क्या"], ["अंत", "आख़िर"]], "relations": [["नहीं"]]}


@pytest.fixture(scope="module")
def rule_bank(engine):
    """Three verified, active, teacher-approved rules with two approved practice items each, and hints: one that
    gives the answer away (approved by mistake) and one that does not."""
    with engine.begin() as c:
        for rule_id, items in BANK.items():
            if c.execute(text("SELECT 1 FROM rule WHERE id = :r"), {"r": rule_id}).first():
                continue
            skill = f"L4.rule.{rule_id}.PR"
            c.execute(text("INSERT INTO skill (id, band, family, target, modality, direction) VALUES "
                           "(:s, 'L4', 'rule', :r, 'PR', 'HI->TE')"), {"s": skill, "r": rule_id})
            c.execute(text("INSERT INTO rule (id, direction, contrast_area) VALUES (:r, 'HI->TE', 'questions')"),
                      {"r": rule_id})
            rv = c.execute(text(
                "INSERT INTO rule_version (rule_id, version, title_hi, l1_explanation_hi, concept_key, band, validity, "
                "learner_evidence, lifecycle, teacher_approved, speaker_approvals, target_skill_id) VALUES (:r, 1, "
                ":t, 'हिंदी की आदत यहाँ नहीं चलती।', CAST(:ck AS jsonb), 'L4', 'verified', 'predicted', 'active', true, "
                "CAST(:a AS jsonb), :s) RETURNING id"),
                {"r": rule_id, "t": f"नियम {rule_id[-3:]}", "ck": json.dumps(CONCEPT, ensure_ascii=False),
                 "a": approvals("s1", "s2"), "s": skill}).scalar_one()
            for k, (meaning, wrong, ok) in enumerate(items):
                iid = f"{rule_id}-{'ab'[k]}"
                c.execute(text("INSERT INTO item (id, rule_id) VALUES (:i, :r)"), {"i": iid, "r": rule_id})
                c.execute(text("INSERT INTO item_version (item_id, version, rule_version_id, hindi_meaning, wrong_form, "
                               "correct_form, pool, review_status) VALUES (:i, 1, :rv, :m, :w, :ok, 'practice', "
                               "'approved')"), {"i": iid, "rv": rv, "m": meaning, "w": wrong, "ok": ok})
            for kind, hint in (("recast", f"ऐसे लिखिए: {items[0][2]} या {items[1][2]}"), ("l1_rule", GOOD_HINT)):
                c.execute(text("INSERT INTO hint (rule_version_id, type, text_hi, status, validated_no_answer) "
                               "VALUES (:rv, :k, :h, 'approved', true)"), {"rv": rv, "k": kind, "h": hint})
    yield


def one(engine, sql, **p):
    with engine.connect() as c:
        return c.execute(text(sql), p).first()


def n_of(page):
    m = re.search(r'name="n" value="(\d+)"', page)
    return m.group(1) if m else None


def kind_of(page):
    if 'name="explanation"' in page:
        return "why"
    if "/continue" in page:
        return "intro"
    if any(m in page for m in MEANING):
        return "own"
    if any(w in page for w in WRONG):
        return "planted"
    if any(ok in page for ok in CORRECT):
        return "no_error"
    return "done"


def answer(c, page, **data):
    return c.post("/learn/rules/answer", data={"exchange_id": exchange_id(page), "n": n_of(page), **data})


def play_right(c, page):
    """Answer the current page correctly; returns the response page."""
    k = kind_of(page)
    if k == "intro":
        c.post("/learn/rules/continue", data={"exchange_id": exchange_id(page)})
        return c.get("/learn/rules").text
    if k == "own":
        return answer(c, page, typed=next(ok for m, ok in MEANING.items() if m in page)).text
    if k == "planted":
        return answer(c, page, typed=next(ok for w, ok in WRONG.items() if w in page)).text
    if k == "no_error":
        return answer(c, page, says_correct="1").text
    if k == "why":
        return answer(c, page, explanation="क्या नहीं लगता, अंत में आ लगता है").text
    return c.get("/learn/rules").text


def advance_to(c, want, limit=80):
    page = c.get("/learn/rules").text
    for _ in range(limit):
        if kind_of(page) == want and 'name="exchange_id"' in page:
            return page
        page = play_right(c, page)
        if "/learn/rules\"" in page and 'name="exchange_id"' not in page:  # a close or done page
            page = c.get("/learn/rules").text
    raise AssertionError(f"never reached a {want} turn")


def test_a_new_learner_meets_a_rule_and_writes_an_own_sentence(engine, rule_bank):
    c, learner = client(engine)
    page = c.get("/learn/rules").text
    assert kind_of(page) == "intro" and "नियम 901" in page and "नया नियम" in page
    assert exchange_id(c.get("/learn/rules").text) == exchange_id(page)  # reloading does not re-roll
    c.post("/learn/rules/continue", data={"exchange_id": exchange_id(page)})
    page = c.get("/learn/rules").text
    assert kind_of(page) == "own" and 'name="typed"' in page
    done = answer(c, page, typed=next(ok for m, ok in MEANING.items() if m in page)).text
    assert "सही!" in done
    ev = one(engine, "SELECT task_type, production, outcome FROM skill_evidence WHERE learner_id = :l", l=learner)
    assert (ev.task_type, ev.production, ev.outcome) == ("own", True, "correct")
    assert one(engine, "SELECT count(*) AS n FROM classmate_rule_state WHERE learner_id = :l", l=learner).n == 0
    snap = one(engine, "SELECT config_snapshot AS s, seed FROM session WHERE learner_id = :l", l=learner)
    assert snap.s["classmate_active"] is False and snap.s["planner"] == "planner-1" and len(snap.s["turns"]) == 7


def test_the_classmate_appears_after_three_ready_rules_and_a_correct_fix_teaches_it(engine, rule_bank):
    c, learner = client(engine)
    page = advance_to(c, "planted")
    sessions = [r.s for r in engine.connect().execute(text(
        "SELECT config_snapshot AS s FROM session WHERE learner_id = :l ORDER BY started_at"), {"l": learner})]
    assert [s["classmate_active"] for s in sessions][-1] is True and not sessions[0]["classmate_active"]
    assert "राजू ने लिखा:" in page and "मैंने ये लिखा — सही है?" in page and "ये वाक्य सही है" in page
    done = play_right(c, page)
    assert "राजू ने सीख लिया।" in done and "राजू की गलती:" in done
    st = one(engine, "SELECT count(*) AS n FROM classmate_rule_state WHERE learner_id = :l AND state = 'taught'",
             l=learner)
    ev = one(engine, "SELECT count(*) AS n FROM event_ledger WHERE event_type = 'classmate_taught' "
                     "AND payload->>'learner_id' = :l", l=str(learner))
    assert st.n == ev.n == 1


def test_a_miss_gets_a_hint_without_the_answer_then_the_answer_to_copy_which_teaches_nothing(engine, rule_bank):
    c, learner = client(engine)
    page = advance_to(c, "planted")
    wrong = next(w for w in WRONG if w in page)
    hinted = answer(c, page, typed=wrong).text  # the planted sentence unchanged
    assert "अभी पूरी तरह सही नहीं।" in hinted and GOOD_HINT in hinted
    assert WRONG[wrong] not in hinted.replace(wrong, "") and "ऐसे लिखिए" not in hinted  # the approved-but-leaky hint is never served
    copy = answer(c, hinted, says_correct="1").text
    assert "इसे एक बार लिखिए" in copy and WRONG[wrong] in copy and "ये वाक्य सही है" not in copy
    done = answer(c, copy, typed=WRONG[wrong]).text
    assert "राजू ने सीख लिया।" not in done
    rows = engine.connect().execute(text(
        "SELECT a.n, a.cue_level, a.hint_type, a.after_reveal, v.outcome, v.reason_code FROM attempt a JOIN verdict v "
        "ON v.attempt_id = a.id WHERE a.exchange_id = :e ORDER BY a.n"), {"e": exchange_id(page)}).all()
    assert [(r.n, r.cue_level, r.hint_type, r.after_reveal) for r in rows] == [
        (1, 0, None, False), (2, 1, "l1_rule", False), (3, 2, None, True)]
    assert [r.reason_code for r in rows][:2] == ["planted_error_unchanged", "missed_error"]
    assert rows[2].outcome == "correct"
    assert one(engine, "SELECT count(*) AS n FROM classmate_rule_state WHERE learner_id = :l", l=learner).n == 0
    evidence = one(engine, "SELECT count(*) AS n FROM skill_evidence ev JOIN verdict v ON v.id = ev.verdict_id "
                           "JOIN attempt a ON a.id = v.attempt_id WHERE a.exchange_id = :e", e=exchange_id(page))
    assert evidence.n == 2  # the copy after the reveal is not evidence


def test_an_unsure_fix_goes_to_the_teacher_and_changes_nothing(engine, rule_bank):
    c, learner = client(engine)
    page = advance_to(c, "planted")
    before = one(engine, "SELECT count(*) AS n FROM skill_evidence WHERE learner_id = :l", l=learner).n
    done = answer(c, page, typed="మీరు ఎక్కడ ఉన్నారు").text
    assert "इस जवाब को शिक्षक देखेंगे।" in done
    q = one(engine, "SELECT count(*) AS n FROM teacher_queue_item q JOIN verdict v ON v.id = q.verdict_id JOIN "
                    "attempt a ON a.id = v.attempt_id WHERE a.exchange_id = :e", e=exchange_id(page))
    assert q.n == 1
    assert one(engine, "SELECT count(*) AS n FROM skill_evidence WHERE learner_id = :l", l=learner).n == before
    assert one(engine, "SELECT count(*) AS n FROM classmate_rule_state WHERE learner_id = :l", l=learner).n == 0


def test_why_after_the_third_correct_fix_changes_neither_mastery_nor_the_classmate(engine, rule_bank):
    c, learner = client(engine)
    page = advance_to(c, "why")
    assert "पर ऐसा क्यों?" in page
    fixes = one(engine, "SELECT count(*) AS n FROM verdict v JOIN attempt a ON a.id = v.attempt_id JOIN exchange e "
                        "ON e.id = a.exchange_id JOIN session s ON s.id = e.session_id WHERE s.learner_id = :l AND "
                        "v.kind = 'fix' AND v.outcome = 'correct'", l=learner).n
    assert fixes == 3
    state = lambda: engine.connect().execute(text(
        "SELECT (SELECT count(*) FROM skill_evidence WHERE learner_id = :l), (SELECT string_agg(rule_id || state, ',' "
        "ORDER BY rule_id) FROM classmate_rule_state WHERE learner_id = :l)"), {"l": learner}).first()
    before = state()
    done = answer(c, page, explanation="क्या नहीं लगता, अंत में आ लगता है").text
    assert "राजू की गलती:" in done
    v = one(engine, "SELECT v.kind, v.outcome FROM verdict v JOIN attempt a ON a.id = v.attempt_id WHERE "
                    "a.exchange_id = :e AND a.n = 2", e=exchange_id(page))
    assert (v.kind, v.outcome) == ("explanation", "correct")
    assert state() == before


def test_with_every_rule_taught_a_no_error_turn_comes_and_an_edit_is_a_false_alarm(engine, rule_bank):
    c, learner = client(engine)
    taught = lambda: one(engine, "SELECT count(*) AS n FROM classmate_rule_state WHERE learner_id = :l "
                                 "AND state = 'taught'", l=learner).n
    page = advance_to(c, "no_error", limit=150)
    while taught() < 3:  # a no-error turn can come earlier, while a rule is still plantable
        play_right(c, page)
        page = advance_to(c, "no_error", limit=150)
    shown = next(ok for ok in CORRECT if ok in page)
    edit = next(w for w, ok in WRONG.items() if ok == shown)
    done = answer(c, page, typed=edit).text
    assert "यह वाक्य पहले से सही था।" in done
    v = one(engine, "SELECT v.false_alarm, v.outcome FROM verdict v JOIN attempt a ON a.id = v.attempt_id WHERE "
                    "a.exchange_id = :e", e=exchange_id(page))
    assert v.false_alarm and v.outcome == "wrong"
    snap = one(engine, "SELECT config_snapshot AS s FROM session WHERE learner_id = :l ORDER BY started_at DESC "
                       "LIMIT 1", l=learner).s
    assert [k for k, _ in snap["turns"]].count("no_error") == 1  # R-17: not a stream of no-error turns

    # the own sentences that follow: the Hindi habit of a taught rule is logged as a copy event (M-37)
    page = advance_to(c, "own")
    meaning = next(m for m in MEANING if m in page)
    habit = next(w for items in BANK.values() for m, w, _ in items if m == meaning)
    answer(c, page, typed=habit)
    assert one(engine, "SELECT count(*) AS n FROM copy_event WHERE learner_id = :l", l=learner).n == 1


def test_a_learner_cannot_answer_someone_elses_exchange(engine, rule_bank):
    a, _ = client(engine)
    b, _ = client(engine)
    page = advance_to(a, "own")
    r = b.post("/learn/rules/answer", data={"exchange_id": exchange_id(page), "n": "1", "typed": "ఇది ఇల్లు"},
               follow_redirects=False)
    assert r.status_code == 303
    assert one(engine, "SELECT count(*) AS n FROM attempt a JOIN exchange e ON e.id = a.exchange_id WHERE "
                       "e.id = :e", e=exchange_id(page)).n == 0


def test_a_replayed_answer_form_is_not_counted_twice(engine, rule_bank):
    c, _ = client(engine)
    page = advance_to(c, "own")
    typed = next(ok for m, ok in MEANING.items() if m in page)
    answer(c, page, typed=typed)
    answer(c, page, typed=typed)
    assert one(engine, "SELECT count(*) AS n FROM attempt WHERE exchange_id = :e", e=exchange_id(page)).n == 1
