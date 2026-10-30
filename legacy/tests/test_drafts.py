"""The hook-drafting script: model drafts go to a separate review file, never into lessons."""
import importlib.util
from pathlib import Path
from setu.bank import load_units

spec = importlib.util.spec_from_file_location("draft_hooks", Path(__file__).resolve().parent.parent / "scripts" / "draft_hooks.py")
dh = importlib.util.module_from_spec(spec); spec.loader.exec_module(dh)


def test_drafts_are_marked_unverified_and_keep_errors():
    unit = next(u for u in load_units() if u.unit_id == "L0-07")
    calls = []
    def fake(prompt):
        calls.append(prompt)
        if len(calls) == 2:
            raise TimeoutError("slow")
        return {"shape": "s", "mnemonic": "m", "example": "కమలం = कमल", "picture": "🪷"}
    d = dh.draft_unit(unit, asker=fake)
    assert d["status"] == "draft_unverified" and len(d["cards"]) == len(unit.lesson)
    assert d["cards"][0]["mnemonic"] == "m" and "error" in d["cards"][1]
    assert unit.lesson[0].telugu in calls[0]
