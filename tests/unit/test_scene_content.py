"""L5 scene scripts: content rules (slice S8; F-SCENE, X-BEG-04, X-NOENG, TS-FRND-*)."""
import copy
import re
from pathlib import Path

import pytest

from setu.content import validate
from setu.domain.tokenize import tokens

ROOT = Path(__file__).resolve().parents[2]
TREE = validate.load_tree(ROOT / "content")
LATIN = re.compile(r"[A-Za-z]")


def errors(tree):
    return [e for e in validate.validate_tree(tree).errors if "scene-script" in e.code or e.detail.startswith("script:")]


def test_four_scene_scripts_exist_as_unreviewed_drafts():
    ids = [s["scene_id"] for s in TREE.scene_scripts]
    assert ids == ["hi-te-scene-01", "hi-te-scene-02", "hi-te-scene-03", "hi-te-scene-04"]
    for s in TREE.scene_scripts:
        assert s["review_status"] == "draft" and all(x["review_status"] == "draft" for x in s["lines"])
        assert "unreviewed" in s["provenance"][0]["source"]
    assert errors(TREE) == []


def test_every_script_defines_objective_band_prerequisites_vocabulary_and_two_productions():
    for s in TREE.scene_scripts:
        assert s["band"] == "L5" and s["objective_hi"] and s["instructions_hi"]
        assert s["prerequisites"] == [f"L3.chunk.{s['scene_id']}.RCL"]
        assert s["vocabulary"]["required"]
        assert sum(1 for x in s["lines"] if x["replies"]) >= 2  # independent production in every run
        for x in s["lines"]:
            assert x["question_hi"] and len(x["options_hi"]) >= 2 and 0 <= x["answer"] < len(x["options_hi"])


def test_hindi_fields_have_no_latin_and_telugu_stays_inside_the_scene_vocabulary():
    for s in TREE.scene_scripts:
        words = set(s["vocabulary"]["required"]) | set(s["vocabulary"].get("permitted") or [])
        hindi = [s["objective_hi"], s["instructions_hi"]] + [v for x in s["lines"] for v in
                                                           (x["question_hi"], x["reply_goal_hi"], x["hint_hi"],
                                                            *x["options_hi"])]
        assert not any(LATIN.search(h) for h in hindi)
        for x in s["lines"]:
            for text in (x["telugu"], *x["replies"]):
                assert set(tokens(text)) <= words, (s["scene_id"], text)


def broken(mutate):
    tree = copy.deepcopy(TREE)
    mutate(tree.scene_scripts[0])
    return {e.code for e in errors(tree)}


def test_a_word_outside_the_scene_vocabulary_is_refused():
    assert "scene-script:oov_word" in broken(lambda s: s["lines"][0].update(telugu="ఎక్కడికి పోతావు బాబు"))


def test_a_hint_that_holds_the_reply_is_refused():
    def leak(s):
        s["lines"][0]["hint_hi"] = "लिखिए " + s["lines"][0]["replies"][0]
    assert "scene-script:hint_has_answer" in broken(leak)


def test_fewer_than_two_productions_latin_instructions_or_approval_claims_are_refused():
    assert "scene-script:too_few_productions" in broken(lambda s: [x.update(replies=[]) for x in s["lines"][1:]])
    assert "scene-script:latin_in_hindi" in broken(lambda s: s.update(instructions_hi="Say hello"))
    assert "approval_claim" in broken(lambda s: s.update(review_status="approved"))
    assert "approval_claim" in broken(lambda s: s["lines"][0].update(review_status="approved"))
    assert "scene-script:bad_answer" in broken(lambda s: s["lines"][0].update(answer=9))
    assert "scene-script:unknown_scene" in broken(lambda s: s.update(scene_id="hi-te-scene-99"))


@pytest.mark.parametrize("field", ["objective_hi", "instructions_hi", "prerequisites", "vocabulary", "lines"])
def test_missing_script_fields_are_refused(field):
    assert "scene-script:missing_field" in broken(lambda s: s.pop(field))
