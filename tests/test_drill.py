"""Stay on a letter until you get it: the drill after the cards, before the scored check."""
import random
from pathlib import Path
from setu.bank import load_units
from setu.memory import Store
from setu.tutor import Tutor
from setu.writer import TemplateWriter

DATA = Path(__file__).resolve().parent.parent / "data"


def tutor(tmp_path, **kw):
    kw.setdefault("course", "singles")
    return Tutor(Store(str(tmp_path)), writer=TemplateWriter(random.Random(0)), seed=1, **kw)


def current(t, lid="a"):
    p = t.store.load(lid).pending
    return p, t.items[p["queue"][0]][1] if p["kind"] == "drill" else None


def test_lesson_starts_a_drill_over_every_letter_before_the_check(tmp_path):
    t = tutor(tmp_path)
    r = t.next("a")
    unit = t.by_id[r["unit"]]
    assert "drill" in r and "check" not in r
    p, _ = current(t)
    assert p["kind"] == "drill" and sorted(p["queue"]) == sorted(i.item_id for i in unit.items)
    seen = []
    while t.store.load("a").pending["kind"] == "drill":
        _, item = current(t); seen.append(item.item_id)
        a = t.answer("a", item.accepted[0])
    assert sorted(seen) == sorted(i.item_id for i in unit.items)        # all right first time: each asked once
    assert "check" in a and t.store.load("a").pending["kind"] == "check"
    assert t.store.load("a").raju == {}                                 # the drill never adds anything to Raju


def test_a_miss_shows_the_same_card_and_stays_on_that_letter(tmp_path):
    t = tutor(tmp_path)
    t.next("a")
    _, item = current(t)
    a = t.answer("a", "ॐ")
    assert a["verdict"] == "wrong" and a["card"]["telugu"] == item.prompt      # same card again
    assert a["next"]["item"] == item.item_id                                    # same letter, not the next one


def test_a_missed_letter_must_be_right_once_more_later(tmp_path):
    t = tutor(tmp_path)
    t.next("a")
    _, item = current(t)
    t.answer("a", "ॐ")
    a = t.answer("a", item.accepted[0])                 # right straight after seeing the card
    p = t.store.load("a").pending
    assert p["kind"] == "drill" and item.item_id in p["queue"]                  # it comes back
    asked = 0
    while t.store.load("a").pending["kind"] == "drill":
        _, it = current(t); asked += it.item_id == item.item_id
        t.answer("a", it.accepted[0])
    assert asked == 1


def test_three_misses_move_on_and_mark_the_letter_weak(tmp_path):
    t = tutor(tmp_path)
    r = t.next("a")
    _, item = current(t)
    hl = t.store.load("a").mem(r["unit"]).half_life
    for _ in range(2):
        assert "weak" not in t.answer("a", "ॐ")
    a = t.answer("a", "ॐ")
    assert a["weak"] and item.accepted[0] in a["message"]
    rec = t.store.load("a")
    assert item.item_id in rec.weak and item.item_id not in rec.pending.get("queue", [])
    assert rec.mem(r["unit"]).half_life < hl                                   # this unit fades sooner


def test_raju_picks_the_weak_letter_first_and_fixing_it_clears_it(tmp_path):
    t = tutor(tmp_path)
    t.next("a")
    _, weak_item = current(t)
    for _ in range(3):
        t.answer("a", "ॐ")
    while t.store.load("a").pending["kind"] == "drill":
        t.answer("a", current(t)[1].accepted[0])
    unit = t.by_id[t.store.load("a").pending["unit"]]
    t.answer("a", unit.check.accepted[0])
    r = t.next("a")
    p = t.store.load("a").pending
    assert r["kind"] == "raju" and p["mistake"] and p["item"] == weak_item.item_id
    t.answer("a", weak_item.accepted[0])
    assert weak_item.item_id not in t.store.load("a").weak


def test_drill_works_for_words_typed_on_a_hindi_keyboard(tmp_path):
    t = tutor(tmp_path)
    unit = next(u for u in t.units if u.unit_id == "L1-05")
    item = next(i for i in unit.items if i.prompt == "पुस्तक")
    assert t._card(unit, item).telugu == "పుస్తకం"
    from setu.checker import check
    assert check(item, "पुस्तकं").verdict == "correct"


def test_every_card_can_be_found_again_after_a_miss():
    for u in load_units():
        for it in u.items:
            assert Tutor._card(u, it) is not None, it.item_id


def test_images_are_optional_and_any_set_must_exist():
    for u in load_units():
        for line in u.lesson:
            if line.image:
                assert (DATA / "hi-te" / line.image).is_file(), (u.unit_id, line.image)
