"""Pure parts of the UI pass: the match game's round logic, the word pictures, and the learning path."""
import datetime as dt
from pathlib import Path

from setu.content import validate
from setu.domain import matching as M
from setu.web import path as P
from setu.web import pictures
from setu.web.i18n import Catalog

ROOT = Path(__file__).resolve().parents[2]
NOW = dt.datetime(2026, 11, 14, tzinfo=dt.UTC)


def words(n, **kw):
    return [M.Word(f"w{i}", f"t{i}", f"m{i}", **kw) for i in range(n)]


def test_a_round_needs_three_met_words_and_holds_at_most_four():
    assert M.pick_round(words(2), now=NOW, seed=1) == []
    assert len(M.pick_round(words(3), now=NOW, seed=1)) == 3
    assert len(M.pick_round(words(9), now=NOW, seed=1)) == 4


def test_due_words_come_first_then_a_seeded_shuffle():
    ws = words(8)
    ws[6] = M.Word("w6", "t6", "m6", due=NOW - dt.timedelta(days=2))
    ws[3] = M.Word("w3", "t3", "m3", due=NOW - dt.timedelta(days=1))
    ws[1] = M.Word("w1", "t1", "m1", due=NOW + dt.timedelta(days=1))  # not due yet
    chosen = M.pick_round(ws, now=NOW, seed=5)
    assert [w.id for w in chosen[:2]] == ["w6", "w3"]
    assert M.pick_round(ws, now=NOW, seed=5) == chosen  # same seed, same round


def test_options_are_the_same_words_in_a_shuffled_order():
    chosen = words(4)
    opts = M.option_order(chosen, seed=3)
    assert sorted(opts) == sorted(w.id for w in chosen) and M.option_order(chosen, seed=3) == opts


def test_picture_mode_needs_a_picture_for_every_word():
    modes = {M.round_mode(words(4, has_picture=True), seed=s) for s in range(40)}
    assert modes == {"picture", "meaning"}
    mixed = words(4, has_picture=True)[:3] + [M.Word("x", "t", "m", has_picture=False)]
    assert {M.round_mode(mixed, seed=s) for s in range(40)} == {"meaning"}


def test_the_summary_line_follows_the_score():
    assert M.summary([True] * 4) == "great"
    assert M.summary([True, True, False, False]) == "good"
    assert M.summary([True, False, False, False]) == "keep"


def test_every_lexicon_word_has_a_picture_except_the_one_left_out_on_purpose():
    lexicon = {x["telugu"] for x in validate.load_tree(ROOT / "content").lexemes}
    assert lexicon - set(pictures.PICTURES) == {"అవసరం"}  # 'need' has no honest picture
    assert set(pictures.PICTURES) <= lexicon  # no picture for a word the course does not teach


def test_picture_labels_exist_in_the_hindi_catalog_and_the_svg_is_self_contained():
    cat = Catalog.load(ROOT / "locale/hi.yaml", pending_file=ROOT / "locale/pending.txt")
    for word in pictures.PICTURES:
        html = str(pictures.picture(word, cat.get))
        if pictures.photo_file(word):  # a shipped picture file: served from our own static folder, with Hindi alt text
            assert html.startswith('<img class="pic pic-photo" src="/static/img/words/') and "http" not in html and 'alt="' in html
        else:
            assert html.startswith("<svg") and 'role="img"' in html and "http" not in html and "<image" not in html
    assert pictures.picture("అవసరం", cat.get) is None and not pictures.has_picture("అవసరం")


def test_number_pictures_show_the_right_number_of_dots():
    cat = Catalog.load(ROOT / "locale/hi.yaml", pending_file=ROOT / "locale/pending.txt")
    for word, n in (("ఒకటి", 1), ("మూడు", 3), ("ఐదు", 5), ("ఏడు", 7), ("పది", 10)):
        assert str(pictures.picture(word, cat.get)).count('class="dotfill"') == n


def target(band, done=False, placed=False):
    return {"band": band, "placed": placed, "done": done}


def test_the_path_marks_one_stage_as_current_and_never_calls_an_empty_stage_done():
    can = [target("L0", done=True), target("L0", done=True)]
    now = [target("L1")]
    later = [target("L2")]
    path = P.build(can, now, later)
    assert [s["state"] for s in path] == ["done", "now", "soon", "soon", "soon", "soon"]
    assert path[0]["done"] == path[0]["total"] == 2 and path[5]["total"] == 0
    assert sum(1 for s in path if s["state"] == "now") == 1


def test_a_placed_target_counts_towards_its_stage():
    path = P.build([], [target("L0", placed=True)], [])
    assert path[0]["state"] == "done" and path[0]["done"] == 1
