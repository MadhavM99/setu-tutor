"""Content conversion and validation (slice 1.4; TS-BANK-01..14, TS-DSR-01..02, E-06).

The committed `content/` tree must be reproducible from the source snapshots, lose no provenance, carry nothing
that claims review or approval, and keep learner-facing fields free of Latin script.
"""
import copy
import hashlib
import json
import re
from pathlib import Path

import pytest

from setu.content import convert, validate
from setu.content.schema import canonical_json

ROOT = Path(__file__).resolve().parents[2]
CONTENT = ROOT / "content"
LATIN = re.compile(r"[A-Za-z]")


@pytest.fixture(scope="module")
def tree():
    return validate.load_tree(CONTENT)


@pytest.fixture(scope="module")
def report(tree):
    return validate.validate_tree(tree)


def test_committed_content_has_no_errors(report):
    assert report.errors == []


def test_counts_match_both_source_banks(tree):
    hi_te = [r for r in tree.rules if r["direction"] == "HI->TE"]
    te_hi = [r for r in tree.rules if r["direction"] == "TE->HI"]
    assert (len(hi_te), sum(len(r["items"]) for r in hi_te)) == (15, 29)
    assert (len(te_hi), sum(len(r["items"]) for r in te_hi)) == (10, 20)


def test_hi_te_rules_keep_provenance_from_both_repositories(tree):
    for rule in tree.rules:
        repos = {p["repo"] for p in rule["provenance"]}
        if rule["direction"] == "HI->TE":
            assert repos == {"setu-tutor", "LMA---Reverse-learning-Tutor"}, rule["rule_id"]
        else:
            assert repos == {"LMA---Reverse-learning-Tutor"}, rule["rule_id"]
        for p in rule["provenance"]:
            assert p["commit"] and p["path"] and p["pointer"] and p["description"]


def test_provenance_is_lossless(tree):
    """Every provenance record embeds the raw source record, and its hash matches the source file today."""
    setu_bank = json.loads((ROOT / "legacy/data/hi-te/rules.json").read_text(encoding="utf-8"))["rules"]
    lma_bank = json.loads((ROOT / "content/sources/lma-c11a63a/l1-hi_l2-te/rules.json").read_text(encoding="utf-8"))
    lma_te = json.loads((ROOT / "content/sources/lma-c11a63a/l1-te_l2-hi/rules.json").read_text(encoding="utf-8"))
    by_source = {
        "setu-tutor": {r["rule_id"]: r for r in setu_bank},
        "LMA---Reverse-learning-Tutor": {r["rule_id"]: r for r in lma_bank + lma_te},
    }
    for rule in tree.rules:
        for p in rule["provenance"]:
            assert hashlib.sha256(canonical_json(p["original"]).encode()).hexdigest() == p["record_sha256"]
            assert p["original"] == by_source[p["repo"]][rule["rule_id"]]


def test_vendored_snapshot_matches_recorded_file_hashes():
    manifest = json.loads((ROOT / "content/sources/lma-c11a63a/MANIFEST.json").read_text(encoding="utf-8"))
    for rel, digest in manifest["sha256"].items():
        data = (ROOT / "content/sources/lma-c11a63a" / rel).read_bytes()
        assert hashlib.sha256(data).hexdigest() == digest, rel


def test_nothing_is_imported_as_reviewed_or_active(tree):
    for rule in tree.rules:
        assert rule["validity"] == "uncertain" and rule["lifecycle"] == "draft"
        assert rule["learner_evidence"] in ("model_predicted", "predicted")
        for key in ("teacher_approved", "speaker_approvals", "reviewers", "reviewed_at"):
            assert key not in rule
        for item in rule["items"]:
            assert item["review_status"] == "draft"
            assert all(v["status"] == "proposed" for v in item["accepted_variants"])
    for lex in tree.lexemes:
        assert lex["review_status"] == "draft"
    for scene in tree.scenes:
        assert scene["review_status"] == "draft"


LEARNER_FACING_RULE = ("title_l1", "explanation_l1")
LEARNER_FACING_ITEM = ("l1_meaning", "correct_form", "wrong_form")


def test_learner_facing_fields_contain_no_latin(tree):
    for rule in tree.rules:
        for f in LEARNER_FACING_RULE:
            assert not LATIN.search(rule.get(f) or ""), (rule["rule_id"], f)
        for item in rule["items"]:
            for f in LEARNER_FACING_ITEM:
                assert not LATIN.search(item.get(f) or ""), (item["item_id"], f)
            assert not any(LATIN.search(v["form"]) for v in item["accepted_variants"])
        for idea in rule["concept_key"]["ideas"]:
            assert not any(LATIN.search(term) for term in idea), rule["rule_id"]
    for lex in tree.lexemes:
        assert not LATIN.search(lex["hindi_gloss"] + (lex.get("false_friend_note_hi") or ""))
    for scene in tree.scenes:
        assert not LATIN.search(scene["title_hi"] + scene["setup_hi"])


def test_latin_text_is_kept_for_rewrite_not_dropped(tree):
    # Legacy explanations mix "Hindi"/"Telugu" in Latin script. They must not reach learner-facing fields, but
    # they must not vanish either: the original stays in `needs_rewrite` (and in the provenance record).
    hi_te_001 = next(r for r in tree.rules if r["rule_id"] == "HI-TE-001")
    assert hi_te_001["explanation_l1"] is None
    assert "Telugu" in hi_te_001["needs_rewrite"]["explanation_l1"]


def test_rejected_legacy_patterns_are_preserved_with_reasons(tree):
    item = next(i for r in tree.rules for i in r["items"] if i["item_id"] == "HI-TE-012-a")
    rejected = {p["pattern"]: p["reasons"] for p in item["rejected_patterns"]}
    assert "అమ్మను" in rejected and "not_anchored" in rejected["అమ్మను"]
    assert "అమ్మను" not in item["accept_patterns"]


def test_known_data_quality_issues_are_flagged(report):
    codes = {(rid, i.code) for rid, issues in report.issues.items() for i in issues}
    assert ("HI-TE-010-a", "more_than_one_error") in codes          # DQ-04
    assert any(rid == "HI-TE-005-a" and code.startswith("pattern_") for rid, code in codes)  # DQ-06


def test_lexemes_flag_false_friends_and_cognates(tree):
    lex = {x["telugu"]: x for x in tree.lexemes}
    assert lex["అవసరం"]["false_friend"] and lex["అవసరం"]["false_friend_note_hi"]
    assert lex["పుస్తకం"]["cognate_of"] == "पुस्तक"
    assert all(len(x["provenance"]) >= 1 for x in tree.lexemes)


def test_conversion_is_reproducible(tmp_path):
    """Converting the source snapshots again gives byte-identical files to the recorded conversion.

    After this slice the YAML is the authored source and may be edited; the manifest pins what the one-time
    conversion produced, so later edits don't break this test but the conversion stays checkable."""
    convert.convert_all(tmp_path, root=ROOT)
    produced = {p.relative_to(tmp_path).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in tmp_path.rglob("*.yaml")}
    manifest = json.loads((CONTENT / "CONVERSION.json").read_text(encoding="utf-8"))
    assert produced == manifest["files"]


def test_committed_yaml_still_matches_the_conversion_until_reviewed():
    # True for this slice: nothing has been edited since conversion. Remove once reviewers start editing.
    manifest = json.loads((CONTENT / "CONVERSION.json").read_text(encoding="utf-8"))
    for rel, digest in manifest["files"].items():
        assert hashlib.sha256((CONTENT / rel).read_bytes()).hexdigest() == digest, rel


def test_data_source_register_matches_the_docs(tree):
    doc = (ROOT / "docs/research/data-source-register.md").read_text(encoding="utf-8")
    doc_ids = set(re.findall(r"^\| (DS-\d+) \|", doc, re.MULTILINE))
    assert {d["id"] for d in tree.data_sources} == doc_ids


# ---------------------------------------------------------------- the validator refuses what it must


def _one_rule(tree, rule_id="HI-TE-001"):
    return copy.deepcopy(next(r for r in tree.rules if r["rule_id"] == rule_id))


@pytest.mark.parametrize("field,value", [
    ("validity", "verified"),
    ("lifecycle", "active"),
    ("lifecycle", "verified"),
    ("teacher_approved", True),
    ("speaker_approvals", [{"lang": "te", "reviewer": "x", "date": "2026-10-31"}]),
    ("reviewers", ["x"]),
])
def test_content_files_cannot_claim_review_or_approval(tree, field, value):
    rule = _one_rule(tree)
    rule[field] = value
    errors = validate.validate_rule(rule).errors
    assert any(e.code == "approval_claim" for e in errors), errors


def test_items_cannot_claim_approval(tree):
    rule = _one_rule(tree)
    rule["items"][0]["review_status"] = "approved"
    assert any(e.code == "approval_claim" for e in validate.validate_rule(rule).errors)
    rule = _one_rule(tree)
    rule["items"][0]["accepted_variants"].append({"form": "నువ్వు రాగలవా", "register": "written",
                                                  "status": "approved", "provenance": []})
    assert any(e.code == "approval_claim" for e in validate.validate_rule(rule).errors)


def test_duplicates_are_errors(tree):
    t = copy.deepcopy(tree)
    t.rules.append(_one_rule(tree))
    assert any(e.code == "duplicate_rule" for e in validate.validate_tree(t).errors)
    rule = _one_rule(tree)
    rule["items"].append(copy.deepcopy(rule["items"][0]))
    assert any(e.code == "duplicate_item" for e in validate.validate_rule(rule).errors)


def test_item_ids_must_belong_to_their_rule_and_direction(tree):
    rule = _one_rule(tree)
    rule["items"][0]["item_id"] = "TE-HI-001-a"
    assert any(e.code == "item_not_in_rule" for e in validate.validate_rule(rule).errors)
    rule = _one_rule(tree)
    rule["items"][0]["item_id"] = "HI-TE-001"
    assert any(e.code == "bad_item_id" for e in validate.validate_rule(rule).errors)
    rule = _one_rule(tree)
    rule["direction"] = "TE->HI"
    assert any(e.code == "direction_mismatch" for e in validate.validate_rule(rule).errors)


def test_target_script_is_enforced_per_direction(tree):
    rule = _one_rule(tree)
    rule["items"][0]["correct_form"] = "क्या तुम आ रहे हो"  # Hindi where Telugu is required
    assert any(e.code == "wrong_script" for e in validate.validate_rule(rule).errors)
    te_hi = _one_rule(tree, "TE-HI-001")
    assert validate.validate_rule(te_hi).errors == []


def test_unicode_duplicates_of_accepted_forms_are_collapsed(tree):
    import unicodedata

    rule = _one_rule(tree)
    item = rule["items"][0]
    nfd = unicodedata.normalize("NFD", item["correct_form"]) + " "
    item["accepted_variants"].append({"form": nfd, "register": "written", "status": "proposed", "provenance": []})
    result = validate.validate_rule(rule)
    assert result.errors == []
    assert any(i.code == "duplicate_variant" for i in result.issues[item["item_id"]])


def test_learner_facing_latin_is_an_error_in_authored_content(tree):
    rule = _one_rule(tree)
    rule["title_l1"] = "Questions: -ā at the end"
    assert any(e.code == "latin_in_learner_text" for e in validate.validate_rule(rule).errors)


def test_tampered_or_missing_provenance_is_an_error(tree):
    rule = _one_rule(tree)
    rule["provenance"][0]["original"]["source"] = "edited after the fact"
    assert any(e.code == "provenance_hash_mismatch" for e in validate.validate_rule(rule).errors)
    rule = _one_rule(tree)
    rule["provenance"] = []
    assert any(e.code == "missing_provenance" for e in validate.validate_rule(rule).errors)
    rule = _one_rule(tree)
    del rule["items"][0]["provenance"][0]["commit"]
    assert any(e.code == "bad_provenance" for e in validate.validate_rule(rule).errors)


def test_authored_patterns_must_be_valid_and_anchored(tree):
    rule = _one_rule(tree)
    rule["items"][0]["accept_patterns"] = ["నువ్వు వస్తావా"]  # unanchored
    assert any(e.code == "pattern_invalid" for e in validate.validate_rule(rule).errors)
    rule = _one_rule(tree)
    rule["items"][0]["wrong_patterns"] = ["^(క్యా)+ నువ్వు వస్తావు$"]  # repeat of a group
    assert any(e.code == "pattern_invalid" for e in validate.validate_rule(rule).errors)
