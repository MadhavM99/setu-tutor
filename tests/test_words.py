"""Level 1 (words): numbers, first words, question words, Hindi-twin words, false friends."""
from setu.bank import load_units, all_items
from setu.checker import check
from setu.text import deva_to_telugu

UNITS = load_units()
WORDS = [u for u in UNITS if u.level == 1]
ITEMS = all_items(UNITS)
SIGNS = set("ంాిీుూెేైొోౌ్")   # ం ా ి ీ ు ూ ె ే ై ొ ో ౌ ్


def taught_letters() -> set[str]:
    out = set()
    for u in UNITS:
        if u.level == 0:
            for line in u.lesson:
                out.update(c for c in line.telugu if "ఀ" <= c <= "౿")
    return out


def test_words_come_after_all_letters():
    assert WORDS[0].requires == [f"L0-{len([u for u in UNITS if u.level == 0]):02d}"]
    assert [u.unit_id for u in WORDS] == [f"L1-{k:02d}" for k in range(1, 7)]


def test_every_telugu_word_uses_only_letters_already_taught():
    """No word may contain a letter or sign the learner has not met in Level 0."""
    known = taught_letters() | SIGNS
    for u in WORDS:
        texts = [l.telugu for l in u.lesson] + [x for it in [u.check, *u.items] for x in [it.prompt, *it.accepted, it.raju_wrong]]
        for t in texts:
            bad = {c for c in t if "ఀ" <= c <= "౿" and c not in known}
            assert not bad, (u.unit_id, t, bad)


def test_raju_mistakes_are_wrong_and_answers_right():
    for u in WORDS:
        for it in [u.check, *u.items]:
            assert check(it, it.raju_wrong).verdict == "wrong", it.item_id
            for a in it.accepted:
                assert check(it, a).verdict == "correct", (it.item_id, a)


def test_type_telugu_with_a_hindi_keyboard():
    assert deva_to_telugu("पुस्तकं") == "పుస్తకం"
    book = ITEMS["L1-05-a"][1]                         # पुस्तक -> పుస్తకం ; Raju forgets the ం
    assert check(book, "पुस्तकं").verdict == "correct"  # typed in Hindi, read as Telugu
    assert check(book, "पुस्तक").reason == "Raju's mistake left unchanged"   # Hindi word without ం = Raju's error


def test_numbers_accept_digits():
    two = ITEMS["L1-01-a"][1]
    assert all(check(two, a).verdict == "correct" for a in ("दो", "2", "२"))
    assert check(two, "तीन").verdict == "wrong"


def test_false_friends():
    need = ITEMS["L1-06-a"][1]                         # అవసరం
    assert check(need, "ज़रूरत").verdict == "correct"
    assert check(need, "अवसर").verdict == "wrong"       # the Hindi look-alike is exactly Raju's mistake
    assert check(need, "मांग").verdict == "unsure"      # open item: a synonym we did not list goes to a teacher
