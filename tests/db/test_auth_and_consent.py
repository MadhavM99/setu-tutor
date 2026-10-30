"""Pseudonymous accounts, roles, consent and withdrawal over the HTTP API, against real Postgres
(E-08, P-ETH-04/05, X-PRIV-01, data-model §5; TS-AUTHN-*, TS-PRIV-01, TS-PRIV-06)."""
import json
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

PASS = "मेरा लंबा पासवर्ड"


@pytest.fixture
def app(engine):
    from setu.web.app import create_app

    return create_app(engine=engine, cookie_secure=True)


def client(app):
    return TestClient(app, base_url="https://testserver")


def invite(engine, role="learner", **kw):
    from setu.web import auth

    return auth.create_invite(engine, role=role, **kw)


def register(app, engine, role="learner"):
    c = client(app)
    r = c.post("/auth/register", json={"invite_code": invite(engine, role=role), "passphrase": PASS})
    assert r.status_code == 201, r.text
    return c, r.json()["handle"], uuid.UUID(r.json()["learner_id"])


def consent(c, scopes=("pilot",)):
    return c.post("/consent", json={"form_version": "pilot-v1", "scopes": list(scopes)})


def q(engine, sql, **p):
    with engine.connect() as c:
        return c.execute(text(sql), p).all()


# ---------------------------------------------------------------- registration and login


def test_register_with_an_invite_gives_a_numeric_handle_and_a_session(app, engine):
    c, handle, lid = register(app, engine)
    assert handle.replace("-", "").isdigit()
    me = c.get("/me").json()
    assert me == {"learner_id": str(lid), "handle": handle, "role": "learner", "consent": None}
    row = q(engine, "SELECT passphrase_hash FROM learner WHERE id = :i", i=lid)[0]
    assert row.passphrase_hash.startswith("$argon2id$")


def test_learner_table_holds_no_names_emails_or_phones(engine):
    cols = {r.column_name for r in q(engine, "SELECT column_name FROM information_schema.columns "
                                             "WHERE table_name = 'learner'")}
    assert not cols & {"name", "full_name", "email", "phone", "mobile", "address", "ip", "ip_address"}


def test_invites_are_single_use_and_unknown_or_expired_invites_fail(app, engine):
    code = invite(engine)
    assert client(app).post("/auth/register", json={"invite_code": code, "passphrase": PASS}).status_code == 201
    again = client(app).post("/auth/register", json={"invite_code": code, "passphrase": PASS})
    assert again.status_code == 400 and again.json()["message_key"] == "err.invite_invalid"
    unknown = client(app).post("/auth/register", json={"invite_code": "0000-0000-0000", "passphrase": PASS})
    assert unknown.json()["message_key"] == "err.invite_invalid"
    expired = invite(engine, valid_hours=-1)
    r = client(app).post("/auth/register", json={"invite_code": expired, "passphrase": PASS})
    assert r.json()["message_key"] == "err.invite_invalid"


def test_weak_passphrase_is_refused(app, engine):
    r = client(app).post("/auth/register", json={"invite_code": invite(engine), "passphrase": "short"})
    assert r.status_code == 400 and r.json()["message_key"] == "err.weak_passphrase"


def test_session_cookie_is_httponly_secure_samesite_and_only_its_hash_is_stored(app, engine):
    c, handle, lid = register(app, engine)
    r = c.post("/auth/login", json={"handle": handle, "passphrase": PASS})
    assert r.status_code == 204
    cookie = r.headers["set-cookie"]
    assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=lax" in cookie.replace("Lax", "lax")
    token = cookie.split("setu_session=", 1)[1].split(";", 1)[0]
    stored = [row.token_hash for row in q(engine, "SELECT token_hash FROM auth_session WHERE learner_id = :i", i=lid)]
    assert token not in stored and len(stored) >= 2


def test_failed_login_does_not_reveal_whether_a_handle_exists(app, engine):
    _, handle, _ = register(app, engine)
    wrong = client(app).post("/auth/login", json={"handle": handle, "passphrase": "गलत पासवर्ड है यह"})
    nobody = client(app).post("/auth/login", json={"handle": "9999-0000", "passphrase": "गलत पासवर्ड है यह"})
    assert wrong.status_code == nobody.status_code == 401
    assert wrong.json() == nobody.json() == {"error": "auth_failed", "message_key": "err.auth_failed"}


def test_five_failures_lock_the_handle_even_for_the_right_passphrase(app, engine):
    _, handle, _ = register(app, engine)
    for _ in range(5):
        client(app).post("/auth/login", json={"handle": handle, "passphrase": "गलत पासवर्ड है यह"})
    r = client(app).post("/auth/login", json={"handle": handle, "passphrase": PASS})
    assert r.status_code == 429 and r.json()["message_key"] == "err.locked"


def test_logout_revokes_the_session(app, engine):
    c, _, _ = register(app, engine)
    cookie = c.cookies.get("setu_session")
    assert c.post("/auth/logout").status_code == 204
    replay = client(app)
    replay.cookies.set("setu_session", cookie)
    assert replay.get("/me").status_code == 401


def test_requests_without_a_session_are_refused(app):
    r = client(app).get("/me")
    assert r.status_code == 401 and r.json()["message_key"] == "err.not_signed_in"


# ---------------------------------------------------------------- roles


def test_only_researchers_and_admins_create_invites(app, engine):
    learner, _, _ = register(app, engine)
    r = learner.post("/research/invites", json={"role": "learner"})
    assert r.status_code == 403 and r.json()["message_key"] == "err.forbidden"
    researcher, _, _ = register(app, engine, role="researcher")
    r = researcher.post("/research/invites", json={"role": "learner", "cohort": "pilot-1"})
    assert r.status_code == 201 and r.json()["invite_code"]
    # a researcher cannot mint admins; only an admin can create privileged invites
    assert researcher.post("/research/invites", json={"role": "admin"}).status_code == 403


def test_teachers_cannot_use_research_endpoints(app, engine):
    teacher, _, _ = register(app, engine, role="teacher")
    assert teacher.post("/research/invites", json={"role": "learner"}).status_code == 403


# ---------------------------------------------------------------- consent


def test_consent_is_recorded_with_its_form_version_and_scopes(app, engine):
    c, _, _ = register(app, engine)
    assert c.get("/consent").json()["form_version"] == "pilot-v1"
    assert consent(c, ("pilot", "audio")).status_code == 204
    me = c.get("/me").json()
    assert me["consent"] == {"form_version": "pilot-v1", "scopes": ["pilot", "audio"]}
    bad = c.post("/consent", json={"form_version": "pilot-v1", "scopes": ["marketing"]})
    assert bad.status_code == 400 and bad.json()["message_key"] == "err.validation"
    unknown_form = c.post("/consent", json={"form_version": "pilot-v0", "scopes": ["pilot"]})
    assert unknown_form.json()["message_key"] == "err.validation"


def _start_session(engine, lid, mode="learn"):
    with engine.begin() as c:
        c.execute(text("SET LOCAL ROLE setu_app"))
        return c.execute(text("INSERT INTO session (learner_id, mode, config_snapshot, seed) VALUES "
                              "(:l, :m, '{}', 1) RETURNING id"), {"l": lid, "m": mode}).scalar_one()


def test_no_practice_session_without_active_consent(app, engine):
    c, _, lid = register(app, engine)
    with pytest.raises(DBAPIError) as e:
        _start_session(engine, lid)
    assert "consent" in str(e.value.orig)
    consent(c, ("audio",))
    _start_session(engine, lid)  # any active consent allows ordinary practice
    with pytest.raises(DBAPIError) as e:
        _start_session(engine, lid, mode="study_A")  # study sessions need the pilot scope
    assert "pilot" in str(e.value.orig)
    consent(c, ("pilot",))
    _start_session(engine, lid, mode="study_A")


# ---------------------------------------------------------------- withdrawal


def _attempt(engine, session_id, raw):
    with engine.begin() as c:
        c.execute(text("SET LOCAL ROLE setu_app"))
        e = c.execute(text("INSERT INTO exchange (session_id, kind, source) VALUES (:s, 'own', 'template') "
                           "RETURNING id"), {"s": session_id}).scalar_one()
        return c.execute(text("INSERT INTO attempt (exchange_id, n, raw_text, normalised_text, idempotency_key) "
                              "VALUES (:e, 1, :t, :t, :k) RETURNING id"),
                         {"e": e, "t": raw, "k": uuid.uuid4().hex}).scalar_one()


def test_withdrawal_redacts_learner_text_and_stops_further_sessions(app, engine):
    from setu.domain.checker import issue_verdict
    from setu.store.outcome_writer import OutcomeWriter

    c, _, lid = register(app, engine)
    consent(c, ("pilot",))
    with engine.begin() as conn:
        conn.execute(text("SET LOCAL ROLE setu_app"))
        conn.execute(text("INSERT INTO background (learner_id, answers) VALUES (:l, '{\"region\": \"हैदराबाद\"}')"),
                     {"l": lid})
    s = _start_session(engine, lid)
    a = _attempt(engine, s, "నేను హైదరాబాద్‌లో ఉంటాను — मेरा नाम रमेश है")
    OutcomeWriter(engine, resolution_key=b"k" * 32).record_verdict(
        issue_verdict(attempt_id=a, outcome="unsure", kind="own", reason_code="unseen", checker_version="t"))

    r = c.post("/consent/withdraw")
    assert r.status_code == 204

    attempt = q(engine, "SELECT raw_text, normalised_text, redacted_at FROM attempt WHERE id = :a", a=a)[0]
    assert attempt.raw_text == "" and attempt.normalised_text is None and attempt.redacted_at is not None
    assert q(engine, "SELECT count(*) AS n FROM background WHERE learner_id = :l", l=lid)[0].n == 0
    assert q(engine, "SELECT count(*) AS n FROM consent WHERE learner_id = :l AND withdrawn_at IS NULL",
             l=lid)[0].n == 0
    assert c.get("/me").status_code == 401  # sessions revoked
    with pytest.raises(DBAPIError):
        _start_session(engine, lid)
    # The append-only ledger is untouched and never held the learner's words in the first place.
    with engine.connect() as conn:
        assert conn.execute(text("SELECT setu_verify_ledger()")).scalar_one() is None
        payloads = conn.execute(text("SELECT payload FROM event_ledger WHERE payload->>'learner_id' = :l"),
                                {"l": str(lid)}).scalars().all()
    assert payloads and not any("रमेश" in json.dumps(p, ensure_ascii=False) for p in payloads)


def test_researcher_can_withdraw_a_participant_and_learners_cannot_withdraw_others(app, engine):
    learner_c, _, lid = register(app, engine)
    consent(learner_c)
    other, _, _ = register(app, engine)
    assert other.post(f"/research/participants/{lid}/withdraw").status_code == 403
    researcher, _, _ = register(app, engine, role="researcher")
    assert researcher.post(f"/research/participants/{lid}/withdraw").status_code == 204
    assert q(engine, "SELECT count(*) AS n FROM consent WHERE learner_id = :l AND withdrawn_at IS NULL",
             l=lid)[0].n == 0


def test_app_role_cannot_redact_or_delete_directly(engine):
    with engine.connect() as c:
        c.execute(text("SET ROLE setu_app"))
        for sql in ("UPDATE attempt SET raw_text = ''", "DELETE FROM background", "DELETE FROM attempt"):
            sp = c.begin_nested()
            with pytest.raises(DBAPIError) as e:
                c.execute(text(sql))
            sp.rollback()
            assert "permission denied" in str(e.value.orig)
        c.execute(text("RESET ROLE"))


def test_read_role_cannot_see_auth_tables(engine):
    with engine.connect() as c:
        c.execute(text("SET ROLE setu_read"))
        for table in ("auth_session", "invite", "login_attempt"):
            sp = c.begin_nested()
            with pytest.raises(DBAPIError):
                c.execute(text(f"SELECT * FROM {table}"))
            sp.rollback()
        c.execute(text("RESET ROLE"))
