"""One-time conversion of the two source repositories into the authored YAML tree (data-model.md §6, E-06).

Sources:
- setu-tutor at baseline 7b84c7e: data/hi-te (now kept unchanged under legacy/data/hi-te);
- LMA---Reverse-learning-Tutor at c11a63a: data/ (vendored verbatim under content/sources/lma-c11a63a).

Nothing is lost: every rule, word, scene and unit keeps a provenance record with repo, commit, original path, JSON
pointer, the sha256 of the raw record and the raw record itself. Nothing is activated: every rule is
`uncertain`/`draft`, every item, word and scene `draft`, every extra accepted form a `proposed` variant.
Learner-facing fields receive only text without Latin script; anything else is kept in `needs_rewrite`.
Legacy answer patterns that fail validation are kept in `rejected_patterns` with the reasons.
"""
import hashlib
import json
import re
import unicodedata
from pathlib import Path

import yaml

from . import patterns
from .schema import L1_SCRIPT, LATIN, SCRIPT_RE, TARGET_SCRIPT, normalise_sentence, sha256_of

SETU = {"repo": "setu-tutor", "remote": None, "commit": "7b84c7e668230dc6a35b57c4d1ef984c45488c5e",
        "base": "data/hi-te", "local": "legacy/data/hi-te"}
LMA = {"repo": "LMA---Reverse-learning-Tutor",
       "remote": "https://github.com/FavianaNoronha/LMA---Reverse-learning-Tutor.git",
       "commit": "c11a63a30f7c20311f3fb1e1318427a8cf63b304", "base": "data",
       "local": "content/sources/lma-c11a63a"}

BAND_REASON = ("imported default: contrast rules sit at L4 of the learning ladder (learning-ladder.md §1); not yet "
               "set by two native speakers or by the leveler")
LICENCE = "team-owned draft content (DS-20); Telugu and Hindi unreviewed"
HEADER = ("# Converted by `python -m setu.content convert` from the source snapshots listed under provenance.\n"
          "# After this one-time conversion this file is the authored source: edit it to change content, and the\n"
          "# importer will add a new version. Review and approval happen only in the teacher console.\n")


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _prov(src, rel_path, pointer, record, description):
    return {"repo": src["repo"], "remote": src["remote"], "commit": src["commit"],
            "path": f"{src['base']}/{rel_path}", "pointer": pointer, "record_sha256": sha256_of(record),
            "description": description, "original": record}


def _ref(src, rel_path, pointer, record):
    """A provenance pointer for a sub-record whose raw form is already embedded in its parent's provenance."""
    return {"repo": src["repo"], "remote": src["remote"], "commit": src["commit"],
            "path": f"{src['base']}/{rel_path}", "pointer": pointer, "record_sha256": sha256_of(record),
            "description": "sub-record; the raw record is embedded in the parent's provenance"}


def _learner_text(value, script, field, needs_rewrite):
    """Keep `value` for a learner-facing field only if it has no Latin and is written in `script`."""
    if value is None:
        return None
    value = unicodedata.normalize("NFC", value)
    if LATIN.search(value) or not SCRIPT_RE[script].search(value):
        needs_rewrite[field] = value
        return None
    return value


def _strip_emoji(s: str) -> str:
    kept = [ch for ch in s if unicodedata.category(ch) != "So" and ch not in "️‍"]
    return " ".join("".join(kept).split())


def _split_patterns(item, direction, kind, legacy):
    """Sort legacy patterns into ones that pass validation (kept) and ones that do not (kept with reasons)."""
    script = TARGET_SCRIPT[direction]
    kept, rejected = [], []
    for p in legacy:
        reasons = [i.code for i in patterns.check_pattern(p, script=script)]
        if not reasons:
            sem = patterns.check_item_patterns(
                correct=item["correct_form"], accepted=[item["correct_form"]] + [v["form"] for v in item["variants"]],
                wrong=item["wrong_form"], accept_patterns=[p] if kind == "accept" else [],
                wrong_patterns=[p] if kind == "wrong" else [], script=script)
            reasons = sorted({i.code for i in sem})
        if reasons:
            rejected.append({"pattern": p, "kind": kind, "reasons": reasons})
        else:
            kept.append(p)
    return kept, rejected


# ---------------------------------------------------------------- rules


def _rule_sources(root: Path):
    setu_rules = _load_json(root / SETU["local"] / "rules.json")["rules"]
    lma_hi = _load_json(root / LMA["local"] / "l1-hi_l2-te/rules.json")
    lma_te = _load_json(root / LMA["local"] / "l1-te_l2-hi/rules.json")
    by_rule: dict[str, list] = {}
    for i, r in enumerate(lma_hi):
        by_rule.setdefault(r["rule_id"], []).append((LMA, "l1-hi_l2-te/rules.json", f"/{i}", r))
    for i, r in enumerate(lma_te):
        by_rule.setdefault(r["rule_id"], []).append((LMA, "l1-te_l2-hi/rules.json", f"/{i}", r))
    for i, r in enumerate(setu_rules):
        by_rule.setdefault(r["rule_id"], []).append((SETU, "rules.json", f"/rules/{i}", r))
    return by_rule


def _book_examples(root: Path):
    out = {}
    path = root / LMA["local"] / "l1-hi_l2-te/book_examples.jsonl"
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        if line.strip():
            ex = json.loads(line)
            for rid in ex.get("rules", []):
                out.setdefault(rid, []).append((n, ex))
    return out


def _merge_field(records, getter):
    values = []
    for src, *_rest, rec in records:
        v = getter(rec)
        if v is not None and v not in values:
            values.append(v)
    return values


def convert_rule(rule_id, records, book):
    direction = "HI->TE" if rule_id.startswith("HI-TE") else "TE->HI"
    l1 = L1_SCRIPT[direction]
    needs_rewrite: dict = {}
    by_repo = {src["repo"]: rec for src, _p, _ptr, rec in records}
    setu_rec = by_repo.get(SETU["repo"])
    first = records[0][3]

    sources_text = " ".join(rec.get("source", "") for *_x, rec in records)
    evidence_values = _merge_field(records, lambda r: r.get("evidence"))
    evidence = evidence_values[0] if evidence_values else "model_predicted"
    if evidence == "model_predicted" and "contrast confirmed in Krishnamurti" in sources_text:
        evidence = "predicted"  # content-and-error-bank.md §6 / data-model.md §6 migration rule

    ideas, dropped = [], []
    for group in (setu_rec or {}).get("key_ideas", []):
        keep = [unicodedata.normalize("NFC", t) for t in group if not LATIN.search(t)]
        dropped += [t for t in group if LATIN.search(t)]
        if keep:
            ideas.append(keep)

    conflicts = {}
    shared = set.intersection(*(set(rec) for *_x, rec in records)) - {"items", "source"}
    for key in sorted(shared):
        vals = _merge_field(records, lambda r, k=key: json.dumps(r.get(k), ensure_ascii=False, sort_keys=True))
        if len(vals) > 1:
            conflicts[key] = [json.loads(v) for v in vals]

    rule = {
        "schema": "setu.rule/1",
        "rule_id": rule_id,
        "direction": direction,
        "contrast_area": first.get("category"),
        "band": "L4",
        "band_reason": BAND_REASON,
        "title_l1": _learner_text((setu_rec or {}).get("title_hi"), l1, "title_l1", needs_rewrite),
        "explanation_l1": _learner_text((setu_rec or {}).get("explain_hi"), l1, "explanation_l1", needs_rewrite),
        "concept_key": {"ideas": ideas},
        "validity": "uncertain",
        "learner_evidence": evidence,
        "lifecycle": "draft",
        "licence": LICENCE,
        "citations": [
            {"data_source": "DS-02", "reference": ex.get("src"), "telugu_draft": ex.get("telugu_draft"),
             "note": ex.get("note"),
             "provenance": _prov(LMA, "l1-hi_l2-te/book_examples.jsonl", f"/line/{n}", ex,
                                 "Krishnamurti & Gwynn 1985 example recorded by the team; Telugu is a draft")}
            for n, ex in book.get(rule_id, [])
        ],
        "needs_rewrite": needs_rewrite,
        "dev_notes": {
            "name_en": first.get("name"),
            "title_en": first.get("title"),
            "l1_habit_en": first.get("l1_habit"),
            "transfer": first.get("transfer"),
            "source_status": _merge_field(records, lambda r: r.get("status")) or ["draft_unverified (default)"],
            "source_versions": _merge_field(records, lambda r: r.get("version")),
            "dropped_latin_concept_terms": dropped,
            "merge_conflicts": conflicts,
        },
        "provenance": [_prov(src, path, ptr, rec, rec.get("source", "")) for src, path, ptr, rec in records],
        "items": [],
    }

    # items: union by id in source order, merging the same item across repositories
    item_records: dict[str, list] = {}
    for src, path, ptr, rec in records:
        for j, it in enumerate(rec.get("items", [])):
            item_records.setdefault(it["item_id"], []).append((src, path, f"{ptr}/items/{j}", it))
    for iid, recs in item_records.items():
        rule["items"].append(convert_item(iid, recs, direction))
    return rule


def convert_item(iid, recs, direction):
    l1 = L1_SCRIPT[direction]
    needs_rewrite: dict = {}
    it = recs[0][3]
    meaning_key = "hindi" if direction == "HI->TE" else "telugu"
    accepted = []
    for _src, _p, _ptr, rec in recs:
        for a in rec.get("accepted", []):
            a = normalise_sentence(a)
            if a not in accepted:
                accepted.append(a)
    conflicts = {}
    for key in sorted(set.intersection(*(set(r[3]) for r in recs))):
        vals = {json.dumps(r[3].get(key), ensure_ascii=False, sort_keys=True) for r in recs}
        if len(vals) > 1:
            conflicts[key] = sorted(vals)
    item = {
        "item_id": iid,
        "l1_meaning": _learner_text(it.get(meaning_key), l1, "l1_meaning", needs_rewrite),
        "correct_form": accepted[0],
        "wrong_form": normalise_sentence(it["planted_error"]) if it.get("planted_error") else None,
        "variants": [{"form": a} for a in accepted[1:]],
    }
    accept, rej_a = _split_patterns(item, direction, "accept",
                                    [p for r in recs for p in r[3].get("fix_regex", [])])
    wrong, rej_w = _split_patterns(item, direction, "wrong",
                                   [p for r in recs for p in r[3].get("wrong_regex", [])])
    dedupe = lambda xs: list(dict.fromkeys(xs))
    return {
        "item_id": iid,
        "l1_meaning": item["l1_meaning"],
        "correct_form": item["correct_form"],
        "wrong_form": item["wrong_form"],
        "accepted_variants": [
            {"form": a, "register": "written", "status": "proposed",
             "provenance": [_ref(src, path, f"{ptr}/accepted/{k}", raw)
                            for src, path, ptr, rec in recs
                            for k, raw in enumerate(rec.get("accepted", [])) if normalise_sentence(raw) == a]}
            for a in accepted[1:]
        ],
        "accept_patterns": dedupe(accept),
        "wrong_patterns": dedupe(wrong),
        "rejected_patterns": [dict(t) for t in {json.dumps(x, ensure_ascii=False, sort_keys=True): x
                                                for x in rej_a + rej_w}.values()],
        "allowed_target_forms": dedupe([f for r in recs for f in r[3].get("allowed_new", [])]),
        "pool": "practice",
        "review_status": "draft",
        "needs_rewrite": needs_rewrite,
        "dev_notes": {"english_meaning": it.get("english"), "merge_conflicts": conflicts},
        "provenance": [_ref(src, path, ptr, rec) for src, path, ptr, rec in recs],
    }


# ---------------------------------------------------------------- words, scenes, units


def convert_lexicon(root: Path):
    lexemes: dict[str, dict] = {}
    for path in sorted((root / SETU["local"]).glob("L1-*.json")):
        unit = _load_json(path)
        false_friend_unit = unit["unit_id"] == "L1-06"
        cognate_unit = unit["unit_id"] == "L1-05"
        for k, line in enumerate(unit["lesson"]):
            telugu = unicodedata.normalize("NFC", line["telugu"])
            hindi = unicodedata.normalize("NFC", line["hindi"])
            gloss, note = hindi, None
            m = re.match(r"^(.*?)\s*\((.*)\)\s*$", hindi)
            if false_friend_unit and m:
                gloss, note = m.group(1), m.group(2)
            lid = f"te:{telugu}"
            prov = _prov(SETU, path.name, f"/lesson/{k}", line, f"{unit['unit_id']} {unit.get('title', '')}")
            if lid in lexemes:
                lexemes[lid]["provenance"].append(prov)
                continue
            lexemes[lid] = {
                "id": lid,
                "telugu": telugu,
                "hindi_gloss": gloss,
                "pos": None,
                "freq_rank": None,
                "cognate_of": hindi if cognate_unit else None,
                "false_friend": bool(false_friend_unit),
                "false_friend_note_hi": note,
                "source_id": "DS-20",
                "review_status": "draft",
                "dev_notes": {"lesson_note": line.get("note") or None, "unit": unit["unit_id"]},
                "provenance": [prov],
            }
    return list(lexemes.values())


def convert_scenes(root: Path):
    course = _load_json(root / SETU["local"] / "course.json")
    scenes = []
    n = 0
    for ci, chapter in enumerate(course["chapters"]):
        for mi, module in enumerate(chapter["modules"]):
            if "scene" not in module:
                continue
            n += 1
            scenes.append({
                "id": f"hi-te-scene-{n:02d}",
                "title_hi": _strip_emoji(module["title"]),
                "setup_hi": unicodedata.normalize("NFC", module["scene"]),
                "review_status": "draft",
                "dev_notes": {"legacy_rule_units": module.get("units", [])},
                "provenance": [_prov(SETU, "course.json", f"/chapters/{ci}/modules/{mi}", module,
                                     f"course module '{module['title']}'")],
            })
    return scenes


def convert_units(root: Path, prefix: str, deferred_to: str):
    units = []
    for path in sorted((root / SETU["local"]).glob(f"{prefix}-*.json")):
        unit = _load_json(path)
        units.append({
            "unit_id": unit["unit_id"],
            "review_status": "draft",
            "imported_to_database": False,
            "deferred_to": deferred_to,
            "note": "Kept verbatim (letters, mnemonics, pictures, drill items) for review; nothing here reaches "
                    "learners. Mnemonics and shape notes become memory-aid drafts only via the grounding "
                    "validator and teacher review (ADR-0005).",
            "provenance": [_prov(SETU, path.name, "", unit, unit.get("source", ""))],
        })
    return units


def convert_data_sources(root: Path):
    doc = (root / "docs/research/data-source-register.md").read_text(encoding="utf-8")
    out = []
    for line in doc.splitlines():
        m = re.match(r"^\| (DS-\d+) \|", line)
        if not m:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        status = next((s for s in ("verified", "to-check", "n/a") if cells[5].startswith(s)), "to-check")
        out.append({"id": cells[0], "name": cells[1], "use": cells[2], "licence": cells[4], "status": status,
                    "notes": f"{cells[3]} · {cells[6]}"})
    return out


# ---------------------------------------------------------------- writing


def _dump(obj) -> str:
    return HEADER + yaml.safe_dump(obj, allow_unicode=True, sort_keys=False, width=110)


def convert_all(out_dir: Path, *, root: Path) -> dict:
    out_dir, root = Path(out_dir), Path(root)
    files: dict[str, str] = {}

    def write(rel, obj):
        path = out_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        text = _dump(obj)
        path.write_text(text, encoding="utf-8")
        files[rel] = hashlib.sha256(text.encode()).hexdigest()

    book = _book_examples(root)
    for rule_id, records in sorted(_rule_sources(root).items()):
        folder = "hi-te" if rule_id.startswith("HI-TE") else "te-hi"
        write(f"{folder}/rules/{rule_id}.yaml", convert_rule(rule_id, records, book))
    write("hi-te/lexicon.yaml", convert_lexicon(root))
    write("hi-te/scenes.yaml", convert_scenes(root))
    for unit in convert_units(root, "L0", "slice 3 (S1 script orientation)"):
        write(f"hi-te/letters/{unit['unit_id']}.yaml", unit)
    for unit in convert_units(root, "L1", "words: lexicon.yaml now; drill items: slice 3 (S3)"):
        write(f"hi-te/word_units/{unit['unit_id']}.yaml", unit)
    write("data_sources.yaml", convert_data_sources(root))
    return files


def write_manifest(content_dir: Path, files: dict, root: Path):
    manifest = {
        "note": "sha256 of each file as produced by the one-time conversion; tests re-run the conversion and "
                "compare against this.",
        "sources": [{k: SETU[k] for k in ("repo", "commit", "base")} | {"read_from": SETU["local"]},
                    {k: LMA[k] for k in ("repo", "remote", "commit", "base")} | {"read_from": LMA["local"]}],
        "files": dict(sorted(files.items())),
    }
    (Path(content_dir) / "CONVERSION.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                                                       encoding="utf-8")
