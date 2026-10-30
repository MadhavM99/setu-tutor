"""Level 0 (letters): content sanity and checker behaviour."""
from setu.bank import load_units, all_items
from setu.checker import check

UNITS = load_units()
LETTERS = [u for u in UNITS if u.level == 0]
ITEMS = all_items(UNITS)
OFF = 0x300                       # Telugu block = Devanagari block + 0x300


def test_letter_units_come_in_order_and_chain():
    assert [u.unit_id for u in LETTERS] == [f"L0-{k:02d}" for k in range(1, len(LETTERS) + 1)]
    assert LETTERS[0].requires == []
    for prev, u in zip(LETTERS, LETTERS[1:]):
        assert u.requires == [prev.unit_id]


def test_twin_letters_really_are_twins():
    """Every single-letter lesson line maps Devanagari -> Telugu by the fixed Unicode offset (no typos)."""
    for u in LETTERS:
        for line in u.lesson:
            d = line.hindi.split()[0]
            if len(d) == 1 and len(line.telugu) == 1:
                assert ord(line.telugu) - ord(d) == OFF, (u.unit_id, line)


def test_every_question_is_about_a_letter_taught_in_its_lesson():
    """Raju never asks about a letter the learner was not shown (the 'learn first' promise)."""
    for u in LETTERS:
        shown = {line.telugu for line in u.lesson}
        for it in [u.check, *u.items]:
            assert it.prompt in shown, (it.item_id, it.prompt)


def test_raju_mistakes_are_real_mistakes():
    for u in LETTERS:
        for it in [u.check, *u.items]:
            assert check(it, it.raju_wrong).verdict == "wrong"
            assert check(it, it.accepted[0]).verdict == "correct"


def test_checker_examples():
    kha = ITEMS["L0-07-b"][1]                    # ఖ -> ख ; Raju says क
    assert check(kha, "ख").verdict == "correct"
    assert check(kha, " ख। ").verdict == "correct"          # spaces and danda are ignored
    assert check(kha, "क").reason == "Raju's mistake left unchanged"
    assert check(kha, "ग").verdict == "wrong"                # closed item: any other letter is wrong
    assert check(kha, "kha").reason.startswith("wrong script")
    assert check(kha, "").verdict == "unsure"


def test_new_sounds_accept_words_too():
    short_e = ITEMS["L0-04-a"][1]                # ఎ: Hindi has no short e
    assert check(short_e, "ऎ").verdict == "correct"
    assert check(short_e, "छोटा ए").verdict == "correct"
    assert check(short_e, "ए").verdict == "wrong"           # the long ए is Raju's mistake
    lla = ITEMS["L0-18-b"][1]                    # ళ
    assert check(lla, "ळ").verdict == "correct" and check(lla, "ल").verdict == "wrong"


def test_every_letter_card_has_memory_hooks():
    """Each letter card gives the learner something to hold on to: a shape and a mnemonic."""
    for u in LETTERS:
        for line in u.lesson:
            assert line.shape and line.mnemonic, (u.unit_id, line.hindi)


def test_units_are_small():
    assert all(len(u.lesson) <= 4 for u in LETTERS)


def test_breath_pairs_are_taught_together():
    """Plain and breathy partners sit in one unit, and Raju's mistake is exactly that confusion."""
    pairs = [{"क", "ख"}, {"ग", "घ"}, {"च", "छ"}, {"ज", "झ"}, {"ट", "ठ"}, {"ड", "ढ"}, {"त", "थ"}, {"द", "ध"},
             {"प", "फ"}, {"ब", "भ"}]
    for u in LETTERS:
        shown = {l.hindi for l in u.lesson}
        for it in u.items:
            if {it.accepted[0], it.raju_wrong} in pairs:
                assert {it.accepted[0], it.raju_wrong} <= shown, (u.unit_id, it.item_id)
