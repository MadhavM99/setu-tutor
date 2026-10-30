"""Tokenizer, Token Miss Rate and leveler v0 (P-DIFF-01, P-DIFF-03, E-16, X-LEV-01/04; TS-TMR-*, TS-LEV-*).

Leveler v0 is the paper's baseline: the item band is the hardest of four dimensions (script, vocabulary, word forms,
structure). It is unvalidated. A dimension the data cannot yet measure is reported as unassessed, never guessed,
and the label is marked incomplete.
"""
import pytest

from setu.domain import leveler as L
from setu.domain import tokenize as T

# ---------------------------------------------------------------- tokenizer (E-16)


def test_tokens_are_canonical_surface_forms():
    assert T.tokens("  నువ్వు,  వస్తావా?  ") == ["నువ్వు", "వస్తావా"]
    assert T.tokens("నువ్వు\u200b వస్తావా") == ["నువ్వు", "వస్తావా"]
    # tokenizer-1 does not split clitics: ఇంట్లో is one surface form (the analyser arrives in Phase 4)
    assert T.tokens("నేను ఇంట్లో ఉన్నాను") == ["నేను", "ఇంట్లో", "ఉన్నాను"]
    assert T.VERSION == "tokenizer-1"


# ---------------------------------------------------------------- TMR (Eq. 1)


def test_tmr_counts_unseen_word_occurrences():
    r = T.tmr("నేను ఇంటికి వెళ్తున్నాను", known={"నేను", "వెళ్తున్నాను"})
    assert r.value == pytest.approx(1 / 3) and r.oov == ("ఇంటికి",) and r.n_tokens == 3
    assert r.tokenizer_version == "tokenizer-1"


def test_tmr_is_zero_when_every_word_is_known():
    assert T.tmr("ఇది పుస్తకం", known={"ఇది", "పుస్తకం"}).value == 0.0


def test_target_words_of_the_planted_rule_are_exempt():
    r = T.tmr("ఇది పుస్తకం ఉంది", known={"ఇది", "పుస్తకం"}, exempt={"ఉంది"})
    assert r.value == 0.0 and r.oov == ()


def test_tmr_counts_repeats_and_ignores_punctuation_and_form_differences():
    r = T.tmr("అమ్మ, అమ్మ!", known=set())
    assert r.value == 1.0 and r.oov == ("అమ్మ",) and r.n_tokens == 2
    assert T.tmr("నువ్వు వస్తావా", known={"నువ్వు", "వస్తావా"}).value == 0.0
    import unicodedata
    assert T.tmr(unicodedata.normalize("NFD", "నువ్వు"), known={"నువ్వు"}).value == 0.0


def test_numbers_are_not_unseen_words():
    assert T.tmr("3 రూపాయలు", known={"రూపాయలు"}).value == 0.0


def test_tmr_of_an_empty_sentence_is_an_error():
    with pytest.raises(ValueError):
        T.tmr(" ? ", known=set())


# ---------------------------------------------------------------- leveler v0


def test_single_independent_letters_are_l0_and_akshara_are_l1():
    assert L.level("ళ").dimensions["script"].band == "L0"
    assert L.level("అ ఆ").dimensions["script"].band == "L0"
    assert L.level("కా").dimensions["script"].band == "L1"       # vowel sign
    assert L.level("క్క").dimensions["script"].band == "L1"      # virama / conjunct
    assert L.level("అం").dimensions["script"].band == "L1"       # anusvara


def test_structure_from_length_and_contrast_family():
    assert L.level("పుస్తకం").dimensions["structure"].band == "L2"
    assert L.level("నా పుస్తకం").dimensions["structure"].band == "L3"
    assert L.level("ఇది పుస్తకం", contrast_area="copula").dimensions["structure"].band == "L4"
    assert L.level("ఇది నేను చదివిన పుస్తకం", contrast_area="clauses").dimensions["structure"].band == "L5"


def test_band_is_the_hardest_dimension_and_names_it():
    r = L.level("ఇది నేను చదివిన పుస్తకం", contrast_area="clauses")
    assert r.band == "L5" and r.deciding == "structure"
    assert "structure" in r.reason and r.leveler_version == "leveler-v0"


def test_unmeasured_dimensions_are_unassessed_not_guessed():
    r = L.level("ఇది పుస్తకం", contrast_area="copula")
    assert r.dimensions["vocabulary"].band is None and r.dimensions["word_forms"].band is None
    assert not r.complete and set(r.unassessed) == {"vocabulary", "word_forms"}
    assert "unassessed" in r.reason


def test_vocabulary_from_frequency_ranks_when_available():
    ranks = {"ఇది": 12, "పుస్తకం": 850}
    r = L.level("ఇది పుస్తకం", contrast_area="copula", frequency_ranks=ranks)
    assert r.dimensions["vocabulary"].band == "L3"   # the rarest word (rank 850) sets it
    unknown = L.level("ఇది కొత్తపదం", frequency_ranks=ranks)
    assert unknown.dimensions["vocabulary"].band is None and "కొత్తపదం" in unknown.dimensions["vocabulary"].reason


def test_learner_relative_checks_report_unknown_letters_and_tmr():
    r = L.level("ఇది పుస్తకం", known_letters=set("ఇదిపుస్త"), known_words={"ఇది"})
    assert set(r.unknown_letters) == {"క", "ం"}
    assert r.tmr == pytest.approx(0.5)


def test_leveler_is_deterministic_and_registered_as_a_baseline():
    a = L.level("ఇది పుస్తకం", contrast_area="copula")
    b = L.level("ఇది పుస్తకం", contrast_area="copula")
    assert a == b
    assert "leveler-v0" in L.LEVELERS  # kept as the baseline when richer levelers are compared (X-LEV-04)


def test_devanagari_items_are_levelled_too():
    r = L.level("यह मेरी किताब है", contrast_area="gender", script="devanagari")
    assert r.dimensions["script"].band == "L1" and r.band == "L4"
