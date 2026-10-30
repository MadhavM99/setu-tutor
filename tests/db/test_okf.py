"""OKF export (X-MEM-03; TS-OKF-01..03): a read-only view whose values equal the database."""
import datetime as dt
import io
import uuid
import zipfile

import yaml
from fastapi.testclient import TestClient
from sqlalchemy import text

from setu.domain.checker import _issue_verdict as issue_verdict

from .helpers import make_learner


def header(body: str) -> dict:
    return yaml.safe_load(body.split("---\n")[1])


def _learner_with_a_skill(engine):
    from setu.store.outcome_writer import OutcomeWriter, SkillTarget

    with engine.begin() as c:
        learner = make_learner(c, handle=f"h-{uuid.uuid4().hex[:10]}")
        skill = f"L2.word.{uuid.uuid4().hex[:6]}.RCL"
        c.execute(text("INSERT INTO skill (id, band, family, target, modality, direction) VALUES "
                       "(:s, 'L2', 'word', 'x', 'RCL', 'HI->TE')"), {"s": skill})
        s = c.execute(text("INSERT INTO session (learner_id, mode, config_snapshot, seed) VALUES (:l, 'learn', '{}', 1) "
                           "RETURNING id"), {"l": learner}).scalar_one()
        e = c.execute(text("INSERT INTO exchange (session_id, kind, source) VALUES (:s, 'review', 'bank') RETURNING id"),
                      {"s": s}).scalar_one()
        a = c.execute(text("INSERT INTO attempt (exchange_id, n, raw_text, idempotency_key) VALUES (:e, 1, "
                           "'गुप्त जवाब', :k) RETURNING id"), {"e": e, "k": uuid.uuid4().hex}).scalar_one()
    w = OutcomeWriter(engine, resolution_key=b"k" * 32)
    w.record_verdict(issue_verdict(attempt_id=a, outcome="correct", kind="recall", reason_code="t"),
                     skill=SkillTarget(skill, "L2", "a", "recall"), at=dt.datetime.now(dt.UTC))
    return learner, skill


def test_export_matches_the_database_and_leaves_out_answer_text(engine, tmp_path):
    from setu.export import okf

    learner, skill = _learner_with_a_skill(engine)
    paths = okf.export_learner(engine, learner, tmp_path)
    names = {p.relative_to(tmp_path).as_posix() for p in paths}
    assert {"profile.md", "classmate.md", f"skills/{skill}.md"} <= names
    h = header((tmp_path / f"skills/{skill}.md").read_text(encoding="utf-8"))
    with engine.connect() as c:
        row = c.execute(text("SELECT status, evidence_n, mastery_mean FROM learner_skill_state WHERE learner_id = :l"),
                        {"l": learner}).one()
        head = c.execute(text("SELECT hash FROM event_ledger ORDER BY id DESC LIMIT 1")).scalar()
    assert h["source"] == "postgres" and h["okf_version"] and h["ledger_head_hash"] == head
    assert (h["status"], h["evidence_n"], h["mastery_mean"]) == (row.status, row.evidence_n, round(row.mastery_mean, 4))
    assert not any("गुप्त जवाब" in p.read_text(encoding="utf-8") for p in paths)


def test_export_is_regenerated_from_the_database(engine, tmp_path):
    from setu.export import okf

    learner, skill = _learner_with_a_skill(engine)
    first = header(okf.collect(engine, learner)[f"skills/{skill}.md"])
    with engine.begin() as c:  # a later state change shows up in the next export
        c.execute(text("UPDATE learner_skill_state SET evidence_n = evidence_n + 1 WHERE learner_id = :l"),
                  {"l": learner})
    second = header(okf.collect(engine, learner)[f"skills/{skill}.md"])
    assert second["evidence_n"] == first["evidence_n"] + 1


def test_learners_download_their_own_record(engine):
    from setu.web import auth
    from setu.web.app import create_app

    c = TestClient(create_app(engine=engine), base_url="https://testserver")
    r = c.post("/api/auth/register", json={"invite_code": auth.create_invite(engine), "passphrase": "मेरा लंबा पासवर्ड"})
    zipped = c.get("/api/export/okf")
    assert zipped.status_code == 200 and zipped.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(zipped.content)) as z:
        assert header(z.read("profile.md").decode())["learner_id"] == r.json()["learner_id"]
    assert TestClient(create_app(engine=engine), base_url="https://testserver").get("/api/export/okf").status_code == 401
