"""Loads the units of a language pair, in learning order, and checks that the order makes sense."""
from __future__ import annotations
import json
from pathlib import Path
from .contracts import Item, LessonLine, Unit

DATA = Path(__file__).resolve().parent.parent / "data"


def load_units(pair: str = "hi-te") -> list[Unit]:
    units = [Unit.model_validate(json.loads(p.read_text(encoding="utf-8")))
             for p in sorted((DATA / pair).glob("L*.json"))]          # units only (not course.json)
    units += load_rules(pair)
    units.sort(key=lambda u: (u.level, u.unit_id))
    seen: set[str] = set()
    for u in units:                                   # every prerequisite must come earlier
        missing = [r for r in u.requires if r not in seen]
        if missing:
            raise ValueError(f"{u.unit_id} requires {missing}, which do not come before it")
        seen.add(u.unit_id)
    return units


def load_rules(pair: str = "hi-te") -> list:
    """The grammar rules (paper §6.2: the error bank) as level-3 units. Each rule item is a Hindi sentence, its
    accepted Telugu forms, and the planted Hindi-speaker mistake. The lesson shows each sentence pair with a
    Devanagari reading aid; the check is writing one of them in Telugu; Raju then plants the mistakes."""
    from .text import telugu_to_deva
    path = DATA / pair / "rules.json"
    if not path.exists():
        return []
    out = []
    for r in json.loads(path.read_text(encoding="utf-8"))["rules"]:
        items = [Item(item_id=it["item_id"], prompt=it["hindi"], accepted=it["accepted"], raju_wrong=it["planted_error"],
                      answer_script="telugu", closed=False, kind="sentence",
                      accept_regex=it.get("fix_regex", []), wrong_regex=it.get("wrong_regex", []))
                 for it in r["items"]]
        last = items[-1]
        check = last.model_copy(update={"item_id": last.item_id + "-check"})
        lesson = [LessonLine(hindi=it.prompt, telugu=it.accepted[0], note=f"पढ़ो: {telugu_to_deva(it.accepted[0]).replace('ॆ', 'े').replace('ॊ', 'ो')}")
                  for it in items]
        out.append(Unit(unit_id=r["rule_id"], level=3, title=r["title_hi"], tip=r["explain_hi"], lesson=lesson,
                        check=check, items=items, key_ideas=r.get("key_ideas", []), habit=r.get("l1_habit", ""),
                        status=r.get("status", "draft_unverified"), version=r.get("version", 1),
                        reviewer=r.get("reviewer"), source=r.get("source", "")))
    return out


def all_items(units: list[Unit]) -> dict[str, tuple[Unit, Item]]:
    out: dict[str, tuple[Unit, Item]] = {}
    for u in units:
        for it in [u.check, *u.items]:
            if it.item_id in out:
                raise ValueError(f"duplicate item id {it.item_id}")
            out[it.item_id] = (u, it)
    return out
