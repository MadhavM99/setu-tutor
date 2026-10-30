"""What is saved per learner: their own memory of each unit, Raju's notebook, and the open question.
Stored as one JSON file per learner (runs/<learner>.json), so a session can stop and continue later.

Recall model v0 (a simple stand-in for FSRS from the paper): each unit has a half-life in days.
A correct answer doubles it (x1.2 when you only *recognised* a correct line), a wrong answer halves it.
p_recall = 2 ** (-days since last practice / half-life)."""
from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

DAY = 86400.0


class UnitMemory(BaseModel):
    introduced_at: Optional[float] = None     # when the lesson was shown (for the new-lessons-per-day limit)
    ready: bool = False                       # the learner answered the check after the lesson correctly
    correct: int = 0
    wrong: int = 0
    last: Optional[float] = None
    half_life: float = 1.0                    # days

    def p_recall(self, now: float) -> float:
        if self.last is None:
            return 0.0
        return 2 ** (-((now - self.last) / DAY) / self.half_life)

    def update(self, verdict: str, now: float, recognition: bool = False) -> None:
        if verdict == "unsure":               # never counts
            return
        if verdict == "correct":
            self.correct += 1
            self.half_life *= 1.2 if recognition else 2.0
        else:
            self.wrong += 1
            self.half_life = max(0.5, self.half_life / 2)
        self.last = now


class LearnerRecord(BaseModel):
    learner_id: str
    day_offset: float = 0.0                   # testing/demo: "skip N days"
    units: Dict[str, UnitMemory] = Field(default_factory=dict)
    raju: Dict[str, str] = Field(default_factory=dict)        # unit_id -> unknown / learning / taught / forgotten
    fu_done: Dict[str, int] = Field(default_factory=dict)     # unit_id -> Raju's follow-ups answered
    fu_from: Dict[str, str] = Field(default_factory=dict)     # unit_id -> item the learner fixed (picks the follow-ups)
    pending: Optional[dict] = None            # the question waiting for an answer
    last_unit: Optional[str] = None           # no back-to-back repeats
    variety: Dict[str, int] = Field(default_factory=dict)   # day -> spot checks given only because nothing else was left
    weak: List[str] = Field(default_factory=list)             # item_ids missed 3 times in the drill: Raju asks these first
    modules_done: List[int] = Field(default_factory=list)     # course modules finished (Raju knew every lesson once)
    model_calls: int = 0
    turns: int = 0
    log: List[dict] = Field(default_factory=list)             # last steps, for /status and debugging

    def now(self) -> float:
        return time.time() + self.day_offset * DAY

    def mem(self, unit_id: str) -> UnitMemory:
        return self.units.setdefault(unit_id, UnitMemory())

    def note(self, **entry) -> None:
        self.log.append({"day": round(self.day_offset, 1), **entry})
        del self.log[:-30]


class Store:
    def __init__(self, root: str = "runs"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, learner_id: str) -> Path:
        safe = "".join(c for c in learner_id if c.isalnum() or c in "-_")[:64] or "anon"
        return self.root / f"{safe}.json"

    def load(self, learner_id: str) -> LearnerRecord:
        p = self._path(learner_id)
        if p.exists():
            return LearnerRecord.model_validate_json(p.read_text(encoding="utf-8"))
        return LearnerRecord(learner_id=learner_id)

    def save(self, rec: LearnerRecord) -> None:
        self._path(rec.learner_id).write_text(rec.model_dump_json(indent=1), encoding="utf-8")

    def reset(self, learner_id: str) -> None:
        """Start a learner from zero (demos)."""
        p = self._path(learner_id)
        if p.exists():
            p.unlink()

    def read_queue(self) -> List[dict]:
        p = self.root / "teacher_queue.jsonl"
        if not p.exists():
            return []
        return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]

    def queue_for_teacher(self, entry: dict) -> None:
        with open(self.root / "teacher_queue.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
