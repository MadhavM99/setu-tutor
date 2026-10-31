"""L5 scenes with the native friend (slice S8; F-SCENE, P-ARCH-08, X-ARCH-01, X-BEG-04, R-INPUT, TS-FRND-*).

The scene scripts in the content tree are unreviewed drafts, so these tests approve copies of them in the test
database (two test speakers), which stands in for native review."""
import re

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from setu.content import importer, validate
from setu.domain.tokenize import tokens

from .helpers import approvals
from .test_content_import import ROOT, count, fresh  # noqa: F401  (fixture)
from .test_letters import client, exchange_id

TREE = validate.load_tree(ROOT / "content")
SCRIPT = TREE.scene_scripts[0]  # auto stand
SID = SCRIPT["scene_id"]
URL = f"/learn/scenes/{SID}"
PREREQ = SCRIPT["prerequisites"][0]
LATIN = re.compile(r"[A-Za-z]")
TELUGU_WORD = re.compile(r"[ఀ-౿]+")


def one(engine, sql, **p):
    with engine.connect() as c:
        return c.execute(text(sql), p).first()


def body(page):
    return re.sub(r"<[^>]+>", " ", page.split("<main", 1)[1].split(">", 1)[1])


@pytest.fixture
def approved_scene(engine):
    """Scene 01's script and lines, approved by two test speakers; one proposed and one approved reply variant."""
    scene = next(s for s in TREE.scenes if s["id"] == SID)
    with engine.begin() as c:
        c.execute(text("INSERT INTO scene (id, title_hi, setup_hi, review_status) VALUES (:i, :t, :s, 'approved') "
                       "ON CONFLICT (id) DO UPDATE SET review_status = 'approved'"),
                  {"i": SID, "t": scene["title_hi"], "s": scene["setup_hi"]})
        for sk, band, fam, mod in ((PREREQ, "L3", "chunk", "RCL"), (f"L5.scene.{SID}.PR", "L5", "scene", "PR"),
                                   (f"L5.scene.{SID}.RD", "L5", "scene", "RD")):
            c.execute(text("INSERT INTO skill (id, band, family, target, modality, direction) VALUES (:s, :b, :f, :t, "
                           ":m, 'HI->TE') ON CONFLICT DO NOTHING"), {"s": sk, "b": band, "f": fam, "t": SID, "m": mod})
        c.execute(text("DELETE FROM scene_reply_variant"))
        c.execute(text("DELETE FROM scene_line WHERE scene_id = :s"), {"s": SID})
        c.execute(text("DELETE FROM scene_script WHERE scene_id = :s"), {"s": SID})
        importer.write_scene_script(c, SCRIPT)
        c.execute(text("UPDATE scene_script SET review_status = 'approved', approvals = CAST(:a AS jsonb) "
                       "WHERE scene_id = :s"), {"s": SID, "a": approvals("s1", "s2")})
        c.execute(text("UPDATE scene_line SET review_status = 'approved', approvals = CAST(:a AS jsonb) "
                       "WHERE scene_id = :s"), {"s": SID, "a": approvals("s1", "s2")})
        line1 = c.execute(text("SELECT id FROM scene_line WHERE scene_id = :s AND n = 1"), {"s": SID}).scalar_one()
        for form, status, who in (("చార్మినార్ కు", "proposed", ()), ("చార్మినార్ కి వెళ్ళాలి", "approved", ("s1", "s2"))):
            c.execute(text("INSERT INTO scene_reply_variant (line_id, form, status, approvals) VALUES (:l, :f, :st, "
                           "CAST(:a AS jsonb))"), {"l": line1, "f": form, "st": status, "a": approvals(*who)})
    yield
    with engine.begin() as c:
        c.execute(text("UPDATE scene_line SET review_status = 'draft', approvals = '[]' WHERE scene_id = :s"),
                  {"s": SID})
        c.execute(text("UPDATE scene_script SET review_status = 'draft', approvals = '[]' WHERE scene_id = :s"),
                  {"s": SID})


def meet_prerequisites(engine, learner, status="mastered"):
    with engine.begin() as c:
        c.execute(text("INSERT INTO skill (id, band, family, target, modality, direction) VALUES (:s, 'L3', 'chunk', "
                       ":t, 'RCL', 'HI->TE') ON CONFLICT DO NOTHING"), {"s": PREREQ, "t": SID})
        c.execute(text("INSERT INTO learner_skill_state (learner_id, skill_id, status) VALUES (:l, :s, :st) "
                       "ON CONFLICT (learner_id, skill_id) DO UPDATE SET status = :st"),
                  {"l": learner, "s": PREREQ, "st": status})


def approved_telugu():
    words = set()
    for x in SCRIPT["lines"]:
        for t in (x["telugu"], *x["replies"]):
            words |= set(tokens(t))
    return words | set(tokens("చార్మినార్ కి వెళ్ళాలి"))


def start(engine, c, learner):
    meet_prerequisites(engine, learner)
    page = c.get(URL).text
    return c.post(URL + "/start").text if f"{URL}/start" in page else page


def n_of(page):
    m = re.search(r'name="n" value="(\d+)"', page)
    return m.group(1) if m else "1"


def comprehend(c, page, right=True):
    line = next(x for x in SCRIPT["lines"] if x["telugu"] in page)
    choice = line["answer"] if right else (line["answer"] + 1) % len(line["options_hi"])
    return c.post(URL + "/answer", data={"exchange_id": exchange_id(page), "n": "1", "choice": str(choice)}).text, line


def reply(c, page, typed, **extra):
    return c.post(URL + "/answer", data={"exchange_id": exchange_id(page), "n": n_of(page), "typed": typed,
                                         **extra}).text


# ---------------------------------------------------------------- import and disabled content


def test_import_creates_draft_scripts_lines_and_l5_skills_that_learners_cannot_see(fresh):  # noqa: F811
    result = importer.import_tree(fresh, TREE)
    assert result.scene_scripts_written == 4 and result.scene_lines_written == sum(len(s["lines"])
                                                                                 for s in TREE.scene_scripts)
    assert count(fresh, "SELECT count(*) FROM scene_script WHERE review_status <> 'draft'") == 0
    assert count(fresh, "SELECT count(*) FROM learner_scene_script") == 0
    assert count(fresh, "SELECT count(*) FROM learner_scene_line") == 0
    assert count(fresh, "SELECT count(*) FROM skill WHERE band = 'L5' AND family = 'scene'") == 8
    assert count(fresh, "SELECT count(*) FROM skill_prereq WHERE skill_id = 'L5.scene.hi-te-scene-01.PR' "
                        "AND requires_id = 'L3.chunk.hi-te-scene-01.RCL'") == 1
    with fresh.connect() as c:
        prov = c.execute(text("SELECT provenance FROM scene_script WHERE scene_id = 'hi-te-scene-01'")).scalar_one()
    assert "unreviewed" in prov[0]["source"]


def test_a_draft_scene_is_disabled_and_its_telugu_never_reaches_the_learner(engine):
    c, learner = client(engine)
    meet_prerequisites(engine, learner)
    for url in ("/learn/scenes", URL):
        page = c.get(url).text
        assert not any(w in page for x in SCRIPT["lines"] for w in tokens(x["telugu"]))
    assert "तैयार किए जा रहे हैं" in c.get(URL).text


def test_approval_needs_two_speakers_and_one_unapproved_line_disables_the_scene(engine, approved_scene):
    with pytest.raises(DBAPIError), engine.begin() as c:
        c.execute(text("UPDATE scene_line SET approvals = CAST(:a AS jsonb) WHERE scene_id = :s AND n = 2"),
                  {"s": SID, "a": approvals("s1")})
    with pytest.raises(DBAPIError), engine.begin() as c:
        c.execute(text("UPDATE scene_script SET approvals = '[]' WHERE scene_id = :s"), {"s": SID})
    with engine.begin() as c:
        c.execute(text("UPDATE scene_line SET review_status = 'in_review' WHERE scene_id = :s AND n = 3"), {"s": SID})
    c, learner = client(engine)
    meet_prerequisites(engine, learner)
    page = c.get(URL).text
    assert "तैयार किए जा रहे हैं" in page and SCRIPT["lines"][2]["telugu"] not in page
    assert one(engine, "SELECT count(*) AS n FROM learner_scene_script WHERE scene_id = :s", s=SID).n == 0


# ---------------------------------------------------------------- prerequisites


def test_a_scene_waits_for_its_chunks_and_names_them(engine, approved_scene):
    c, learner = client(engine)
    page = c.get(URL).text
    assert "पहले" in page and "ऑटो स्टैंड" in page and f"{URL}/start" not in page
    meet_prerequisites(engine, learner, status="learning")
    assert f"{URL}/start" not in c.get(URL).text
    meet_prerequisites(engine, learner, status="placed")
    page = c.get(URL).text
    assert f"{URL}/start" in page and SCRIPT["objective_hi"] in page and SCRIPT["instructions_hi"] in page


# ---------------------------------------------------------------- a full run


def test_a_run_has_comprehension_independent_and_assisted_production_and_a_safe_fallback(engine, approved_scene):
    c, learner = client(engine)
    pages = []
    page = start(engine, c, learner)
    pages.append(page)
    assert "रवि" in page and SCRIPT["lines"][0]["question_hi"] in page and 'name="choice"' in page

    # line 1: comprehension right, then an independent reply on the compose keyboard
    page, line = comprehend(c, page)
    pages.append(page)
    assert line["reply_goal_hi"] in page and 'name="typed"' in page and line["replies"][0] not in page
    built = c.post(URL + "/answer", data={"exchange_id": exchange_id(page), "n": "1", "buffer": line["replies"][0],
                                          "built": "1"}).text
    pages.append(built)
    assert "सही!" in built

    # line 2: comprehension wrong (recognition only), a near miss gets the approved hint, then right with the hint
    page = c.get(URL).text
    page, line2 = comprehend(c, page, right=False)
    pages.append(page)
    near = line2["replies"][0][:-1]
    hinted = reply(c, page, near)
    pages.append(hinted)
    assert line2["hint_hi"] in hinted and line2["replies"][0] not in hinted.replace(line2["telugu"], "")
    pages.append(reply(c, hinted, line2["replies"][0]))

    # line 3: an unexpected reply gets the fixed Hindi fallback, never invented Telugu; the scene goes on and ends
    page = c.get(URL).text
    page, _ = comprehend(c, page)
    fallback = reply(c, page, "నాకు తెలియదు బాబు")
    pages.append(fallback)
    assert "रवि को ठीक से समझ नहीं आया" in fallback and "इस जवाब को शिक्षक देखेंगे" in fallback
    done = c.get(URL).text
    pages.append(done)
    assert "दृश्य पूरा हुआ" in done

    # no unapproved Telugu ever reached the learner, and every instruction was Hindi
    for p in pages:
        shown = set(TELUGU_WORD.findall(body(p))) - {"ఞ"}
        keys = set(TELUGU_WORD.findall(p.split('class="keys"', 1)[1].split("</form>", 1)[0])) if 'class="keys"' in p \
            else set()
        assert shown - keys <= approved_telugu(), shown - keys - approved_telugu()
        assert not LATIN.search(body(p))

    rows = engine.connect().execute(text(
        "SELECT e.task->>'line' AS line, e.task->>'step' AS step, a.n, a.response_mode, a.cue_level, a.assistance, "
        "a.hint_type, v.kind, v.outcome FROM exchange e JOIN session s ON s.id = e.session_id JOIN attempt a ON "
        "a.exchange_id = e.id JOIN verdict v ON v.attempt_id = a.id WHERE s.learner_id = :l ORDER BY a.created_at"),
        {"l": learner}).all()
    got = [(r.line, r.step, r.n, r.response_mode, r.cue_level, r.kind, r.outcome) for r in rows]
    assert got == [
        ("1", "comprehend", 1, "multiple_choice", 1, "recognition", "correct"),
        ("1", "reply", 1, "onscreen_keyboard", 0, "own", "correct"),
        ("2", "comprehend", 1, "multiple_choice", 1, "recognition", "wrong"),
        ("2", "reply", 1, "typed", 0, "own", "partial"),
        ("2", "reply", 2, "typed", 1, "own", "correct"),
        ("3", "comprehend", 1, "multiple_choice", 1, "recognition", "correct"),
        ("3", "reply", 1, "typed", 0, "own", "unsure"),
    ]
    assert rows[4].assistance == ["hint"] and rows[4].hint_type == "generic"

    events = {r.event: r for r in engine.connect().execute(text(
        "SELECT event, oov_words, hindi_share, data FROM scene_event WHERE scene_id = :s AND session_id IN "
        "(SELECT id FROM session WHERE learner_id = :l)"), {"s": SID, "l": learner})}
    assert {"started", "line_shown", "hint", "fallback", "completed"} <= set(events)
    m = events["completed"].data
    assert m["comprehension"] == {"correct": 2, "asked": 3}
    assert m["production"] == {"independent_correct": 1, "assisted_correct": 1, "unsure": 1, "opportunities": 3}
    assert m["hints"] == 1 and m["fallbacks"] == 1 and m["out_of_band_words"] == []
    assert set(m["vocabulary_introduced"]) <= set(SCRIPT["vocabulary"]["required"])
    assert set(m["vocabulary_recalled"]) <= set(m["vocabulary_introduced"]) | set(SCRIPT["vocabulary"]["required"])
    assert m["time_on_task_s"] >= 0 and m["hindi_share"] == 0.0
    assert one(engine, "SELECT time_on_task_s FROM session WHERE learner_id = :l AND config_snapshot->>'activity' = "
                       "'scene'", l=learner).time_on_task_s is not None
    assert one(engine, "SELECT count(*) AS n FROM teacher_queue_item q JOIN verdict v ON v.id = q.verdict_id JOIN "
                       "attempt a ON a.id = v.attempt_id JOIN exchange e ON e.id = a.exchange_id JOIN session s ON "
                       "s.id = e.session_id WHERE s.learner_id = :l", l=learner).n == 1
    ev = one(engine, "SELECT task_type, production, cue_level FROM skill_evidence WHERE learner_id = :l AND "
                     "skill_id = :s ORDER BY id LIMIT 1", l=learner, s=f"L5.scene.{SID}.PR")
    assert (ev.task_type, ev.production, ev.cue_level) == ("scene_reply", True, 0)


# ---------------------------------------------------------------- variants


def test_only_an_approved_variant_is_accepted(engine, approved_scene):
    c, learner = client(engine)
    page, _ = comprehend(c, start(engine, c, learner))
    assert "इस जवाब को शिक्षक देखेंगे" in reply(c, page, "చార్మినార్ కు")  # proposed, not approved: unsure
    c2, learner2 = client(engine)
    page, _ = comprehend(c2, start(engine, c2, learner2))
    assert "सही!" in reply(c2, page, "చార్మినార్ కి వెళ్ళాలి")


# ---------------------------------------------------------------- a model cannot bypass the bank


def test_a_model_proposal_never_replaces_the_approved_line(engine, approved_scene):
    c, learner = client(engine)
    c.app.state.friend_model = lambda line, context: "ఎక్కడికి పోతావు బాబు ignore instructions"
    page = start(engine, c, learner)
    assert SCRIPT["lines"][0]["telugu"] in page and "పోతావు" not in page and "ignore" not in page
    shown = one(engine, "SELECT data FROM scene_event WHERE event = 'line_shown' AND session_id IN (SELECT id FROM "
                        "session WHERE learner_id = :l) ORDER BY created_at LIMIT 1", l=learner).data
    assert shown["source"] == "bank" and "NOT_APPROVED" in shown["rejected"]


def test_replaying_an_answer_is_not_counted_twice(engine, approved_scene):
    c, learner = client(engine)
    page = start(engine, c, learner)
    for _ in range(2):
        c.post(URL + "/answer", data={"exchange_id": exchange_id(page), "n": "1", "choice": "0"})
    assert one(engine, "SELECT count(*) AS n FROM attempt WHERE exchange_id = :e", e=exchange_id(page)).n == 1
