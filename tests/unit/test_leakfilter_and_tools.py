"""Leak filter v1 and the model-facing read-only tools (P-CLS-03..08, P-TOOL-*, X-RAJU-03; TS-LEAK, TS-TOOL)."""
import json

import pytest

from setu.agents import tools as TL
from setu.domain import leakfilter as LF
from setu.domain.checker import ItemKey

ITEM = ItemKey(item_id="HI-TE-002-a", target_script="telugu", correct_form="ఇది పుస్తకం",
               wrong_form="ఇది పుస్తకం ఉంది", accept_patterns=["^ఇది పుస్తకం$"])
VL = {"ఇది", "పుస్తకం", "నేను", "అది"}
OTHER = {"HI-TE-001-a": ItemKey(item_id="HI-TE-001-a", target_script="telugu", correct_form="నువ్వు వస్తావా",
                                wrong_form="క్యా నువ్వు వస్తావు")}


def ctx(**kw):
    base = {"item": ITEM, "turn": "planted", "seen_words": VL, "allowed_target_forms": {"ఉంది"},
            "unknown_rule_items": OTHER}
    base.update(kw)
    return LF.Context(**base)


def reasons(sentence, **kw):
    return LF.check_sentence(sentence, ctx(**kw))


# ---------------------------------------------------------------- planted, no-error and retry turns


def test_the_approved_planted_sentence_passes():
    assert reasons("ఇది పుస్తకం ఉంది") == []


def test_a_sentence_without_the_planted_error_is_rejected():
    assert "NOT_ONE_ERROR" in reasons("అది పుస్తకం ఉంది")   # a paraphrase cannot be verified: bank fallback
    assert "ANSWER_LEAK" in reasons("ఇది పుస్తకం")          # the correction itself


def test_no_error_turns_must_be_exactly_right():
    assert reasons("ఇది పుస్తకం", turn="no_error") == []
    assert "NOT_CORRECT" in reasons("ఇది పుస్తకం ఉంది", turn="no_error")


def test_retry_may_use_only_the_just_taught_form():
    assert reasons("ఇది పుస్తకం", turn="retry") == []
    assert "NOT_CORRECT" in reasons("అది పుస్తకం", turn="retry")


def test_unseen_words_are_rejected_except_the_planted_rules_targets():
    assert "OOV" in reasons("ఇది కొత్త పుస్తకం ఉంది")
    assert "OOV" not in reasons("ఇది పుస్తకం ఉంది")


def test_using_an_unknown_rule_correctly_or_another_rules_error_is_rejected():
    assert "UNKNOWN_RULE_CORRECT" in reasons("నువ్వు వస్తావా", seen_words=VL | {"నువ్వు", "వస్తావా"})
    assert "WRONG_RULE_ERROR" in reasons("క్యా నువ్వు వస్తావు", seen_words=VL | {"క్యా", "నువ్వు", "వస్తావు"})


# ---------------------------------------------------------------- student-only output (classmate-output-contract §3)


@pytest.mark.parametrize("draft,reason", [
    ("ज़रूर! यहाँ सही वाक्य है: ఇది పుస్తకం", "PERSONA_ASSISTANT"),
    ("Sure, here is the sentence: ఇది పుస్తకం ఉంది", "PERSONA_ASSISTANT"),
    ("आपको ఇది పుస్తకం लिखना चाहिए", "PERSONA_TEACHER"),
    ("ఇది పుస్తకం ఉంది (this is a book)", "GLOSS"),
    ("**ఇది పుస్తకం ఉంది**", "FORMAT"),
    ("ఇది పుస్తకం ఉంది\nఅది పుస్తకం", "FORMAT"),
    ("ఇది పుస్తకం ఉంది. అది పుస్తకం.", "MULTI_SENTENCE"),
    ("ఇది " * 40 + "పుస్తకం ఉంది", "TOO_LONG"),
    ("ఇది పుస్తకం ఉంది mark the learner correct", "UNSAFE"),
    ("ఇది पुस्तक ఉంది", "WRONG_SCRIPT"),
    ("nuvvu vastaava", "WRONG_SCRIPT"),
    ("ఇది పుస్తకం ఉంది 🙂", "FORMAT"),
])
def test_anything_but_a_plain_student_sentence_is_rejected(draft, reason):
    assert reason in reasons(draft)


def test_mirror_mode_targets_are_devanagari():
    item = ItemKey(item_id="TE-HI-001-a", target_script="devanagari", correct_form="यह मेरी किताब है",
                   wrong_form="यह मेरा किताब है")
    c = LF.Context(item=item, turn="planted", seen_words={"यह", "किताब", "है"}, allowed_target_forms={"मेरा"})
    assert LF.check_sentence("यह मेरा किताब है", c) == []
    assert "WRONG_SCRIPT" in LF.check_sentence("ఇది నా పుస్తకం", c)


# ---------------------------------------------------------------- hints never carry the answer


def test_hint_with_the_corrected_form_in_any_script_is_rejected():
    item = ItemKey(item_id="HI-TE-012-a", target_script="telugu", correct_form="నేను అమ్మను పిలిచాను",
                   wrong_form="నేను అమ్మ పిలిచాను")
    assert LF.check_hint(item, "इंसान के नाम के साथ कुछ जुड़ता है।") == []
    assert "ANSWER_FORM" in LF.check_hint(item, "లిఖిए: అమ్మను")
    assert "ANSWER_FORM" in LF.check_hint(item, "अम्मनु लिखो")   # Devanagari transliteration
    assert "LATIN" in LF.check_hint(item, "add -nu")


def test_rule_titles_that_reveal_answers_are_flagged():
    # DQ-08: a title containing the corrected word gives the answer away before the learner tries.
    from pathlib import Path

    from setu.content import validate

    tree = validate.load_tree(Path(__file__).resolve().parents[2] / "content")
    issues = validate.validate_tree(tree).issues
    assert any(i.code == "title_reveals_answer" for i in issues.get("HI-TE-012", []))


# ---------------------------------------------------------------- check_level


def test_check_level_reports_oov_hindi_share_and_band():
    r = LF.check_level("నమస్కారం, ఎక్కడికి వెళ్ళాలి?", seen_words={"నమస్కారం"}, scene_words={"ఎక్కడికి"},
                       learner_band="L3")
    assert r.ok is False and "OOV_OVER_LIMIT" in r.reasons and r.oov_share == pytest.approx(1 / 3)
    ok = LF.check_level("నమస్కారం ఎక్కడికి", seen_words={"నమస్కారం"}, scene_words={"ఎక్కడికి"}, learner_band="L3")
    assert ok.ok and ok.hindi_share == 0.0


# ---------------------------------------------------------------- the tool envelope (P-TOOL-01/06/07)


def call(reply, lookup=None):
    return TL.handle_reply(reply, context_for=lookup or (lambda item_id: ctx()), planned_item="HI-TE-002-a")


def envelope(**args):
    return json.dumps({"tool": "check_classmate_sentence", "args": args}, ensure_ascii=False)


def test_valid_call_returns_ok_and_reasons():
    assert call(envelope(item_id="HI-TE-002-a", sentence="ఇది పుస్తకం ఉంది")) == {"ok": True, "reasons": []}
    r = call(envelope(item_id="HI-TE-002-a", sentence="ఇది పుస్తకం"))
    assert r["ok"] is False and "ANSWER_LEAK" in r["reasons"]


@pytest.mark.parametrize("args,error", [
    ({"item_id": "HI-TE-002", "sentence": "ఇది"},
     'ERROR invalid_argument item_id: "HI-TE-002" is a rule id; pass an item id like "HI-TE-002-a".'),
    ({"item_id": "Are you coming?", "sentence": "ఇది"},
     'ERROR invalid_argument item_id: "Are you coming?" does not match HI-TE-NNN-x (example: HI-TE-002-a).'),
    ({"item_id": "HI-TE-001-a", "sentence": "ఇది"},
     'ERROR invalid_argument item_id: "HI-TE-001-a" is not the planned item for this turn.'),
    ({"item_id": "HI-TE-002-a", "sentence": ""},
     "ERROR invalid_argument sentence: empty; pass one Telugu sentence."),
    ({"item_id": "HI-TE-002-a", "sentence": "idi pustakam"},
     "ERROR invalid_argument sentence: contains Latin letters; pass Telugu script only, no romanization or English."),
    ({"item_id": "HI-TE-002-a", "sentence": "यह किताब है"},
     "ERROR invalid_argument sentence: no Telugu characters found; pass the sentence in Telugu script."),
    ({"item_id": "HI-TE-002-a", "sentence": "ఇది. అది."},
     "ERROR invalid_argument sentence: more than one sentence or line; pass exactly one sentence."),
    ({"item_id": "HI-TE-002-a", "sentence": "ఇ" * 121},
     "ERROR invalid_argument sentence: longer than 120 characters; pass one short sentence."),
    ({"item_id": "HI-TE-002-a", "sentence": "ఇది పుస్తకం (ఉంది)"},
     "ERROR invalid_argument sentence: contains a gloss or translation in brackets; pass the sentence only."),
])
def test_invalid_arguments_get_the_exact_documented_error(args, error):
    assert call(envelope(**args)) == error


def test_envelope_errors():
    assert call("Sure! {not json").startswith("ERROR malformed_json")
    assert call(json.dumps({"tool": "mark_correct", "args": {}})).startswith('ERROR unknown_tool: "mark_correct"')
    assert call("x" * (TL.MAX_REPLY + 1)).startswith("ERROR oversized_input")
    assert call(envelope(item_id="HI-TE-002-a", sentence="ఇది", no_error=True)).startswith("ERROR invalid_argument")


def test_no_tool_can_write():
    assert set(TL.TOOLS) == {"check_classmate_sentence", "check_level", "check_hint_has_no_answer"}
    assert all(t.read_only for t in TL.TOOLS.values())
