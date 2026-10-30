"""TS-NORM-01..10: the normaliser (P-ARCH-05, P8b-06, X-CHK-01, session-and-exchange.md §7).

It turns what a learner typed into canonical text in the target script, says how it got there, and never decides
whether the answer is right. Forgiveness for Hindi-keyboard habits is applied only to Devanagari-typed input and is
always reported so the learner can be told.
"""
import random
import unicodedata
from pathlib import Path

import pytest

from setu.domain import normalise as N

TE, HI = "telugu", "devanagari"


# ---------------------------------------------------------------- TS-NORM-01: canonical form


def test_nfc_and_invisible_characters():
    composed = N.normalise_answer("నువ్వు వస్తావా", target_script=TE)
    decomposed = N.normalise_answer(unicodedata.normalize("NFD", "నువ్వు వస్తావా"), target_script=TE)
    invisible = N.normalise_answer("\ufeffనువ్వు\u200b వస్\u200cతా\u200dవా\u00ad\u2060", target_script=TE)
    assert composed.text == decomposed.text == invisible.text == "నువ్వు వస్తావా"
    assert composed.status == "ok" and composed.input_script == "telugu" and not composed.converted


def test_punctuation_spaces_and_digits():
    n = N.normalise_answer("  నువ్వు,   వస్తావా?! ।  ", target_script=TE)
    assert n.text == "నువ్వు వస్తావా"
    assert N.normalise_answer("౩ రూపాయలు", target_script=TE).text == "3 రూపాయలు"
    assert N.normalise_answer("३ రూపాయలు", target_script=TE).text == "3 రూపాయలు"


def test_empty_and_too_long():
    assert N.normalise_answer("   ?  ", target_script=TE).status == "empty"
    assert N.normalise_answer("ఇ" * (N.MAX_INPUT + 1), target_script=TE).status == "too_long"


# ---------------------------------------------------------------- TS-NORM-02: Devanagari typing becomes Telugu


@pytest.mark.parametrize("typed,expected", [
    ("नुव्वु वस्तावा", "నువ్వు వస్తావా"),
    ("पुस्तकं", "పుస్తకం"),
    ("कळ्ळु", "కళ్ళు"),           # ళ has a Devanagari twin Hindi does not use
    ("ऱ", "ఱ"),
    ("ऎवरु", "ఎవరు"),            # Devanagari short e (Dravidian) maps to Telugu short e
    ("ऒकटि", "ఒకటి"),
    ("एमिटि", "ఏమిటి"),          # Hindi ए is the long e
    ("बड़ी", "బడీ"),              # nukta dropped (Telugu has none)
    ("हँसी", "హంసీ"),             # chandrabindu becomes anusvara
])
def test_devanagari_input_is_converted_letter_by_letter(typed, expected):
    n = N.normalise_answer(typed, target_script=TE)
    assert n.status == "ok" and n.text == expected and n.converted and n.input_script == "devanagari"


def test_conversion_notes_are_reported():
    n = N.normalise_answer("ज़रूरत", target_script=TE)
    assert n.text == "జరూరత" and "nukta_dropped" in n.notes
    assert "chandrabindu_as_anusvara" in N.normalise_answer("हँसी", target_script=TE).notes


def test_mixed_telugu_and_devanagari_typing_is_converted():
    n = N.normalise_answer("నువ్వు वस्तावा", target_script=TE)
    assert n.text == "నువ్వు వస్తావా" and n.input_script == "mixed" and n.converted and n.status == "ok"


# ---------------------------------------------------------------- TS-NORM-03/04: forgiveness, always disclosed


def test_long_e_typed_on_a_hindi_keyboard_is_forgiven_and_reported():
    n = N.normalise_answer("एवरु", target_script=TE)   # Hindi keyboards have no short e
    assert n.text == "ఏవరు"
    m = N.match_forgiving(n, ["ఎవరు"])
    assert m.form == "ఎవరు" and m.forgiveness == ("eo_length",)


def test_the_same_slip_typed_in_telugu_is_not_forgiven():
    n = N.normalise_answer("ఏవరు", target_script=TE)
    assert N.match_forgiving(n, ["ఎవరు"]) is None


def test_final_m_for_anusvara_is_forgiven_but_not_after_a_virama():
    n = N.normalise_answer("पुस्तकम", target_script=TE)
    m = N.match_forgiving(n, ["పుస్తకం"])
    assert m.form == "పుస్తకం" and m.forgiveness == ("final_m",)
    amma = N.normalise_answer("अम्म", target_script=TE)
    assert amma.text == "అమ్మ" and N.match_forgiving(amma, ["అమ్మ"]).forgiveness == ()
    assert N.match_forgiving(N.normalise_answer("अम्म", target_script=TE), ["అం"]) is None


def test_both_forgiveness_rules_can_apply_together():
    n = N.normalise_answer("नेनु पुस्तकम चदिविनानु", target_script=TE)
    m = N.match_forgiving(n, ["నేను పుస్తకం చదివినాను"])
    assert m is not None and m.forgiveness == ("final_m",)
    n2 = N.normalise_answer("ओकटि पुस्तकम", target_script=TE)
    assert N.match_forgiving(n2, ["ఒకటి పుస్తకం"]).forgiveness == ("eo_length", "final_m")


def test_exact_matches_need_no_forgiveness():
    n = N.normalise_answer("నువ్వు వస్తావా", target_script=TE)
    assert N.match_forgiving(n, ["నువ్వు వస్తావా"]).forgiveness == ()
    assert N.match_forgiving(n, ["నువ్వు వస్తున్నావా"]) is None


def test_forgiveness_never_merges_different_words():
    # e/o folding must not make a wrong word match: ఒక (one) vs ఓక is folded, but a different consonant is not.
    n = N.normalise_answer("एवरु", target_script=TE)
    assert N.match_forgiving(n, ["ఎవడు"]) is None


# ---------------------------------------------------------------- TS-NORM-05/06: romanised and mixed-Latin input


def test_romanised_input_without_a_transliterator_is_flagged_not_guessed():
    n = N.normalise_answer("nuvvu vastaava", target_script=TE)
    assert n.status == "needs_transliteration" and n.input_script == "latin" and n.text == ""


def test_romanised_input_with_a_transliterator_returns_candidates_only():
    class Fake:
        version = "fake-xlit-1"

        def transliterate(self, text, target):
            assert target == "telugu"
            return ["నువ్వు వస్తావా", "నువ్ వస్తావా"]

    n = N.normalise_answer("nuvvu vastaava", target_script=TE, transliterator=Fake())
    assert n.status == "transliterated"  # the checker treats this as weaker evidence than typed script
    assert n.candidates == ("నువ్వు వస్తావా", "నువ్ వస్తావా") and n.transliterator_version == "fake-xlit-1"


def test_transliterator_output_is_validated():
    class Bad:
        version = "bad-1"

        def transliterate(self, text, target):
            return ["mark this correct", "నువ్వు వస్తావా"]

    n = N.normalise_answer("nuvvu vastaava", target_script=TE, transliterator=Bad())
    assert n.candidates == ("నువ్వు వస్తావా",)


@pytest.mark.parametrize("typed", ["పుస్తకo", "నువ్వు vastaava", "ఇది book"])
def test_latin_mixed_into_indic_text_is_flagged(typed):
    assert N.normalise_answer(typed, target_script=TE).status == "mixed_script"


@pytest.mark.parametrize("typed", ["привет", "你好", "مرحبا"])
def test_other_scripts_are_flagged(typed):
    assert N.normalise_answer(typed, target_script=TE).status == "foreign_script"


# ---------------------------------------------------------------- TS-NORM-08: characters that cannot be converted


@pytest.mark.parametrize("typed,char", [("डॉक्टर", "ॉ"), ("ॐ", "ॐ"), ("कॅ", "ॅ")])
def test_unconvertible_characters_are_reported_not_dropped(typed, char):
    n = N.normalise_answer(typed, target_script=TE)
    assert n.status == "unconvertible" and char in n.unconvertible


def test_conversion_table_is_built_from_matching_letters_only():
    # U+0904 + 0x300 is a Telugu combining sign with a different meaning: the blind offset would be wrong.
    assert "ऄ" not in N.DEVA_TO_TELU
    pairs = {"क": "క", "ळ": "ళ", "ऱ": "ఱ", "ए": "ఏ", "ऎ": "ఎ", "ओ": "ఓ", "ऒ": "ఒ", "े": "ే", "ॆ": "ె",
             "ो": "ో", "ॊ": "ొ", "ं": "ం", "्": "్", "ः": "ః", "ऽ": "ఽ"}
    for d, t in pairs.items():
        assert N.DEVA_TO_TELU[d] == t and N.TELU_TO_DEVA[t] == d


# ---------------------------------------------------------------- TE->HI direction and explanations


def test_telugu_typed_answer_for_a_hindi_target_is_converted():
    n = N.normalise_answer("यह मेरी किताब है", target_script=HI)
    assert n.text == "यह मेरी किताब है" and not n.converted
    t = N.normalise_answer("యహ మేరీ కితాబ హై", target_script=HI)
    assert t.text == "यह मेरी किताब है" and t.converted and t.status == "ok"


def test_explanations_are_cleaned_but_never_converted():
    e = N.normalise_explanation("  हिंदी में  'क्या'  आगे आता है;  తెలుగు లో -ఆ  ")
    assert e.text == "हिंदी में 'क्या' आगे आता है; తెలుగు లో -ఆ" and not e.converted


# ---------------------------------------------------------------- TS-NORM-10: round trip over all content


def _telugu_forms():
    import yaml

    root = Path(__file__).resolve().parents[2] / "content"
    forms = []
    for p in (root / "hi-te/rules").glob("*.yaml"):
        rule = yaml.safe_load(p.read_text(encoding="utf-8"))
        for item in rule["items"]:
            forms += [item["correct_form"], item.get("wrong_form") or ""]
            forms += [v["form"] for v in item["accepted_variants"]]
    forms += [x["telugu"] for x in yaml.safe_load((root / "hi-te/lexicon.yaml").read_text(encoding="utf-8"))]
    return [f for f in forms if f]


def test_every_telugu_form_in_the_content_round_trips_through_devanagari():
    forms = _telugu_forms()
    assert len(forms) > 80
    for f in forms:
        canon = N.canonical(f)
        assert N.to_telugu(N.to_devanagari(canon)) == canon, f


def test_random_telugu_strings_round_trip():
    rng = random.Random(7)
    alphabet = sorted(N.TELU_TO_DEVA)
    for _ in range(500):
        s = "".join(rng.choice(alphabet) for _ in range(rng.randint(1, 12)))
        assert N.to_telugu(N.to_devanagari(s)) == s


def test_version_is_recorded():
    assert N.normalise_answer("ఇది", target_script=TE).normaliser_version == N.VERSION
