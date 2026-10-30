"""Validate the authored content tree (content-and-error-bank.md §2, §6; data-model.md).

Errors block import. Issues import with the record as a draft (stored in `validation_issues`) and block approval.
Content files may never claim review or approval: that happens only in the teacher console.
"""
import dataclasses
from pathlib import Path

import yaml

from . import patterns
from .schema import (
    APPROVAL_KEYS,
    BANDS,
    DIRECTION_OF_PREFIX,
    EVIDENCE,
    IMPORTABLE,
    ITEM_ID,
    L1_SCRIPT,
    LATIN,
    OTHER_SCRIPT,
    RULE_ID,
    SCRIPT_RE,
    TARGET_SCRIPT,
    Issue,
    normalise_sentence,
    sha256_of,
)

RULE_KEYS = {"schema", "rule_id", "direction", "contrast_area", "band", "band_reason", "title_l1", "explanation_l1",
             "concept_key", "validity", "learner_evidence", "lifecycle", "licence", "citations", "needs_rewrite",
             "dev_notes", "provenance", "items"}
ITEM_KEYS = {"item_id", "l1_meaning", "correct_form", "wrong_form", "accepted_variants", "accept_patterns",
             "wrong_patterns", "rejected_patterns", "allowed_target_forms", "pool", "review_status", "needs_rewrite",
             "dev_notes", "provenance"}
VARIANT_KEYS = {"form", "register", "region", "status", "provenance"}
PROVENANCE_KEYS = {"repo", "remote", "commit", "path", "pointer", "record_sha256", "description", "original"}
POOLS = ("practice", "test_heldout", "diagnostic")
DATA_SOURCE_STATUS = ("verified", "to-check", "n/a")


@dataclasses.dataclass
class ContentTree:
    rules: list
    lexemes: list
    scenes: list
    data_sources: list
    letters: list
    word_units: list
    root: Path | None = None


@dataclasses.dataclass
class Result:
    errors: list
    issues: dict

    def add(self, record_id, issue: Issue):
        if issue.error:
            issue.detail = f"{record_id}: {issue.detail}" if issue.detail else record_id
            self.errors.append(issue)
        else:
            self.issues.setdefault(record_id, []).append(issue)

    def merge(self, other: "Result"):
        self.errors.extend(other.errors)
        for k, v in other.issues.items():
            self.issues.setdefault(k, []).extend(v)


def _yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_tree(root: Path) -> ContentTree:
    root = Path(root)
    rules = [_yaml(p) for d in ("hi-te/rules", "te-hi/rules") for p in sorted((root / d).glob("*.yaml"))]
    return ContentTree(
        rules=rules,
        lexemes=_yaml(root / "hi-te/lexicon.yaml") or [],
        scenes=_yaml(root / "hi-te/scenes.yaml") or [],
        data_sources=_yaml(root / "data_sources.yaml") or [],
        letters=[_yaml(p) for p in sorted((root / "hi-te/letters").glob("*.yaml"))],
        word_units=[_yaml(p) for p in sorted((root / "hi-te/word_units").glob("*.yaml"))],
        root=root,
    )


# ---------------------------------------------------------------- helpers


def _err(code, detail="", field=None):
    return Issue(code, detail, field=field, error=True)


def _check_l1_text(res, rid, field, value, direction):
    if value is None:
        return
    if not isinstance(value, str):
        res.add(rid, _err("bad_type", f"{field} must be text", field))
    elif LATIN.search(value):
        res.add(rid, _err("latin_in_learner_text", field, field))
    elif not SCRIPT_RE[L1_SCRIPT[direction]].search(value):
        res.add(rid, _err("wrong_script", f"{field} must be written in {L1_SCRIPT[direction]}", field))


def _check_target_text(res, rid, field, value, direction):
    script = TARGET_SCRIPT[direction]
    if not isinstance(value, str) or not value.strip():
        res.add(rid, _err("missing_field", field, field))
        return
    if LATIN.search(value) or OTHER_SCRIPT[script].search(value) or not SCRIPT_RE[script].search(value):
        res.add(rid, _err("wrong_script", f"{field} must be {script} only", field))


def _check_provenance(res, rid, prov):
    if not isinstance(prov, list) or not prov:
        res.add(rid, _err("missing_provenance"))
        return
    for p in prov:
        missing = {"repo", "commit", "path", "pointer", "record_sha256", "description"} - set(p)
        if missing:
            res.add(rid, _err("bad_provenance", f"missing {sorted(missing)}"))
        unknown = set(p) - PROVENANCE_KEYS
        if unknown:
            res.add(rid, _err("unknown_field", f"provenance {sorted(unknown)}"))
        if "original" in p and sha256_of(p["original"]) != p.get("record_sha256"):
            res.add(rid, _err("provenance_hash_mismatch", p.get("pointer", "")))


def _approval_claims(res, rid, record, *, status_field=None, allowed=()):
    for key in APPROVAL_KEYS:
        if key in record:
            res.add(rid, _err("approval_claim", f"'{key}' is set only by the teacher console"))
    if status_field and record.get(status_field) not in allowed:
        res.add(rid, _err("approval_claim", f"{status_field} must be one of {allowed} in content files"))


# ---------------------------------------------------------------- rules


def validate_rule(rule: dict) -> Result:
    res = Result([], {})
    rid = rule.get("rule_id", "?")
    for key in set(rule) - RULE_KEYS - set(APPROVAL_KEYS):
        res.add(rid, _err("unknown_field", key))
    _approval_claims(res, rid, rule)
    if rule.get("validity") not in IMPORTABLE["validity"]:
        res.add(rid, _err("approval_claim", "validity must be 'uncertain' (or 'rejected') in content files"))
    if rule.get("lifecycle") not in IMPORTABLE["lifecycle"]:
        res.add(rid, _err("approval_claim", "lifecycle must be 'draft' in content files"))
    if not isinstance(rid, str) or not RULE_ID.match(rid):
        res.add(rid, _err("bad_rule_id"))
        return res
    direction = rule.get("direction")
    if DIRECTION_OF_PREFIX.get(rid[:5]) != direction:
        res.add(rid, _err("direction_mismatch", f"{rid} is not a {direction} rule"))
        return res
    if rule.get("band") not in BANDS:
        res.add(rid, _err("bad_band"))
    if rule.get("learner_evidence") not in EVIDENCE:
        res.add(rid, _err("bad_evidence"))
    if not rule.get("contrast_area"):
        res.add(rid, _err("missing_field", "contrast_area"))
    for field in ("title_l1", "explanation_l1"):
        _check_l1_text(res, rid, field, rule.get(field), direction)
        if rule.get(field) is None:
            res.add(rid, Issue("missing_l1_text", field, field))
    concept = rule.get("concept_key") or {}
    for part in ("ideas", "relations"):
        for group in concept.get(part, []):
            for term in group:
                if LATIN.search(term):
                    res.add(rid, _err("latin_in_learner_text", f"concept_key {part} term {term!r}"))
    if concept.get("ideas") and not concept.get("relations"):
        # Without relation phrases the checker cannot tell an explanation from a keyword list (checker-1).
        res.add(rid, Issue("concept_key_without_relations"))
    for field in (rule.get("needs_rewrite") or {}):
        res.add(rid, Issue("needs_rewrite", field, field))
    _check_provenance(res, rid, rule.get("provenance"))

    seen_items = set()
    for item in rule.get("items") or []:
        iid = item.get("item_id", "?")
        if iid in seen_items:
            res.add(iid, _err("duplicate_item", iid))
            continue
        seen_items.add(iid)
        res.merge(_validate_item(item, rid, direction))
    if not seen_items:
        res.add(rid, Issue("no_items"))
    return res


def _validate_item(item, rid, direction) -> Result:
    res = Result([], {})
    iid = item.get("item_id", "?")
    for key in set(item) - ITEM_KEYS - set(APPROVAL_KEYS):
        res.add(iid, _err("unknown_field", key))
    if not isinstance(iid, str) or not ITEM_ID.match(iid):
        res.add(iid, _err("bad_item_id"))
        return res
    if iid[:9] != rid:
        res.add(iid, _err("item_not_in_rule", f"{iid} does not belong to {rid}"))
        return res
    _approval_claims(res, iid, item, status_field="review_status", allowed=IMPORTABLE["review_status"])
    if item.get("pool") not in POOLS:
        res.add(iid, _err("bad_pool"))
    _check_target_text(res, iid, "correct_form", item.get("correct_form"), direction)
    if item.get("wrong_form") is not None:
        _check_target_text(res, iid, "wrong_form", item.get("wrong_form"), direction)
    _check_l1_text(res, iid, "l1_meaning", item.get("l1_meaning"), direction)
    _check_provenance(res, iid, item.get("provenance"))
    if res.errors:
        return res

    correct = normalise_sentence(item["correct_form"])
    seen_forms = {correct}
    for v in item.get("accepted_variants") or []:
        for key in set(v) - VARIANT_KEYS - set(APPROVAL_KEYS):
            res.add(iid, _err("unknown_field", f"variant {key}"))
        _approval_claims(res, iid, v, status_field="status", allowed=IMPORTABLE["variant_status"])
        _check_target_text(res, iid, "accepted_variants.form", v.get("form"), direction)
        form = normalise_sentence(v.get("form") or "")
        if form in seen_forms:
            res.add(iid, Issue("duplicate_variant", form))
        seen_forms.add(form)

    script = TARGET_SCRIPT[direction]
    for kind in ("accept_patterns", "wrong_patterns"):
        for p in item.get(kind) or []:
            bad = patterns.check_pattern(p, script=script)
            if bad:
                res.add(iid, _err("pattern_invalid", f"{kind} {p!r}: {[i.code for i in bad]}"))
    if res.errors:
        return res
    for issue in patterns.check_item_patterns(
            correct=item["correct_form"], accepted=sorted(seen_forms), wrong=item.get("wrong_form"),
            accept_patterns=item.get("accept_patterns") or [], wrong_patterns=item.get("wrong_patterns") or [],
            script=script):
        res.add(iid, Issue("pattern_" + issue.code, issue.detail))
    for rej in item.get("rejected_patterns") or []:
        res.add(iid, Issue("pattern_rejected", f"{rej.get('kind')} {rej.get('pattern')!r}: {rej.get('reasons')}"))
    if item.get("wrong_form"):
        _, problem = patterns.one_error_span(wrong=item["wrong_form"], correct=item["correct_form"])
        if problem in ("more_than_one_error", "no_error"):
            res.add(iid, Issue(problem, f"{item['wrong_form']!r} vs {item['correct_form']!r}"))
    else:
        res.add(iid, Issue("no_planted_error"))
    for field in (item.get("needs_rewrite") or {}):
        res.add(iid, Issue("needs_rewrite", field, field))
    if item.get("l1_meaning") is None:
        res.add(iid, Issue("missing_l1_text", "l1_meaning"))
    return res


# ---------------------------------------------------------------- other records


def _validate_lexeme(lex) -> Result:
    res = Result([], {})
    lid = lex.get("id", "?")
    _approval_claims(res, lid, lex, status_field="review_status", allowed=IMPORTABLE["review_status"])
    if not str(lid).startswith("te:"):
        res.add(lid, _err("bad_lexeme_id"))
    _check_target_text(res, lid, "telugu", lex.get("telugu"), "HI->TE")
    for field in ("hindi_gloss", "false_friend_note_hi", "cognate_of"):
        _check_l1_text(res, lid, field, lex.get(field), "HI->TE")
    if not lex.get("hindi_gloss"):
        res.add(lid, _err("missing_field", "hindi_gloss"))
    if lex.get("false_friend") and not lex.get("false_friend_note_hi"):
        res.add(lid, _err("false_friend_without_note"))
    _check_provenance(res, lid, lex.get("provenance"))
    return res


def _validate_scene(scene) -> Result:
    res = Result([], {})
    sid = scene.get("id", "?")
    _approval_claims(res, sid, scene, status_field="review_status", allowed=IMPORTABLE["review_status"])
    for field in ("title_hi", "setup_hi"):
        if not scene.get(field):
            res.add(sid, _err("missing_field", field))
        _check_l1_text(res, sid, field, scene.get(field), "HI->TE")
    _check_provenance(res, sid, scene.get("provenance"))
    return res


def validate_tree(tree: ContentTree) -> Result:
    res = Result([], {})
    rule_ids, item_owner, sentences = set(), {}, {}
    for rule in tree.rules:
        rid = rule.get("rule_id")
        if rid in rule_ids:
            res.add(rid, _err("duplicate_rule", rid))
            continue
        rule_ids.add(rid)
        res.merge(validate_rule(rule))
        for item in rule.get("items") or []:
            iid = item.get("item_id")
            if iid in item_owner and item_owner[iid] != rid:
                res.add(iid, _err("duplicate_item", f"{iid} appears in {item_owner[iid]} and {rid}"))
            item_owner[iid] = rid
            key = normalise_sentence(item.get("correct_form") or "")
            if key in sentences and sentences[key] != iid:
                res.add(iid, Issue("duplicate_sentence", f"same correct form as {sentences[key]}"))
            sentences.setdefault(key, iid)

    lex_ids = set()
    for lex in tree.lexemes:
        if lex.get("id") in lex_ids:
            res.add(lex.get("id"), _err("duplicate_lexeme"))
        lex_ids.add(lex.get("id"))
        res.merge(_validate_lexeme(lex))
    scene_ids = set()
    for scene in tree.scenes:
        if scene.get("id") in scene_ids:
            res.add(scene.get("id"), _err("duplicate_scene"))
        scene_ids.add(scene.get("id"))
        res.merge(_validate_scene(scene))
    ds_ids = set()
    for ds in tree.data_sources:
        if ds.get("id") in ds_ids:
            res.add(ds.get("id"), _err("duplicate_data_source"))
        ds_ids.add(ds.get("id"))
        if ds.get("status") not in DATA_SOURCE_STATUS:
            res.add(ds.get("id"), _err("bad_status", str(ds.get("status"))))
    for unit in tree.letters + tree.word_units:
        uid = unit.get("unit_id", "?")
        _approval_claims(res, uid, unit, status_field="review_status", allowed=IMPORTABLE["review_status"])
        _check_provenance(res, uid, unit.get("provenance"))
    return res
