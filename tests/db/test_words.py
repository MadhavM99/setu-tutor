"""L2 words: approval, visibility and the word practice pages (migration 0010, slice S3; TS-L2-*, P-LSP-07)."""
import json

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from setu.content import importer, validate

from .helpers import approvals
from .test_aksharas import recall_letter
from .test_content_import import ROOT, count, fresh  # noqa: F401  (fixture)
from .test_letters import approved_letters, client, exchange_id  # noqa: F401  (fixture)

LEXICON = validate.load_tree(ROOT / "content").lexemes


def test_import_fills_word_order_letters_look_alikes_and_word_skills(fresh):  # noqa: F811
    importer.import_tree(fresh, validate.load_tree(ROOT / "content"))
    with fresh.connect() as c:
        w = c.execute(text("SELECT word_group, ladder_order, letters, looks_like_hi FROM lexeme WHERE id = 'te:అవసరం'"))\
            .one()
    assert (w.word_group, w.letters, w.looks_like_hi) == ("L1-06", ["అ", "వ", "స", "ర"], "अवसर")
    assert count(fresh, "SELECT count(*) FROM lexeme WHERE word_group IS NULL OR ladder_order IS NULL") == 0
    assert count(fresh, "SELECT count(*) FROM skill WHERE band = 'L2' AND family = 'word'") == 12
    assert count(fresh, "SELECT count(*) FROM skill_prereq WHERE skill_id = 'L2.word.L1-05.REC' "
                        "AND requires_id = 'L1.akshara.vowel_signs.REC'") == 1
    assert count(fresh, "SELECT count(*) FROM learner_lexeme") == 0


def insert_words(c, status="approved"):
    for order, lex in enumerate(LEXICON, start=1):
        c.execute(text("INSERT INTO lexeme (id, telugu, hindi_gloss, cognate_of, false_friend, false_friend_note_hi, "
                       "looks_like_hi, word_group, ladder_order, letters, review_status, approvals) VALUES (:id, :te, "
                       ":g, :cog, :ff, :note, :look, :grp, :o, CAST(:l AS jsonb), :st, CAST(:a AS jsonb)) "
                       "ON CONFLICT (id) DO UPDATE SET review_status = EXCLUDED.review_status, "
                       "approvals = EXCLUDED.approvals, letters = EXCLUDED.letters, word_group = EXCLUDED.word_group, "
                       "ladder_order = EXCLUDED.ladder_order, looks_like_hi = EXCLUDED.looks_like_hi"),
                  {"id": lex["id"], "te": lex["telugu"], "g": lex["hindi_gloss"], "cog": lex.get("cognate_of"),
                   "ff": lex["false_friend"], "note": lex.get("false_friend_note_hi"),
                   "look": lex.get("looks_like_hi"), "grp": lex["dev_notes"]["unit"], "o": order,
                   "l": json.dumps(importer.word_letters(lex["telugu"])), "st": status,
                   "a": approvals("s1", "s2") if status == "approved" else "[]"})


@pytest.fixture
def approved_words(engine, approved_letters):  # noqa: F811
    with engine.begin() as c:
        insert_words(c)
        for lex in LEXICON:
            for m in ("REC", "RCL"):
                c.execute(text("INSERT INTO skill (id, band, family, target, modality, direction) VALUES "
                               "(:s, 'L2', 'word', :g, :m, 'HI->TE') ON CONFLICT DO NOTHING"),
                          {"s": importer.word_skill_id(lex["dev_notes"]["unit"], m), "g": lex["dev_notes"]["unit"],
                           "m": m})
    yield
    with engine.begin() as c:
        c.execute(text("UPDATE lexeme SET review_status = 'draft', approvals = '[]' WHERE id = ANY(:i)"),
                  {"i": [lex["id"] for lex in LEXICON]})


def only_letters(engine, chars):
    with engine.begin() as x:
        x.execute(text("UPDATE letter SET review_status = 'in_review', approvals = '[]' WHERE NOT telugu = ANY(:c)"),
                  {"c": list(chars)})


def test_a_word_needs_two_approvals_and_approved_letters(engine, approved_words):
    with pytest.raises(DBAPIError), engine.begin() as c:
        c.execute(text("UPDATE lexeme SET approvals = CAST(:a AS jsonb) WHERE id = 'te:పుస్తకం'"),
                  {"a": approvals("s1")})
    only_letters(engine, "కతపస")
    with engine.connect() as c:
        visible = set(c.execute(text("SELECT id FROM learner_lexeme")).scalars())
    assert "te:పుస్తకం" in visible and "te:సమయం" not in visible


def test_a_learner_learns_a_cognate_through_meaning_and_cue_free_recall(engine, approved_words):
    only_letters(engine, "కతపస")
    c, learner = client(engine)
    assert "पहले अक्षर सीखिए" in c.get("/learn/words").text  # letters not yet recalled
    for ch in "కతపస":
        recall_letter(c, ch)
    page = c.get("/learn/words").text
    assert "नया शब्द" in page and "పుస్తకం" in page and "हिंदी के ‘पुस्तक’ जैसा" in page
    c.post("/learn/words/continue", data={"exchange_id": exchange_id(page)})
    page = c.get("/learn/words").text
    assert "किस तेलुगु शब्द का मतलब है" in page
    c.post("/learn/words/answer", data={"exchange_id": exchange_id(page), "choice": "te:పుస్తకం"})
    page = c.get("/learn/words").text
    assert "इस शब्द का मतलब क्या है" in page
    c.post("/learn/words/answer", data={"exchange_id": exchange_id(page), "choice": "te:పుస్తకం"})
    page = c.get("/learn/words").text
    assert "तेलुगु में लिखिए" in page and 'value="ు"' in page and 'value="ం"' in page
    fb = c.post("/learn/words/answer", data={"exchange_id": exchange_id(page), "buffer": "పుస్తకం", "built": "1"})
    assert "सही" in fb.text
    with engine.connect() as x:
        cards = dict(x.execute(text("SELECT modality, reps FROM learner_lexeme_card WHERE learner_id = :l AND "
                                    "card_kind = 'lexeme' AND card_ref = 'te:పుస్తకం'"), {"l": learner}).all())
        skill = x.execute(text("SELECT cuefree_successes FROM learner_skill_state WHERE learner_id = :l AND "
                               "skill_id = 'L2.word.L1-05.RCL'"), {"l": learner}).scalar_one()
    assert cards == {"REC": 2, "RCL": 1} and skill == 1


def test_choosing_a_false_friends_look_alike_is_wrong_and_explained(engine, approved_words):
    only_letters(engine, "అవసర")
    c, learner = client(engine)
    for ch in "అరవస":
        recall_letter(c, ch)
    page = c.get("/learn/words").text
    assert "అవసరం" in page and "‘अवसर’ जैसा दिखता है" in page
    c.post("/learn/words/continue", data={"exchange_id": exchange_id(page)})
    c.post("/learn/words/answer", data={"exchange_id": exchange_id(c.get("/learn/words").text),
                                        "choice": "te:అవసరం"})
    page = c.get("/learn/words").text
    assert 'value="trap:te:అవసరం"' in page and ">अवसर<" in page
    fb = c.post("/learn/words/answer", data={"exchange_id": exchange_id(page), "choice": "trap:te:అవసరం"}).text
    assert "सही जवाब यह है" in fb and "मतलब अलग है" in fb
    with engine.connect() as x:
        outcome = x.execute(text(
            "SELECT v.outcome FROM verdict v JOIN attempt a ON a.id = v.attempt_id JOIN exchange e ON e.id = "
            "a.exchange_id JOIN session s ON s.id = e.session_id WHERE s.learner_id = :l AND "
            "e.task->>'type' = 'meaning'"), {"l": learner}).scalar_one()
    assert outcome == "wrong"


def test_word_pages_are_hindi_only(engine, approved_words):
    from .test_ui_pages import assert_hindi_page

    only_letters(engine, "అవసర")
    c, _ = client(engine)
    for ch in "అరవస":
        recall_letter(c, ch)
    page = c.get("/learn/words")
    assert_hindi_page(page)
    c.post("/learn/words/continue", data={"exchange_id": exchange_id(page.text)})
    for answer in ({"choice": "te:అవసరం"}, {"choice": "trap:te:అవసరం"}, {"buffer": "అవసరం", "built": "1"}):
        page = c.get("/learn/words")
        assert_hindi_page(page)
        assert_hindi_page(c.post("/learn/words/answer", data={"exchange_id": exchange_id(page.text), **answer}))
