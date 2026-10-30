"""Import the authored content tree into Postgres (slice 1.4).

- Runs in one transaction under the `setu_content` role: all or nothing, never learner data or learning state.
- Refuses a tree with validation errors (including any claim of review or approval).
- Idempotent: each record carries the sha256 of its authored form; unchanged records add nothing.
- Immutable history: a changed rule or item becomes a new version that supersedes the previous one. The importer
  never supersedes a version that someone has moved past `draft` (under review, verified, active…): those changes
  go through the teacher console.
- Never activates anything: rules enter as `uncertain`/`draft`, items and words as `draft`, extra accepted
  forms as `proposed`. Validation issues are stored with each item version and block its approval.
"""
import dataclasses
import json

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from setu.domain import leveler

from . import patterns
from .schema import TARGET_SCRIPT, normalise_sentence, sha256_of
from .validate import ContentTree, Result, validate_tree

IMPORTER_VERSION = "importer-2"  # adds rule target skills and leveler labels (slice S1); part of every content hash


class ImportRefused(Exception):
    pass


@dataclasses.dataclass
class ImportResult:
    new_rule_versions: int = 0
    new_item_versions: int = 0
    new_variants: int = 0
    lexemes_written: int = 0
    scenes_written: int = 0
    data_sources_written: int = 0
    letters_written: int = 0
    aksharas_written: int = 0
    skills_written: int = 0
    unchanged: int = 0


def _tx(engine: Engine):
    return _ContentTx(engine.execution_options(isolation_level="READ COMMITTED"))


class _ContentTx:
    def __init__(self, engine):
        self._engine = engine

    def __enter__(self) -> Connection:
        self._ctx = self._engine.begin()
        c = self._ctx.__enter__()
        c.execute(text("SET LOCAL ROLE setu_content"))
        return c

    def __exit__(self, *exc):
        return self._ctx.__exit__(*exc)


def effective_role(engine: Engine) -> str:
    with _tx(engine) as c:
        return c.execute(text("SELECT current_user")).scalar_one()


def _j(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True)


def import_tree(engine: Engine, tree: ContentTree, *, report: Result | None = None) -> ImportResult:
    report = report or validate_tree(tree)
    if report.errors:
        raise ImportRefused(f"{len(report.errors)} validation errors, e.g. "
                            + "; ".join(f"{e.code}: {e.detail}" for e in report.errors[:5]))
    result = ImportResult()
    with _tx(engine) as c:
        for ds in tree.data_sources:
            _data_source(c, ds, result)
        _letters_and_script_skills(c, tree.letters_l0, result)
        _aksharas_and_skills(c, tree.aksharas, tree.letters_l0, result)
        for rule in tree.rules:
            _skill(c, result, rule_skill_id(rule), band=rule["band"], family="rule", target=rule["rule_id"],
                   modality="PR", direction=rule["direction"])
            _rule(c, rule, report, result)
        for order, lex in enumerate(tree.lexemes, start=1):
            _lexeme(c, lex, result, order)
        for scene in tree.scenes:
            _scene(c, scene, result)
    return result


# ---------------------------------------------------------------- data sources


def _data_source(c, ds, result):
    row = c.execute(text("SELECT name, use, licence, status, notes FROM data_source WHERE id = :i"),
                    {"i": ds["id"]}).first()
    values = {k: ds.get(k) for k in ("name", "use", "licence", "status", "notes")}
    if row is None:
        c.execute(text("INSERT INTO data_source (id, name, use, licence, status, notes) "
                       "VALUES (:id, :name, :use, :licence, :status, :notes)"), {"id": ds["id"], **values})
        result.data_sources_written += 1
    elif dict(row._mapping) != values:
        c.execute(text("UPDATE data_source SET name = :name, use = :use, licence = :licence, status = :status, "
                       "notes = :notes WHERE id = :id"), {"id": ds["id"], **values})
        result.data_sources_written += 1


# ---------------------------------------------------------------- rules and items


def _latest(c, table, key_col, key):
    return c.execute(
        text(f"SELECT id, version, content_hash, {'lifecycle' if table == 'rule_version' else 'review_status'} "
             f"AS state FROM {table} WHERE {key_col} = :k ORDER BY version DESC LIMIT 1"), {"k": key}).first()


def _last_imported_hash(c, table, key_col, key):
    return c.execute(text(f"SELECT content_hash FROM {table} WHERE {key_col} = :k AND content_hash IS NOT NULL "
                          f"ORDER BY version DESC LIMIT 1"), {"k": key}).scalar()


def rule_skill_id(rule) -> str:
    return f"{rule['band']}.rule.{rule['rule_id']}.PR"


def _rule_hash(rule):
    derived = {"importer": IMPORTER_VERSION, "target_skill_id": rule_skill_id(rule)}
    return sha256_of({**{k: v for k, v in rule.items() if k != "items"}, "_derived": derived})


def _rule(c, rule, report, result):
    rid = rule["rule_id"]
    existing = c.execute(text("SELECT direction, contrast_area FROM rule WHERE id = :r"), {"r": rid}).first()
    if existing is None:
        c.execute(text("INSERT INTO rule (id, direction, contrast_area) VALUES (:r, :d, :a)"),
                  {"r": rid, "d": rule["direction"], "a": rule["contrast_area"]})
    elif existing.direction != rule["direction"]:
        raise ImportRefused(f"{rid}: direction {rule['direction']} differs from the database ({existing.direction})")

    digest = _rule_hash(rule)
    latest = _latest(c, "rule_version", "rule_id", rid)
    if latest is not None and _last_imported_hash(c, "rule_version", "rule_id", rid) == digest:
        # Unchanged since its last import. If someone has since added a later version (e.g. moved it into review),
        # new item versions point at that newest version, which is the one reviewers see.
        rule_version_id = latest.id
        result.unchanged += 1
    else:
        if latest is not None and latest.state != "draft":
            raise ImportRefused(f"{rid}: version {latest.version} is '{latest.state}'; content changes to reviewed "
                                "rules go through the teacher console, not the importer")
        rule_issues = [i.as_dict() for i in report.issues.get(rid, [])]
        rule_version_id = c.execute(
            text("INSERT INTO rule_version (rule_id, version, title_hi, l1_explanation_hi, concept_key, band, "
                 "validity, learner_evidence, lifecycle, teacher_approved, sources, licence, supersedes_version, "
                 "change_note, provenance, validation_issues, content_hash, target_skill_id) VALUES (:r, :v, :t, :e, "
                 "CAST(:ck AS jsonb), :band, :validity, :evidence, 'draft', false, CAST(:src AS jsonb), :lic, :sup, "
                 ":note, CAST(:prov AS jsonb), CAST(:iss AS jsonb), :h, :skill) RETURNING id"),
            {"r": rid, "v": (latest.version + 1) if latest else 1, "t": rule.get("title_l1"),
             "e": rule.get("explanation_l1"), "ck": _j(rule.get("concept_key") or {}), "band": rule["band"],
             "validity": rule["validity"], "evidence": rule["learner_evidence"],
             "src": _j(rule.get("citations") or []), "lic": rule.get("licence"),
             "sup": latest.id if latest else None,
             "note": "imported from content/" if latest is None
                     else f"imported from content/ (supersedes v{latest.version})",
             "prov": _j(rule["provenance"]), "iss": _j(rule_issues), "h": digest,
             "skill": rule_skill_id(rule)}).scalar_one()
        result.new_rule_versions += 1

    for item in rule["items"]:
        _item(c, rid, rule_version_id, item, report, result, rule)


def _item_hash(item):
    return sha256_of({**item, "_derived": {"importer": IMPORTER_VERSION, "leveler": leveler.VERSION}})


def _item(c, rid, rule_version_id, item, report, result, rule):
    iid = item["item_id"]
    if c.execute(text("SELECT rule_id FROM item WHERE id = :i"), {"i": iid}).scalar() is None:
        c.execute(text("INSERT INTO item (id, rule_id) VALUES (:i, :r)"), {"i": iid, "r": rid})
    digest = _item_hash(item)
    if _last_imported_hash(c, "item_version", "item_id", iid) == digest:
        result.unchanged += 1
        return
    latest = _latest(c, "item_version", "item_id", iid)
    if latest is not None and latest.state != "draft":
        raise ImportRefused(f"{iid}: version {latest.version} is '{latest.state}'; content changes to reviewed "
                            "items go through the teacher console, not the importer")
    span = None
    if item.get("wrong_form"):
        span, _ = patterns.one_error_span(wrong=item["wrong_form"], correct=item["correct_form"])
    issues = [i.as_dict() for i in report.issues.get(iid, [])]
    lv = leveler.level(item["correct_form"], contrast_area=rule.get("contrast_area"),
                       script=TARGET_SCRIPT[rule["direction"]])
    item_version_id = c.execute(
        text("INSERT INTO item_version (item_id, version, rule_version_id, hindi_meaning, wrong_form, one_error_span, "
             "correct_form, wrong_patterns, accept_patterns, allowed_target_forms, pool, review_status, provenance, "
             "validation_issues, content_hash, band, band_reason, leveler_version) VALUES (:i, :v, :rv, :m, :w, :span, "
             ":c, :wp, :ap, :atf, :pool, 'draft', CAST(:prov AS jsonb), CAST(:iss AS jsonb), :h, :band, :breason, "
             ":lver) RETURNING id"),
        {"i": iid, "v": (latest.version + 1) if latest else 1, "rv": rule_version_id, "m": item.get("l1_meaning"),
         "w": item.get("wrong_form"), "span": span, "c": normalise_sentence(item["correct_form"]),
         "wp": item.get("wrong_patterns") or [], "ap": item.get("accept_patterns") or [],
         "atf": item.get("allowed_target_forms") or [], "pool": item["pool"], "prov": _j(item["provenance"]),
         "iss": _j(issues), "h": digest, "band": lv.band, "breason": lv.reason,
         "lver": lv.leveler_version}).scalar_one()
    result.new_item_versions += 1

    seen = {normalise_sentence(item["correct_form"])}
    for v in item.get("accepted_variants") or []:
        form = normalise_sentence(v["form"])
        if form in seen:  # duplicate after Unicode/whitespace normalisation: keep one
            continue
        seen.add(form)
        c.execute(text("INSERT INTO accepted_variant (item_version_id, form, register, region, status, approvals, "
                       "provenance) VALUES (:iv, :f, :reg, :region, 'proposed', '[]'::jsonb, CAST(:p AS jsonb))"),
                  {"iv": item_version_id, "f": form, "reg": v.get("register", "written"), "region": v.get("region"),
                   "p": _j(v.get("provenance") or [])})
        result.new_variants += 1


# ---------------------------------------------------------------- words and scenes


LEXEME_DERIVED = "lexeme-2"  # word group, ladder order and letters (slice S3); part of the word's hash


def word_letters(telugu: str) -> list[str]:
    """The letters a word is written with (signs, virama and ం/ః are not letters)."""
    from .aksharas import SIGNS, VIRAMA

    marks = {s for _, s, _, _ in SIGNS} | {VIRAMA}
    return list(dict.fromkeys(ch for ch in telugu if ch not in marks))


def word_skill_id(group: str, modality: str) -> str:
    return f"L2.word.{group}.{modality}"


def _lexeme(c, lex, result, order=None):
    group = (lex.get("dev_notes") or {}).get("unit") or "misc"
    derived = {"importer": LEXEME_DERIVED, "group": group, "order": order, "letters": word_letters(lex["telugu"])}
    digest = sha256_of({**lex, "_derived": derived})
    row = c.execute(text("SELECT content_hash, review_status FROM lexeme WHERE id = :i"), {"i": lex["id"]}).first()
    values = {"id": lex["id"], "telugu": lex["telugu"], "gloss": lex["hindi_gloss"], "pos": lex.get("pos"),
              "rank": lex.get("freq_rank"), "cog": lex.get("cognate_of"), "ff": bool(lex.get("false_friend")),
              "note": lex.get("false_friend_note_hi"), "src": lex.get("source_id"),
              "prov": _j(lex["provenance"]), "h": digest, "look": lex.get("looks_like_hi"), "grp": group,
              "ord": order, "letters": _j(derived["letters"])}
    for modality, requires in (("REC", ["L1.akshara.vowel_signs.REC"]), ("RCL", [word_skill_id(group, "REC")])):
        _skill(c, result, word_skill_id(group, modality), band="L2", family="word", target=group, modality=modality,
               direction="HI->TE",
               requires=[r for r in requires if c.execute(text("SELECT 1 FROM skill WHERE id = :s"), {"s": r}).first()])
    if row is None:
        c.execute(text("INSERT INTO lexeme (id, telugu, hindi_gloss, pos, freq_rank, cognate_of, false_friend, "
                       "false_friend_note_hi, source_id, review_status, provenance, content_hash, looks_like_hi, "
                       "word_group, ladder_order, letters) VALUES (:id, :telugu, :gloss, :pos, :rank, :cog, :ff, "
                       ":note, :src, 'draft', CAST(:prov AS jsonb), :h, :look, :grp, :ord, "
                       "CAST(:letters AS jsonb))"), values)
        result.lexemes_written += 1
    elif row.content_hash != digest:
        if row.review_status != "draft":
            raise ImportRefused(f"{lex['id']}: word is '{row.review_status}'; edit it in the teacher console")
        c.execute(text("UPDATE lexeme SET telugu = :telugu, hindi_gloss = :gloss, pos = :pos, freq_rank = :rank, "
                       "cognate_of = :cog, false_friend = :ff, false_friend_note_hi = :note, source_id = :src, "
                       "provenance = CAST(:prov AS jsonb), content_hash = :h, looks_like_hi = :look, "
                       "word_group = :grp, ladder_order = :ord, letters = CAST(:letters AS jsonb) WHERE id = :id"),
                  values)
        result.lexemes_written += 1
    else:
        result.unchanged += 1


def _scene(c, scene, result):
    digest = sha256_of(scene)
    row = c.execute(text("SELECT content_hash, review_status FROM scene WHERE id = :i"), {"i": scene["id"]}).first()
    values = {"id": scene["id"], "t": scene["title_hi"], "s": scene["setup_hi"], "prov": _j(scene["provenance"]),
              "h": digest}
    if row is None:
        c.execute(text("INSERT INTO scene (id, title_hi, setup_hi, review_status, provenance, content_hash) "
                       "VALUES (:id, :t, :s, 'draft', CAST(:prov AS jsonb), :h)"), values)
        result.scenes_written += 1
    elif row.content_hash != digest:
        if row.review_status != "draft":
            raise ImportRefused(f"{scene['id']}: scene is '{row.review_status}'; edit it in the teacher console")
        c.execute(text("UPDATE scene SET title_hi = :t, setup_hi = :s, provenance = CAST(:prov AS jsonb), "
                       "content_hash = :h WHERE id = :id"), values)
        result.scenes_written += 1
    else:
        result.unchanged += 1


# ---------------------------------------------------------------- L0 letters and the skill graph (slice S1)

L0_MODALITIES = ("REC", "RCL")


def script_skill_id(group: str, modality: str) -> str:
    return f"L0.script.{group}.{modality}"


def _skill(c, result, skill_id, *, band, family, target, modality, direction, requires=()):
    if c.execute(text("SELECT 1 FROM skill WHERE id = :s"), {"s": skill_id}).first() is None:
        c.execute(text("INSERT INTO skill (id, band, family, target, modality, direction) VALUES "
                       "(:s, :b, :f, :t, :m, :d)"),
                  {"s": skill_id, "b": band, "f": family, "t": target, "m": modality, "d": direction})
        result.skills_written += 1
    for req in requires:
        c.execute(text("INSERT INTO skill_prereq (skill_id, requires_id) VALUES (:s, :r) ON CONFLICT DO NOTHING"),
                  {"s": skill_id, "r": req})


def _letters_and_script_skills(c, letters, result):
    groups = list(dict.fromkeys(letter["group"] for letter in sorted(letters, key=lambda x: x["varnamala_order"])))
    for i, group in enumerate(groups):
        rec, rcl = script_skill_id(group, "REC"), script_skill_id(group, "RCL")
        previous = [script_skill_id(groups[i - 1], "REC")] if i else []
        _skill(c, result, rec, band="L0", family="script", target=group, modality="REC", direction="HI->TE",
               requires=previous)
        _skill(c, result, rcl, band="L0", family="script", target=group, modality="RCL", direction="HI->TE",
               requires=[rec])
    for letter in letters:
        digest = sha256_of(letter)
        row = c.execute(text("SELECT content_hash, review_status FROM letter WHERE id = :i"),
                        {"i": letter["id"]}).first()
        values = {"id": letter["id"], "te": letter["telugu"], "dv": letter["devanagari"],
                  "label": letter["twin_label_hi"], "kind": letter["kind"], "grp": letter["group"],
                  "grp_hi": letter["group_hi"], "ord": letter["varnamala_order"], "new": letter["new_for_hindi"],
                  "note": letter.get("note_hi"), "prov": _j(letter["provenance"]), "h": digest}
        if row is None:
            c.execute(text("INSERT INTO letter (id, telugu, devanagari, twin_label_hi, kind, letter_group, group_hi, "
                           "varnamala_order, new_for_hindi, note_hi, review_status, provenance, content_hash) VALUES "
                           "(:id, :te, :dv, :label, :kind, :grp, :grp_hi, :ord, :new, :note, 'draft', "
                           "CAST(:prov AS jsonb), :h)"), values)
            result.letters_written += 1
        elif row.content_hash != digest:
            if row.review_status != "draft":
                raise ImportRefused(f"{letter['id']}: letter is '{row.review_status}'; edit it in the teacher console")
            c.execute(text("UPDATE letter SET telugu = :te, devanagari = :dv, twin_label_hi = :label, kind = :kind, "
                           "letter_group = :grp, group_hi = :grp_hi, varnamala_order = :ord, new_for_hindi = :new, "
                           "note_hi = :note, provenance = CAST(:prov AS jsonb), content_hash = :h WHERE id = :id"),
                      values)
            result.letters_written += 1
        else:
            result.unchanged += 1


# ---------------------------------------------------------------- L1 aksharas (slice S2)

# family -> families whose recognition it needs (beyond every L0 row's recognition)
L1_FAMILIES = {"vowel_signs": (), "nasal_visarga": ("vowel_signs",), "doubles": ("vowel_signs",),
               "conjuncts": ("doubles",)}


def akshara_skill_id(family: str, modality: str) -> str:
    return f"L1.akshara.{family}.{modality}"


def _aksharas_and_skills(c, aksharas, letters, result):
    if not aksharas:
        return
    l0_rows = list(dict.fromkeys(x["group"] for x in sorted(letters, key=lambda x: x["varnamala_order"])))
    for family, needs in L1_FAMILIES.items():
        rec = akshara_skill_id(family, "REC")
        requires = [script_skill_id(g, "REC") for g in l0_rows] + [akshara_skill_id(n, "REC") for n in needs]
        _skill(c, result, rec, band="L1", family="akshara", target=family, modality="REC", direction="HI->TE",
               requires=requires)
        _skill(c, result, akshara_skill_id(family, "RCL"), band="L1", family="akshara", target=family,
               modality="RCL", direction="HI->TE", requires=[rec])
    for unit in aksharas:
        digest = sha256_of(unit)
        row = c.execute(text("SELECT content_hash, review_status FROM akshara WHERE id = :i"), {"i": unit["id"]}).first()
        values = {"id": unit["id"], "te": unit["telugu"], "dv": unit["devanagari"], "label": unit["twin_label_hi"],
                  "kind": unit["kind"], "fam": unit["family"], "grp": unit["group"], "grp_hi": unit["group_hi"],
                  "letters": _j(unit["letters"]), "ord": unit["order"], "note": unit.get("note_hi"),
                  "prov": _j(unit["provenance"]), "h": digest}
        if row is None:
            c.execute(text("INSERT INTO akshara (id, telugu, devanagari, twin_label_hi, kind, family, akshara_group, "
                           "group_hi, letters, unit_order, note_hi, review_status, provenance, content_hash) VALUES "
                           "(:id, :te, :dv, :label, :kind, :fam, :grp, :grp_hi, CAST(:letters AS jsonb), :ord, :note, "
                           "'draft', CAST(:prov AS jsonb), :h)"), values)
            result.aksharas_written += 1
        elif row.content_hash != digest:
            if row.review_status != "draft":
                raise ImportRefused(f"{unit['id']}: akshara is '{row.review_status}'; edit it in the teacher console")
            c.execute(text("UPDATE akshara SET telugu = :te, devanagari = :dv, twin_label_hi = :label, kind = :kind, "
                           "family = :fam, akshara_group = :grp, group_hi = :grp_hi, letters = CAST(:letters AS jsonb), "
                           "unit_order = :ord, note_hi = :note, provenance = CAST(:prov AS jsonb), content_hash = :h "
                           "WHERE id = :id"), values)
            result.aksharas_written += 1
        else:
            result.unchanged += 1
