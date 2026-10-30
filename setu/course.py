"""The course map: chapters -> modules -> numbered lessons, with one Raju lesson closing every module.

    अध्याय 1 · अक्षर
      Module 1 · स्वर (1)     1.1 1.2 1.3 lessons, then 1.4 "🧒 Raju को आपकी मदद चाहिए" (only on 1.1–1.3)
      Module 2 · स्वर (2)     1.5 ...
A module is finished when Raju knows every lesson in it; only then does the next module open.
The map lives in data/<pair>/course.json, so modules can be regrouped without touching code.
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

DATA = Path(__file__).resolve().parent.parent / "data"
RAJU_STEP = "🧒 Raju को आपकी मदद चाहिए"


@dataclass
class Step:
    no: str                    # "1.4"
    kind: str                  # "lesson" | "raju"
    title: str
    unit: Optional[str] = None # for lessons


@dataclass
class Module:
    index: int                 # 0-based across the whole course
    chapter: int               # 1-based
    chapter_title: str
    chapter_icon: str
    number: int                # 1-based inside the chapter
    title: str
    units: List[str]
    steps: List[Step] = field(default_factory=list)
    scene: str = ""            # the real situation this module is set in (paper §5: scenes)

    @property
    def label(self) -> str:
        return f"Module {self.number} · {self.title}"

    @property
    def raju_step(self) -> Step:
        return self.steps[-1]


class Course:
    def __init__(self, modules: List[Module]):
        self.modules = modules
        self.of_unit: Dict[str, Module] = {u: m for m in modules for u in m.units}
        self.step_of_unit: Dict[str, Step] = {s.unit: s for m in modules for s in m.steps if s.unit}

    def chapters(self):
        out: Dict[int, List[Module]] = {}
        for m in self.modules:
            out.setdefault(m.chapter, []).append(m)
        return out


def build(chapters: list, titles: Dict[str, str]) -> Course:
    mods: List[Module] = []
    for ci, ch in enumerate(chapters, 1):
        n = 0
        for mi, md in enumerate(ch["modules"], 1):
            m = Module(len(mods), ci, ch["title"], ch.get("icon", "📘"), mi, md["title"], list(md["units"]),
                       scene=md.get("scene", ""))
            for u in m.units:
                n += 1
                m.steps.append(Step(f"{ci}.{n}", "lesson", titles.get(u, u), u))
            n += 1
            m.steps.append(Step(f"{ci}.{n}", "raju", RAJU_STEP))
            mods.append(m)
    return Course(mods)


def load_course(units, pair: str = "hi-te") -> Course:
    """Every unit must be in exactly one module. Inside chapters the course order is the teaching order; a unit's
    prerequisites must still come before it."""
    titles = {u.unit_id: u.title for u in units}
    path = DATA / pair / "course.json"
    chapters = json.loads(path.read_text(encoding="utf-8"))["chapters"]
    course = build(chapters, titles)
    listed = [u for m in course.modules for u in m.units]
    order = [u.unit_id for u in units]
    if sorted(listed) != sorted(order) or len(set(listed)) != len(listed):
        raise ValueError(f"{path}: every unit must appear exactly once (missing: {sorted(set(order) - set(listed))})")
    pos = {u: i for i, u in enumerate(listed)}
    for u in units:
        bad = [r for r in u.requires if pos.get(r, -1) >= pos[u.unit_id]]
        if bad:
            raise ValueError(f"{path}: {u.unit_id} comes before {bad}, which it requires")
    return course


def singles(units) -> Course:
    """One unit per module (Raju right after every lesson). Used by tests of Raju's mechanics."""
    return build([{"title": "all", "modules": [{"title": u.unit_id, "units": [u.unit_id]} for u in units]}],
                 {u.unit_id: u.title for u in units})
