"""Teacher review of content records (slice 4.1; X-TCH-01, gate G3).

The only code that approves or rejects letters, aksharas, words, chunks, scenes, scene scripts, scene lines and
scene reply variants. It runs every review in one transaction as `setu_content` and:
- accepts a decision only from an account whose role is `teacher` (re-checked in the database);
- reviews exactly the version the teacher saw (the content hash shown on the page must still match);
- counts an approval only with the reviewer's declaration that they are a native Telugu speaker (not needed for a
  scene's Hindi title and set-up), and never twice from one reviewer (also a database check);
- makes a record learner-visible at the second approval (`approved`); a rejection withdraws it at once;
- keeps every decision in `content_review` (immutable) and appends one ledger event (`actor = teacher:<id>`).
"""
import dataclasses
import datetime as dt
import json
import os

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

TELUGU, HINDI = True, False


@dataclasses.dataclass(frozen=True)
class Kind:
    table: str
    key: str
    status: str
    approvals: str | None  # None: one teacher approves (Hindi-only records)
    hash_sql: str
    fields: tuple  # (column, catalog key, is Telugu)
    order: str
    pending: tuple = ("draft", "in_review")

    @property
    def native_required(self) -> bool:
        return self.approvals is not None


KINDS = {
    "letter": Kind("letter", "id", "review_status", "approvals", "coalesce(content_hash, md5(telugu || devanagari))",
                   (("telugu", "tch.f.telugu", TELUGU), ("devanagari", "tch.f.devanagari", HINDI),
                    ("twin_label_hi", "tch.f.label", HINDI), ("note_hi", "tch.f.note", HINDI)), "varnamala_order"),
    "akshara": Kind("akshara", "id", "review_status", "approvals",
                    "coalesce(content_hash, md5(telugu || devanagari))",
                    (("telugu", "tch.f.telugu", TELUGU), ("devanagari", "tch.f.devanagari", HINDI),
                     ("twin_label_hi", "tch.f.label", HINDI)), "unit_order"),
    "lexeme": Kind("lexeme", "id", "review_status", "approvals",
                   "coalesce(content_hash, md5(telugu || coalesce(hindi_gloss, '')))",
                   (("telugu", "tch.f.telugu", TELUGU), ("hindi_gloss", "tch.f.meaning", HINDI),
                    ("false_friend_note_hi", "tch.f.note", HINDI)), "ladder_order NULLS LAST, id"),
    "chunk": Kind("chunk", "id", "review_status", "approvals", "coalesce(content_hash, md5(telugu || hindi_meaning))",
                  (("telugu", "tch.f.telugu", TELUGU), ("hindi_meaning", "tch.f.meaning", HINDI),
                   ("register", "tch.f.register", HINDI)), "unit_order"),
    "scene": Kind("scene", "id", "review_status", None, "coalesce(content_hash, md5(title_hi || setup_hi))",
                  (("title_hi", "tch.f.title", HINDI), ("setup_hi", "tch.f.setup", HINDI)), "id"),
    "scene_script": Kind("scene_script", "scene_id", "review_status", "approvals",
                         "coalesce(content_hash, md5(objective_hi))",
                         (("objective_hi", "tch.f.objective", HINDI), ("instructions_hi", "tch.f.instructions", HINDI),
                          ("vocab_required", "tch.f.vocab", TELUGU)), "scene_id"),
    "scene_line": Kind("scene_line", "id", "review_status", "approvals", "coalesce(content_hash, md5(telugu))",
                       (("telugu", "tch.f.telugu", TELUGU), ("question_hi", "tch.f.question", HINDI),
                        ("options_hi", "tch.f.options", HINDI), ("reply_goal_hi", "tch.f.goal", HINDI),
                        ("replies", "tch.f.replies", TELUGU), ("hint_hi", "tch.f.hint", HINDI)), "scene_id, n"),
    "accepted_variant": Kind("accepted_variant", "id", "status", "approvals",
                             "md5(form || register || coalesce(region, ''))",
                             (("form", "tch.f.telugu", TELUGU), ("register", "tch.f.register", HINDI),
                              ("region", "tch.f.region", HINDI)), "id", pending=("proposed",)),
    "scene_reply_variant": Kind("scene_reply_variant", "id", "status", "approvals", "md5(form)",
                                (("form", "tch.f.telugu", TELUGU),), "created_at", pending=("proposed",)),
}
DONE = {"approved", "rejected"}


def _select(k: Kind) -> str:
    approvals = k.approvals or "'[]'::jsonb"
    cols = ", ".join(f for f, _, _ in k.fields)
    return (f"SELECT CAST({k.key} AS text) AS id, {k.hash_sql} AS content_hash, {k.status} AS status, "
            f"{approvals} AS approvals, provenance, {cols} FROM {k.table}")


class ReviewRefused(Exception):
    """A review that cannot be applied; `key` is the Hindi catalog message."""

    def __init__(self, key: str):
        super().__init__(key)
        self.key = key


class ContentReviewer:
    @classmethod
    def from_environment(cls, *, fallback: Engine) -> "ContentReviewer":
        url = os.environ.get("SETU_CONTENT_DATABASE_URL")
        return cls(create_engine(url) if url else fallback)

    def __init__(self, engine: Engine):
        self._engine = engine

    def _tx(self):
        return _ContentTx(self._engine.execution_options(isolation_level="READ COMMITTED"))

    # ------------------------------------------------------------------ reading

    def pending_counts(self) -> dict:
        with self._tx() as c:
            return {name: c.execute(text(f"SELECT count(*) FROM {k.table} WHERE {k.status} = ANY(:p)"),
                                    {"p": list(k.pending)}).scalar_one() for name, k in KINDS.items()}

    def pending(self, kind: str, reviewer_id, limit: int = 200) -> list[dict]:
        k = KINDS[kind]
        with self._tx() as c:
            rows = c.execute(text(_select(k) + f" WHERE {k.status} = ANY(:p) ORDER BY {k.order} LIMIT :n"),
                             {"p": list(k.pending), "n": limit}).all()
        me = f"teacher:{reviewer_id}"
        return [{**r._mapping, "mine": any(a.get("reviewer") == me for a in r.approvals or [])} for r in rows]

    def record(self, kind: str, target_id: str) -> dict | None:
        k = KINDS[kind]
        with self._tx() as c:
            row = c.execute(text(_select(k) + f" WHERE CAST({k.key} AS text) = :i"), {"i": target_id}).first()
        return dict(row._mapping) if row else None

    # ------------------------------------------------------------------ deciding

    def review(self, kind: str, target_id: str, reviewer_id, *, decision: str, native: bool, content_hash: str,
               comment_hi: str | None = None, at: dt.datetime | None = None) -> str:
        """Apply one decision; returns the record's status afterwards. Raises ReviewRefused."""
        if kind not in KINDS or decision not in ("approve", "reject"):
            raise ReviewRefused("tch.bad_request")
        k, at = KINDS[kind], at or dt.datetime.now(dt.UTC)
        with self._tx() as c:
            if c.execute(text("SELECT role FROM learner WHERE id = :t"), {"t": reviewer_id}).scalar() != "teacher":
                raise ReviewRefused("err.forbidden")
            row = c.execute(text(
                f"SELECT {k.status} AS status, {k.hash_sql} AS content_hash"
                f"{', ' + k.approvals + ' AS approvals' if k.approvals else ''} FROM {k.table} "
                f"WHERE CAST({k.key} AS text) = :i FOR UPDATE"), {"i": target_id}).first()
            if row is None:
                raise ReviewRefused("tch.not_found")
            if row.content_hash != content_hash:
                raise ReviewRefused("tch.changed")
            me = f"teacher:{reviewer_id}"
            approvals = list(row.approvals or []) if k.approvals else []
            if decision == "approve":
                if row.status == "rejected":
                    raise ReviewRefused("tch.was_rejected")
                if k.native_required and not native:
                    raise ReviewRefused("tch.native_required")
                if any(a.get("reviewer") == me for a in approvals):
                    raise ReviewRefused("tch.already")
                if k.approvals:
                    approvals.append({"lang": "te", "reviewer": me, "date": at.date().isoformat(), "native": True})
                    status = "approved" if len(approvals) >= 2 else ("in_review" if k.pending[0] == "draft"
                                                                     else row.status)
                else:
                    status = "approved"
            else:
                status = "rejected"
            sets = f"{k.status} = :st" + (f", {k.approvals} = CAST(:a AS jsonb)" if k.approvals else "")
            c.execute(text(f"UPDATE {k.table} SET {sets} WHERE CAST({k.key} AS text) = :i"),
                      {"st": status, "a": json.dumps(approvals), "i": target_id})
            c.execute(text("INSERT INTO content_review (target_kind, target_id, content_hash, reviewer_id, decision, "
                           "native_speaker, comment_hi, status_after) VALUES (:k, :i, :h, :r, :d, :n, :cm, :st)"),
                      {"k": kind, "i": target_id, "h": content_hash, "r": reviewer_id, "d": decision,
                       "n": bool(native), "cm": comment_hi or None, "st": status})
            c.execute(text("INSERT INTO event_ledger (actor, event_type, payload) VALUES (:a, 'content_reviewed', "
                           "CAST(:p AS jsonb))"),
                      {"a": me, "p": json.dumps({"target_kind": kind, "target_id": target_id, "decision": decision,
                                                 "content_hash": content_hash, "status": status,
                                                 "approvals": len(approvals)}, ensure_ascii=False, sort_keys=True)})
            return status


class _ContentTx:
    def __init__(self, engine: Engine):
        self._engine = engine

    def __enter__(self):
        self._ctx = self._engine.begin()
        conn = self._ctx.__enter__()
        conn.execute(text("SET LOCAL ROLE setu_content"))
        return conn

    def __exit__(self, *exc):
        return self._ctx.__exit__(*exc)
