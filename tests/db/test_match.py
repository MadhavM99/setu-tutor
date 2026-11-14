"""The match game and the UI pass: a learner who has met three words plays a round through the real pages."""
import re

from sqlalchemy import text

from setu.domain import matching

from .test_aksharas import recall_letter
from .test_letters import approved_letters, client, exchange_id  # noqa: F401
from .test_ui_pages import assert_hindi_page
from .test_words import approved_words, only_letters  # noqa: F401  (fixtures)

WORDS = ("te:రెండు", "te:మూడు", "te:ఆరు")


def learn_three_words(engine, c):
    """Learn రెండు, మూడు and ఆరు through the real word pages (letters first), so three cards exist."""
    only_letters(engine, "ఆడమర")
    for ch in "ఆడమర":
        recall_letter(c, ch)
    learned = set()
    for _ in range(40):
        page = c.get("/learn/words").text
        if 'name="exchange_id"' not in page:
            break
        eid = exchange_id(page)
        with engine.connect() as x:
            task = x.execute(text("SELECT task FROM exchange WHERE id = :e"), {"e": eid}).scalar_one()
        word = task["letter_id"]
        if task["type"] == "intro":
            c.post("/learn/words/continue", data={"exchange_id": eid})
        elif task["type"] in ("choice", "meaning"):
            c.post("/learn/words/answer", data={"exchange_id": eid, "choice": word})
        else:
            c.post("/learn/words/answer", data={"exchange_id": eid, "buffer": word.removeprefix("te:"), "built": "1"})
            learned.add(word)
        if len(learned) == 3:
            break
    assert learned == set(WORDS)


def open_round(engine, learner):
    with engine.connect() as x:
        return x.execute(text(
            "SELECT e.id, e.task FROM exchange e JOIN session s ON s.id = e.session_id LEFT JOIN attempt a ON "
            "a.exchange_id = e.id WHERE s.learner_id = :l AND e.task->>'activity' = 'match' AND a.id IS NULL "
            "ORDER BY (e.task->>'slot')::int"), {"l": learner}).all()


def skill_snapshot(engine, learner):
    with engine.connect() as x:
        return x.execute(text("SELECT skill_id, status, cuefree_successes FROM learner_skill_state WHERE "
                              "learner_id = :l ORDER BY skill_id"), {"l": learner}).all()


def test_with_fewer_than_three_met_words_the_game_says_to_learn_words_first(engine, approved_words):  # noqa: F811
    c, _ = client(engine)
    page = c.get("/learn/match")
    assert_hindi_page(page)
    assert "कम से कम तीन शब्द सीखिए" in page.text


def test_a_round_is_the_met_words_and_a_reload_does_not_re_roll_it(engine, approved_words):  # noqa: F811
    c, learner = client(engine)
    learn_three_words(engine, c)
    first = c.get("/learn/match")
    assert_hindi_page(first)
    rows = open_round(engine, learner)
    assert {r.task["letter_id"] for r in rows} == set(WORDS)
    assert len(re.findall(r'name="pair_', first.text)) == 3 * 3  # three words, three answers each
    assert [r.id for r in open_round(engine, learner)] == [r.id for r in rows]
    c.get("/learn/match")
    assert [r.id for r in open_round(engine, learner)] == [r.id for r in rows]


def test_right_answers_are_marked_by_the_checker_and_feed_the_card_schedule_only(engine, approved_words):  # noqa: F811
    c, learner = client(engine)
    learn_three_words(engine, c)
    c.get("/learn/match")
    rows = open_round(engine, learner)
    skills_before = skill_snapshot(engine, learner)
    with engine.connect() as x:
        reps_before = x.execute(text("SELECT coalesce(sum(reps), 0) FROM learner_lexeme_card WHERE learner_id = :l AND "
                                     "card_kind = 'lexeme' AND modality = 'REC'"), {"l": learner}).scalar_one()
    answers = {f"pair_{r.id}": r.task["letter_id"] for r in rows}
    page = c.post("/learn/match/answer", data=answers)
    assert_hindi_page(page)
    assert "३ में से ३ जोड़ियाँ सही" in page.text and "सारी जोड़ियाँ सही हैं" in page.text
    with engine.connect() as x:
        outcomes = x.execute(text(
            "SELECT v.outcome, a.response_mode, a.assistance FROM verdict v JOIN attempt a ON a.id = v.attempt_id "
            "JOIN exchange e ON e.id = a.exchange_id JOIN session s ON s.id = e.session_id WHERE s.learner_id = :l "
            "AND e.task->>'activity' = 'match'"), {"l": learner}).all()
        reps_after = x.execute(text("SELECT coalesce(sum(reps), 0) FROM learner_lexeme_card WHERE learner_id = :l AND "
                                    "card_kind = 'lexeme' AND modality = 'REC'"), {"l": learner}).scalar_one()
    assert [o.outcome for o in outcomes] == ["correct"] * 3
    assert all(o.response_mode == "multiple_choice" and o.assistance == ["choices"] for o in outcomes)
    assert reps_after == reps_before + 3  # the cards were reviewed ...
    assert skill_snapshot(engine, learner) == skills_before  # ... and no skill got evidence from the game
    assert open_round(engine, learner) == []  # the round is finished; the next visit starts a new one


def test_wrong_pairs_are_shown_with_the_right_answer(engine, approved_words):  # noqa: F811
    c, learner = client(engine)
    learn_three_words(engine, c)
    c.get("/learn/match")
    rows = open_round(engine, learner)
    ids = [r.task["letter_id"] for r in rows]
    shifted = ids[1:] + ids[:1]  # every word paired with another word's meaning
    page = c.post("/learn/match/answer", data={f"pair_{r.id}": s for r, s in zip(rows, shifted)})
    assert_hindi_page(page)
    assert page.text.count("सही जोड़ी यह है") == 3 and "कोई बात नहीं" in page.text
    with engine.connect() as x:
        wrong = x.execute(text(
            "SELECT count(*) FROM verdict v JOIN attempt a ON a.id = v.attempt_id JOIN exchange e ON e.id = "
            "a.exchange_id JOIN session s ON s.id = e.session_id WHERE s.learner_id = :l AND "
            "e.task->>'activity' = 'match' AND v.outcome = 'wrong'"), {"l": learner}).scalar_one()
    assert wrong == 3


def test_an_unfinished_round_is_sent_back_with_the_answers_so_far_and_nothing_is_recorded(engine, approved_words):  # noqa: F811
    c, learner = client(engine)
    learn_three_words(engine, c)
    c.get("/learn/match")
    rows = open_round(engine, learner)
    page = c.post("/learn/match/answer", data={f"pair_{rows[0].id}": rows[0].task["letter_id"]})
    assert_hindi_page(page)
    assert "पहले हर शब्द के सामने एक जवाब चुनिए" in page.text and "checked" in page.text
    assert len(open_round(engine, learner)) == 3  # still open, no attempts written
    forged = c.post("/learn/match/answer", data={f"pair_{r.id}": "te:not-a-word" for r in rows})
    assert "पहले हर शब्द के सामने एक जवाब चुनिए" in forged.text
    assert len(open_round(engine, learner)) == 3


def test_picture_rounds_show_pictures_in_the_answers_and_meaning_rounds_show_hindi(engine, approved_words, monkeypatch):  # noqa: F811
    c, learner = client(engine)
    learn_three_words(engine, c)
    monkeypatch.setattr(matching, "round_mode", lambda chosen, seed: "picture")
    page = c.get("/learn/match")
    assert_hindi_page(page)
    assert "chip-pic" in page.text and page.text.count('class="pic"') >= 3 * 3  # a picture per answer, per word
    assert "तस्वीर" in page.text  # the screen-reader labels are Hindi
    c.post("/learn/match/answer", data={f"pair_{r.id}": r.task["letter_id"] for r in open_round(engine, learner)})
    monkeypatch.setattr(matching, "round_mode", lambda chosen, seed: "meaning")
    page = c.get("/learn/match")
    assert "chip-pic" not in page.text and "दो (2)" in page.text


def test_another_learner_cannot_answer_someone_elses_round(engine, approved_words):  # noqa: F811
    c, learner = client(engine)
    learn_three_words(engine, c)
    c.get("/learn/match")
    rows = open_round(engine, learner)
    other, _ = client(engine)
    r = other.post("/learn/match/answer", data={f"pair_{x.id}": x.task["letter_id"] for x in rows},
                   follow_redirects=False)
    assert r.status_code == 303 and len(open_round(engine, learner)) == 3


def test_the_word_pages_and_home_carry_voice_pictures_and_the_path(engine, approved_words):  # noqa: F811
    c, learner = client(engine)
    home = c.get("/")
    assert_hindi_page(home)
    assert 'class="path"' in home.text and "आप यहाँ हैं" in home.text and "/learn/match" not in home.text
    learn_three_words(engine, c)
    home = c.get("/")
    assert_hindi_page(home)
    assert "/learn/match" in home.text  # three met words open the game
    assert "/static/js/voice.js" in home.text
    assert_hindi_page(c.get("/ladder"))


def test_the_word_intro_and_feedback_cards_carry_a_picture_and_voice_controls(engine, approved_words):  # noqa: F811
    only_letters(engine, "కతపస")
    c, _ = client(engine)
    for ch in "కతపస":
        recall_letter(c, ch)
    page = c.get("/learn/words")
    assert_hindi_page(page)
    assert "పుస్తకం" in page.text and 'class="pic"' in page.text and "खुली किताब की तस्वीर" in page.text
    assert 'class="speak speak-big" data-say="పుస్తకం"' in page.text and 'class="say-it"' in page.text
    assert 'class="slow-toggle"' in page.text and "तस्वीर बस याद रखने में मदद के लिए है" in page.text
    assert page.text.count(" hidden>") >= 3  # every voice control starts hidden; voice.js shows what the browser can do
    c.post("/learn/words/continue", data={"exchange_id": exchange_id(page.text)})
    choice = c.get("/learn/words")
    assert_hindi_page(choice)
    assert 'class="pic"' in choice.text  # the target word's picture beside the Hindi prompt
    fb = c.post("/learn/words/answer", data={"exchange_id": exchange_id(choice.text), "choice": "te:పుస్తకం"})
    assert_hindi_page(fb)
    assert 'class="pic"' in fb.text and "data-say=" in fb.text and "celebrate" in fb.text
    meaning = c.get("/learn/words")
    assert 'class="pic"' not in meaning.text  # no picture on a question about what the word means
