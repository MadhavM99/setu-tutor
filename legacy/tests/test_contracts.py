import json
from pathlib import Path
from setu.contracts import Unit

DATA = Path(__file__).resolve().parent.parent / "data" / "hi-te"


def test_every_unit_file_matches_the_contract():
    files = sorted(DATA.glob("L*.json"))
    assert files, "no unit files found"
    for f in files:
        u = Unit.model_validate(json.loads(f.read_text(encoding="utf-8")))
        assert u.unit_id == f.stem                       # file name = unit id
        assert u.lesson, "every unit starts with a lesson"
        for it in [u.check, *u.items]:
            assert it.raju_wrong not in it.accepted      # Raju's mistake must really be a mistake
            assert it.item_id.startswith(u.unit_id)


def test_new_units_are_unverified_until_reviewed():
    for f in DATA.glob("L*.json"):
        u = Unit.model_validate(json.loads(f.read_text(encoding="utf-8")))
        if u.reviewer is None:
            assert u.status == "draft_unverified"
