"""Per-learner record export as Markdown files with YAML headers (X-MEM-03, data-model.md §8).

A read-only view: Postgres stays the source of truth and nothing is ever imported back. Each file's header carries
`okf_version`, `source: postgres`, `generated_at` and `ledger_head_hash` (the hash of the newest ledger event when
the export was made). The learner's own answer text is not included; counts and states are.
The Open Knowledge Format details beyond these headers were not available to us, so `okf_version: 0.1-setu`
records the subset implemented here.
"""
import datetime as dt
import io
import zipfile
from pathlib import Path

import yaml
from sqlalchemy import text
from sqlalchemy.engine import Engine

OKF_VERSION = "0.1-setu"


def _doc(header: dict, body: str) -> str:
    return "---\n" + yaml.safe_dump(header, allow_unicode=True, sort_keys=True) + "---\n\n" + body.rstrip() + "\n"


def collect(engine: Engine, learner_id) -> dict[str, str]:
    with engine.execution_options(isolation_level="REPEATABLE READ").begin() as c:
        c.execute(text("SET LOCAL ROLE setu_app"))
        me = c.execute(text("SELECT id, handle, l1, l2, direction, role, created_at FROM learner WHERE id = :l"),
                       {"l": learner_id}).one()
        head = c.execute(text("SELECT hash FROM event_ledger ORDER BY id DESC LIMIT 1")).scalar()
        skills = c.execute(text("SELECT skill_id, status, mastery_mean, mastery_lo, mastery_hi, evidence_n, "
                                "cuefree_successes, production_successes, last_practised, due_at, tracker_version "
                                "FROM learner_skill_state WHERE learner_id = :l ORDER BY skill_id"),
                           {"l": learner_id}).all()
        classmate = c.execute(text("SELECT rule_id, state, state_version FROM classmate_rule_state "
                                   "WHERE learner_id = :l ORDER BY rule_id"), {"l": learner_id}).all()
        sessions = c.execute(text(
            "SELECT s.started_at::date AS day, count(DISTINCT s.id) AS sessions, count(a.id) AS attempts "
            "FROM session s LEFT JOIN exchange e ON e.session_id = s.id LEFT JOIN attempt a ON a.exchange_id = e.id "
            "WHERE s.learner_id = :l GROUP BY 1 ORDER BY 1"), {"l": learner_id}).all()
    base = {"okf_version": OKF_VERSION, "source": "postgres", "generated_at": dt.datetime.now(dt.UTC).isoformat(),
            "ledger_head_hash": head, "learner_id": str(me.id)}
    files = {"profile.md": _doc({**base, "kind": "profile", "handle": me.handle, "l1": me.l1, "l2": me.l2,
                                 "direction": me.direction, "role": me.role}, f"# {me.handle}")}
    for s in skills:
        header = {**base, "kind": "skill", "skill_id": s.skill_id, "status": s.status,
                  "mastery_mean": round(s.mastery_mean, 4), "mastery_lo": round(s.mastery_lo, 4),
                  "mastery_hi": round(s.mastery_hi, 4), "evidence_n": s.evidence_n,
                  "cuefree_successes": s.cuefree_successes, "production_successes": s.production_successes,
                  "last_practised": s.last_practised.isoformat() if s.last_practised else None,
                  "due_at": s.due_at.isoformat() if s.due_at else None, "tracker_version": s.tracker_version}
        files[f"skills/{s.skill_id}.md"] = _doc(header, f"# {s.skill_id}")
    files["classmate.md"] = _doc({**base, "kind": "classmate",
                                  "rules": {r.rule_id: {"state": r.state, "version": r.state_version}
                                            for r in classmate}}, "# classmate")
    for d in sessions:
        files[f"sessions/{d.day.isoformat()}.md"] = _doc(
            {**base, "kind": "sessions", "day": d.day.isoformat(), "sessions": d.sessions, "attempts": d.attempts},
            f"# {d.day.isoformat()}")
    return files


def export_learner(engine: Engine, learner_id, out_dir: Path) -> list[Path]:
    out = []
    for rel, body in collect(engine, learner_id).items():
        path = Path(out_dir) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        out.append(path)
    return out


def export_zip(engine: Engine, learner_id) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for rel, body in collect(engine, learner_id).items():
            z.writestr(rel, body)
    return buf.getvalue()
