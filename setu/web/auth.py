"""Pseudonymous accounts (E-08, data-model.md §5).

- No names, emails or phone numbers. A facilitator hands out an invite code; the app generates a random numeric
  handle (digits only, so nothing Latin appears to learners) and the learner chooses a passphrase.
- Passphrases are hashed with argon2id. Session tokens are random; only their sha256 is stored.
- Five failed logins within 15 minutes lock a handle. No IP addresses are stored (they are personal data).
- Failed logins look the same whether or not the handle exists.
"""
import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from .db import AppDatabase

_hasher = PasswordHasher()  # argon2id with the library's current recommended parameters
_DUMMY_HASH = _hasher.hash("timing-equaliser-not-a-real-account")

MIN_PASSPHRASE, MAX_PASSPHRASE = 10, 200
SESSION_DAYS = 14
LOCK_AFTER_FAILURES, LOCK_WINDOW = 5, timedelta(minutes=15)
ROLES = ("learner", "teacher", "researcher", "admin")
# Who may create invites for which roles.
INVITE_RIGHTS = {"researcher": ("learner", "teacher"), "admin": ROLES}


def _digits(n: int) -> str:
    return "".join(secrets.choice("0123456789") for _ in range(n))


def new_handle() -> str:
    return f"{_digits(4)}-{_digits(4)}"


def new_invite_code() -> str:
    return f"{_digits(4)}-{_digits(4)}-{_digits(4)}"


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def code_hash(code: str) -> str:
    return hashlib.sha256(code.strip().encode()).hexdigest()


def hash_passphrase(passphrase: str) -> str:
    return _hasher.hash(passphrase)


def verify_passphrase(stored_hash: str, passphrase: str) -> bool:
    try:
        return _hasher.verify(stored_hash, passphrase)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def passphrase_problem(passphrase: str, *, handle: str | None = None) -> str | None:
    stripped = passphrase.strip()
    if len(stripped) < MIN_PASSPHRASE:
        return "too_short"
    if len(passphrase) > MAX_PASSPHRASE:
        return "too_long"
    if handle and stripped.replace("-", "") == handle.replace("-", ""):
        return "same_as_handle"
    return None


def _now() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------- invites


def create_invite(engine_or_db, *, role: str = "learner", cohort: str | None = None, valid_hours: float = 72,
                  created_by: uuid.UUID | None = None) -> str:
    """Create a single-use invite and return its code (shown once; only its hash is stored)."""
    if role not in ROLES:
        raise ValueError(f"role must be one of {ROLES}")
    db = engine_or_db if isinstance(engine_or_db, AppDatabase) else AppDatabase(engine_or_db)
    code = new_invite_code()
    with db.tx() as c:
        c.execute(text("INSERT INTO invite (code_hash, role, cohort, created_by, expires_at) "
                       "VALUES (:h, :r, :co, :by, :exp)"),
                  {"h": code_hash(code), "r": role, "co": cohort, "by": created_by,
                   "exp": _now() + timedelta(hours=valid_hours)})
    return code


def redeem_invite(c: Connection, code: str, passphrase: str) -> tuple[uuid.UUID, str] | None:
    invite = c.execute(text("SELECT id, role, cohort FROM invite WHERE code_hash = :h AND used_at IS NULL "
                            "AND expires_at > now() FOR UPDATE"), {"h": code_hash(code)}).first()
    if invite is None:
        return None
    for _ in range(20):  # handles are random; retry on the rare collision
        handle = new_handle()
        if c.execute(text("SELECT 1 FROM learner WHERE handle = :h"), {"h": handle}).first() is None:
            break
    else:
        raise RuntimeError("could not allocate a handle")
    learner_id = c.execute(
        text("INSERT INTO learner (handle, passphrase_hash, l1, l2, direction, role, cohort) "
             "VALUES (:h, :p, 'hi', 'te', 'HI->TE', :r, :co) RETURNING id"),
        {"h": handle, "p": hash_passphrase(passphrase), "r": invite.role, "co": invite.cohort}).scalar_one()
    c.execute(text("UPDATE invite SET used_at = now(), used_by = :l WHERE id = :i"), {"l": learner_id, "i": invite.id})
    return learner_id, handle


# ---------------------------------------------------------------- sessions


def open_session(c: Connection, learner_id: uuid.UUID) -> tuple[str, datetime]:
    token = new_session_token()
    expires = _now() + timedelta(days=SESSION_DAYS)
    c.execute(text("INSERT INTO auth_session (token_hash, learner_id, expires_at) VALUES (:t, :l, :e)"),
              {"t": token_hash(token), "l": learner_id, "e": expires})
    return token, expires


def is_locked(c: Connection, handle: str) -> bool:
    last_ok = c.execute(text("SELECT max(ts) FROM login_attempt WHERE handle = :h AND ok"), {"h": handle}).scalar()
    since = max(_now() - LOCK_WINDOW, last_ok) if last_ok else _now() - LOCK_WINDOW
    failures = c.execute(text("SELECT count(*) FROM login_attempt WHERE handle = :h AND NOT ok AND ts > :s"),
                         {"h": handle, "s": since}).scalar_one()
    return failures >= LOCK_AFTER_FAILURES


def check_login(c: Connection, handle: str, passphrase: str) -> uuid.UUID | None:
    row = c.execute(text("SELECT id, passphrase_hash FROM learner WHERE handle = :h"), {"h": handle}).first()
    ok = verify_passphrase(row.passphrase_hash if row else _DUMMY_HASH, passphrase) and row is not None
    c.execute(text("INSERT INTO login_attempt (handle, ok) VALUES (:h, :ok)"), {"h": handle, "ok": ok})
    return row.id if ok else None


def session_user(c: Connection, token: str):
    return c.execute(
        text("SELECT l.id AS learner_id, l.handle, l.role, s.id AS session_id FROM auth_session s "
             "JOIN learner l ON l.id = s.learner_id WHERE s.token_hash = :t AND s.revoked_at IS NULL "
             "AND s.expires_at > now()"), {"t": token_hash(token)}).first()


def revoke_session(c: Connection, session_id: uuid.UUID) -> None:
    c.execute(text("UPDATE auth_session SET revoked_at = now() WHERE id = :s AND revoked_at IS NULL"),
              {"s": session_id})


def bootstrap_admin_invite(engine: Engine) -> str:
    """For first deployment only: an admin invite (used by `python -m setu.web.admin`)."""
    return create_invite(engine, role="admin", valid_hours=24)
