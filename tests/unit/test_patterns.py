"""Adversarial tests for answer patterns (data-model.md item_version, DQ-06/07, TS-BANK).

Patterns must be fully anchored, safe to run (no catastrophic backtracking), written in the item's target script,
and semantically right: an accept pattern matches the correct form and its accepted variants but not the planted
error or a fragment; a wrong pattern matches the planted error but not the correct form.
"""
import pytest

from setu.content.patterns import check_item_patterns, check_pattern, one_error_span

TE = "telugu"
HI = "devanagari"


@pytest.mark.parametrize("pattern", [
    "^నువ్వు వస్తావా$",
    "^నువ్వు (వస్తావా|వస్తున్నావా)$",
    "^ఇది (నా )?పుస్తకం$",
    "^(?:నేను|మేము) వస్తాను$",
])
def test_well_formed_anchored_patterns_pass(pattern):
    assert check_pattern(pattern, script=TE) == []


@pytest.mark.parametrize("pattern,reason", [
    ("అమ్మను", "not_anchored"),                       # legacy fragment pattern (DQ-07)
    ("^అమ్మను", "not_anchored"),
    ("అమ్మను$", "not_anchored"),
    ("కాదు$", "not_anchored"),                          # legacy over-broad wrong pattern (DQ-06)
    ("^నువ్వు వస్తావా|వస్తున్నావా$", "top_level_alternation"),  # anchors bind only the outer branches
    ("^నువ్వు వస్తావా\\$", "not_anchored"),             # escaped dollar is a literal, not an anchor
    ("^నువ్వు\\Z", "not_anchored"),
    ("^.*అమ్మను.*$", "wildcard"),
    ("^ఇది .+$", "wildcard"),
    ("^$", "matches_empty"),
    ("^(నా)?$", "matches_empty"),
    ("^(?=ఇది)ఇది$", "lookaround"),
    ("^(?!x)ఇది$", "lookaround"),
    ("^(ఇది) \\1$", "backreference"),
    ("^(ఇ+)+$", "nested_repeat"),                       # catastrophic backtracking
    ("^(ఇ|ఇ)*$", "nested_repeat"),
    ("^(?i)ఇది$", "inline_flag"),
    ("(?m)^ఇది$", "inline_flag"),
    ("^ఇది\nఅది$", "newline"),
    ("^(ఇది$", "invalid_regex"),
    ("^nuvvu vastaava$", "wrong_script"),
    ("^यह किताब है$", "wrong_script"),
    ("^" + "ఇ" * 400 + "$", "too_long"),
    ("^ఇ{1,1000}$", "unbounded_or_large_repeat"),
])
def test_unsafe_or_unanchored_patterns_are_rejected(pattern, reason):
    reasons = [i.code for i in check_pattern(pattern, script=TE)]
    assert reason in reasons, reasons


def test_devanagari_items_take_devanagari_patterns():
    assert check_pattern("^यह मेरी किताब है$", script=HI) == []
    assert "wrong_script" in [i.code for i in check_pattern("^ఇది నా పుస్తకం$", script=HI)]


def _codes(issues):
    return sorted({i.code for i in issues})


def test_accept_pattern_must_not_accept_the_planted_error_or_a_fragment():
    issues = check_item_patterns(
        correct="నేను అమ్మను పిలిచాను", accepted=["నేను అమ్మను పిలిచాను"], wrong="నేను అమ్మ పిలిచాను",
        accept_patterns=["^(అమ్మను|నేను అమ్మను పిలిచాను)$"], wrong_patterns=[], script=TE)
    assert "accepts_fragment" in _codes(issues)

    issues = check_item_patterns(
        correct="ఇది పుస్తకం", accepted=["ఇది పుస్తకం"], wrong="ఇది పుస్తకం ఉంది",
        accept_patterns=["^ఇది పుస్తకం( ఉంది)?$"], wrong_patterns=[], script=TE)
    assert "accepts_wrong_form" in _codes(issues)


def test_accept_pattern_must_match_the_correct_form():
    issues = check_item_patterns(
        correct="నువ్వు వస్తావా", accepted=["నువ్వు వస్తావా"], wrong="క్యా నువ్వు వస్తావు",
        accept_patterns=["^నువ్వు వస్తున్నావా$"], wrong_patterns=[], script=TE)
    assert "misses_correct_form" in _codes(issues)


def test_wrong_pattern_must_match_the_wrong_form_and_never_a_correct_one():
    issues = check_item_patterns(
        correct="ఇది పుస్తకం కాదు", accepted=["ఇది పుస్తకం కాదు"], wrong="ఇది పుస్తకం లేదు",
        accept_patterns=[], wrong_patterns=["^ఇది పుస్తకం (కాదు|లేదు)$"], script=TE)
    assert "rejects_correct_form" in _codes(issues)
    issues = check_item_patterns(
        correct="ఇది పుస్తకం కాదు", accepted=["ఇది పుస్తకం కాదు"], wrong="ఇది పుస్తకం లేదు",
        accept_patterns=[], wrong_patterns=["^అది పుస్తకం లేదు$"], script=TE)
    assert "misses_wrong_form" in _codes(issues)


def test_good_item_patterns_pass():
    assert check_item_patterns(
        correct="నువ్వు వస్తావా", accepted=["నువ్వు వస్తావా", "నువ్వు వస్తున్నావా"], wrong="క్యా నువ్వు వస్తావు",
        accept_patterns=["^నువ్వు (వస్తావా|వస్తున్నావా)$"], wrong_patterns=["^క్యా నువ్వు వస్తావు$"], script=TE) == []


# ---------------------------------------------------------------- exactly one error


def test_two_separate_differences_are_flagged_for_review():
    # HI-TE-001-a: the planted sentence differs in two places (క్యా added and -ఆ missing). Whether that is one
    # error of the planted rule is a reviewer's call, so it is flagged rather than silently accepted.
    _, issue = one_error_span(wrong="క్యా నువ్వు వస్తావు", correct="నువ్వు వస్తావా")
    assert issue == "more_than_one_error"


def test_one_error_span_for_a_single_substitution():
    span, issue = one_error_span(wrong="నేను అమ్మ పిలిచాను", correct="నేను అమ్మను పిలిచాను")
    assert issue is None and "నేను అమ్మ పిలిచాను"[span[0]:span[1]] == "అమ్మ"


def test_one_error_span_flags_hi_te_010_a():
    # DQ-04: the legacy planted sentence for HI-TE-010-a contains more than one error.
    _, issue = one_error_span(wrong="ఇది జో పుస్తకం నేను చదివాను", correct="ఇది నేను చదివిన పుస్తకం")
    assert issue == "more_than_one_error"


def test_one_error_span_for_an_omission_has_no_span():
    span, issue = one_error_span(wrong="यह किताब", correct="यह किताब है")
    assert span is None and issue == "omission_error"


def test_identical_wrong_and_correct_is_not_an_error():
    _, issue = one_error_span(wrong="ఇది పుస్తకం", correct="ఇది పుస్తకం")
    assert issue == "no_error"
