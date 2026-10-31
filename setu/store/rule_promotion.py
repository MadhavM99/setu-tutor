"""Rule review and promotion, variant proposals and rater agreement (slice 4.2; F1, F2, F4, P-EVAL-11, X-TCH-02/03).

Runs as `setu_content`, like `ContentReviewer`. Rule and item versions are immutable, so every lifecycle step is a
new version that copies the previous one and changes only its status fields:
- a review is recorded against the newest version (one per reviewer per round); `setu.domain.rule_review.decide`
  turns the native Telugu reviews into verify / reject / a third reviewer / wait;
- verify → a new version `validity = verified, lifecycle = verified` with the approvers as `speaker_approvals`, plus a
  new `approved` version of every item without open issues (its accepted variants copied along). Refused, with a
  Hindi reason, while the rule has open validation issues or no Hindi title or explanation;
- activate (a teacher, on a verified version) → `active, teacher_approved`: only now learners see the rule;
- deprecate (an active version) → `deprecated`, withdrawn at once; reject → `rejected`.
Every step appends one `content_reviewed` ledger event by the teacher.
"""
import dataclasses
import datetime as dt
import json

from sqlalchemy import text

from setu.domain import rule_review as R
from setu.research import agreement

from .content_review import ContentReviewer, ReviewRefused

ROUND = 1
LIKERT = range(1, 6)
BANDS = ("L0", "L1", "L2", "L3", "L4", "L5")
RULE_COPY = ("rule_id, title_hi, l1_explanation_hi, concept_key, band, target_skill_id, learner_evidence, sources, "
             "licence, reviewers, region_register_notes, opportunities, observed_errors, provenance, validation_issues")
ITEM_COPY = ("item_id, template, hindi_meaning, wrong_form, one_error_span, correct_form, no_error_equivalent, "
             "wrong_patterns, accept_patterns, vocab_prereqs, allowed_target_forms, analyser_requirements, band, "
             "band_reason, leveler_version, pool, provenance, validation_issues")
CONSOLE_BATCH = "console"


@dataclasses.dataclass(frozen=True)
class RuleForm:
    language: str
    native: bool
    acceptable_natural: int
    category_ok: bool
    explanation_ok: int
    band_fit: str
    confidence: int
    decision: str
    comments_hi: str | None = None

    def check(self):
        if (self.language not in ("te", "hi") or self.decision not in R.DECISIONS or self.band_fit not in BANDS
                or any(x not in LIKERT for x in (self.acceptable_natural, self.explanation_ok, self.confidence))):
            raise ReviewRefused("tch.bad_request")


class RuleReviewer(ContentReviewer):
    # ------------------------------------------------------------------ reading

    def overview(self) -> list[dict]:
        with self._tx() as c:
            rows = c.execute(text(
                "SELECT rv.id, rv.rule_id, rv.version, rv.title_hi, rv.lifecycle, rv.validity, r.direction, "
                "jsonb_array_length(rv.validation_issues) AS issues FROM rule_version rv JOIN rule r ON r.id = rv.rule_id "
                "WHERE rv.version = (SELECT max(x.version) FROM rule_version x WHERE x.rule_id = rv.rule_id) "
                "ORDER BY rv.rule_id")).all()
            return [{**r._mapping, "state": _decide(c, r.id).state, "reviews": _count(c, r.id)} for r in rows]

    def detail(self, rule_id: str, reviewer_id) -> dict | None:
        with self._tx() as c:
            v = _latest(c, rule_id)
            if v is None:
                return None
            items = c.execute(text(
                "SELECT DISTINCT ON (iv.item_id) iv.id, iv.item_id, iv.hindi_meaning, iv.wrong_form, iv.correct_form, "
                "iv.one_error_span, iv.review_status, iv.pool, jsonb_array_length(iv.validation_issues) AS issues, "
                "coalesce((SELECT array_agg(av.form || ' (' || av.status || ')' ORDER BY av.form) FROM accepted_variant av "
                "WHERE av.item_version_id = iv.id), '{}') AS variants FROM item_version iv JOIN item i ON i.id = iv.item_id "
                "WHERE i.rule_id = :r ORDER BY iv.item_id, iv.version DESC"), {"r": rule_id}).all()
            hints = c.execute(text("SELECT type, text_hi, status FROM hint WHERE rule_version_id = :v"),
                              {"v": v.id}).all()
            history = c.execute(text("SELECT version, lifecycle, validity, teacher_approved, change_note, created_at "
                                     "FROM rule_version WHERE rule_id = :r ORDER BY version DESC"), {"r": rule_id}).all()
            mine = c.execute(text("SELECT 1 FROM rule_review WHERE rule_version_id = :v AND reviewer_id = :w AND "
                                  "round = :n"), {"v": v.id, "w": f"teacher:{reviewer_id}", "n": ROUND}).first()
            return {"version": v, "item_rows": [_marked(i) for i in items], "hints": hints, "history": history,
                    "state": _decide(c, v.id).state, "reviews": _count(c, v.id), "mine": mine is not None}

    # ------------------------------------------------------------------ deciding

    def review_rule(self, rule_id: str, rule_version_id: str, reviewer_id, form: RuleForm) -> str:
        """Record one review; promote or reject when the reviews decide it. Returns a Hindi catalog key."""
        form.check()
        me = f"teacher:{reviewer_id}"
        with self._tx() as c:
            _require_teacher(c, reviewer_id)
            v = _latest(c, rule_id, lock=True)
            if v is None or str(v.id) != str(rule_version_id):
                raise ReviewRefused("tch.r.changed")
            if v.lifecycle not in ("draft", "review"):
                raise ReviewRefused("tch.r.not_reviewable")
            if c.execute(text("SELECT 1 FROM rule_review WHERE rule_version_id = :v AND reviewer_id = :w AND round = :n"),
                         {"v": v.id, "w": me, "n": ROUND}).first():
                raise ReviewRefused("tch.r.already")
            c.execute(text(
                "INSERT INTO rule_review (rule_version_id, reviewer_id, language, acceptable_natural, category_ok, "
                "explanation_ok, band_fit, confidence, comments_hi, round, decision, native_speaker, batch) VALUES "
                "(:v, :w, :lang, :an, :cat, :ex, :band, :conf, :cm, :n, :d, :native, :batch)"),
                {"v": v.id, "w": me, "lang": form.language, "an": form.acceptable_natural, "cat": form.category_ok,
                 "ex": form.explanation_ok, "band": form.band_fit, "conf": form.confidence,
                 "cm": form.comments_hi or None, "n": ROUND, "d": form.decision,
                 "native": form.native and form.language == "te", "batch": CONSOLE_BATCH})
            _ledger(c, me, rule_id, "review", {"decision": form.decision, "rule_version_id": str(v.id)})
            d = _decide(c, v.id)
            if d.state == "reject":
                _new_version(c, v, me, validity="rejected", lifecycle="rejected", note="rejected by two reviewers")
                return "tch.r.rejected"
            if d.state == "needs_third":
                return "tch.r.needs_third"
            if d.state != "verify":
                return "tch.r.needs_second"
            if not v.title_hi or not v.l1_explanation_hi:
                return "tch.r.needs_explanation"
            if v.issues:
                return "tch.r.has_issues"
            today = dt.datetime.now(dt.UTC).date().isoformat()
            approvals = [{"lang": "te", "reviewer": w, "date": today, "native": True} for w in d.approvers]
            new_id = _new_version(c, v, me, validity="verified", lifecycle="verified", approvals=approvals,
                                  note="verified by two native Telugu reviewers")
            _approve_items(c, rule_id, new_id)
            return "tch.r.verified"

    def activate(self, rule_id: str, rule_version_id: str, teacher_id) -> str:
        me = f"teacher:{teacher_id}"
        with self._tx() as c:
            _require_teacher(c, teacher_id)
            v = _latest(c, rule_id, lock=True)
            if v is None or str(v.id) != str(rule_version_id):
                raise ReviewRefused("tch.r.changed")
            if v.validity != "verified" or v.lifecycle != "verified":
                raise ReviewRefused("tch.r.not_verified")
            _new_version(c, v, me, lifecycle="active", teacher_approved=True, note="activated by a teacher")
            return "tch.r.activated"

    def deprecate(self, rule_id: str, rule_version_id: str, teacher_id) -> str:
        me = f"teacher:{teacher_id}"
        with self._tx() as c:
            _require_teacher(c, teacher_id)
            v = _latest(c, rule_id, lock=True)
            if v is None or str(v.id) != str(rule_version_id):
                raise ReviewRefused("tch.r.changed")
            if v.lifecycle != "active":
                raise ReviewRefused("tch.r.not_active")
            _new_version(c, v, me, lifecycle="deprecated", note="withdrawn by a teacher")
            return "tch.r.deprecated"

    def propose_variant(self, *, item_version_id, form: str, teacher_id, queue_item_id) -> bool:
        """F3 → F4: propose a settled answer as an accepted variant of its item (still needs two approvals)."""
        me = f"teacher:{teacher_id}"
        if item_version_id is None or not form:
            return False
        with self._tx() as c:
            _require_teacher(c, teacher_id)
            if c.execute(text("SELECT 1 FROM accepted_variant WHERE item_version_id = :iv AND form = :f"),
                         {"iv": item_version_id, "f": form}).first():
                return False
            prov = [{"source": f"proposed by {me} when settling an answer", "queue_item_id": str(queue_item_id)}]
            c.execute(text("INSERT INTO accepted_variant (item_version_id, form, register, status, approvals, provenance) "
                           "VALUES (:iv, :f, 'written', 'proposed', '[]', CAST(:p AS jsonb))"),
                      {"iv": item_version_id, "f": form, "p": json.dumps(prov)})
            c.execute(text("INSERT INTO event_ledger (actor, event_type, payload) VALUES (:a, 'content_reviewed', "
                           "CAST(:p AS jsonb))"),
                      {"a": me, "p": json.dumps({"target_kind": "accepted_variant", "decision": "propose",
                                                 "item_version_id": str(item_version_id)}, sort_keys=True)})
            return True

    # ------------------------------------------------------------------ agreement (F2)

    def agreement(self, batch: str = CONSOLE_BATCH, *, store: bool = False, teacher_id=None) -> dict:
        """Cohen's kappa between the first two native Telugu reviewers of each rule version in `batch`."""
        with self._tx() as c:
            if store:
                _require_teacher(c, teacher_id)
            rows = c.execute(text(
                "SELECT rule_version_id, category_ok, band_fit, decision FROM rule_review WHERE batch = :b AND "
                "language = 'te' AND native_speaker AND round = :n ORDER BY rule_version_id, created_at"),
                {"b": batch, "n": ROUND}).all()
            pairs: dict = {}
            for r in rows:
                pairs.setdefault(r.rule_version_id, [])
                if len(pairs[r.rule_version_id]) < 2:
                    pairs[r.rule_version_id].append(r)
            pairs = {k: v for k, v in pairs.items() if len(v) == 2}
            out = {}
            for metric in ("category_ok", "band_fit", "decision"):
                a = [getattr(p[0], metric) for p in pairs.values()]
                b = [getattr(p[1], metric) for p in pairs.values()]
                res = agreement.report(a, b)
                out[metric] = {"value": None if res.kappa is None else f"{res.kappa:.3f}", "n": res.n,
                               "key": {"too_few": "tch.k.too_few", "undefined": "tch.k.undefined"}.get(res.reason)}
                if store and res.kappa is not None:
                    c.execute(text("INSERT INTO kappa_report (batch, metric, kappa, n) VALUES (:b, :m, :k, :n)"),
                              {"b": batch, "m": metric, "k": res.kappa, "n": res.n})
            disputed = sorted(str(k) for k, p in pairs.items()
                              if p[0].category_ok != p[1].category_ok or p[0].decision != p[1].decision)
            names = dict(c.execute(text("SELECT CAST(id AS text), rule_id FROM rule_version WHERE CAST(id AS text) = "
                                        "ANY(:ids)"), {"ids": disputed}).all()) if disputed else {}
            return {"metrics": out, "pairs": len(pairs), "disputed": [names.get(d, d) for d in disputed]}


# ---------------------------------------------------------------- helpers


def _require_teacher(c, teacher_id):
    if teacher_id is None or c.execute(text("SELECT role FROM learner WHERE id = :t"),
                                       {"t": teacher_id}).scalar() != "teacher":
        raise ReviewRefused("err.forbidden")


def _latest(c, rule_id, lock=False):
    if lock:  # versions are immutable (no row locks for this role): serialise decisions on one rule instead
        c.execute(text("SELECT pg_advisory_xact_lock(hashtext(:r))"), {"r": f"rule:{rule_id}"})
    return c.execute(text(
        "SELECT *, jsonb_array_length(validation_issues) AS issues FROM rule_version WHERE rule_id = :r "
        "ORDER BY version DESC LIMIT 1"), {"r": rule_id}).first()


def _reviews(c, version_id):
    return [R.Review(r.reviewer_id, r.language, r.decision, r.category_ok, r.native_speaker) for r in c.execute(text(
        "SELECT reviewer_id, language, decision, category_ok, native_speaker FROM rule_review WHERE rule_version_id = :v "
        "AND round = :n ORDER BY created_at"), {"v": version_id, "n": ROUND})]


def _decide(c, version_id):
    return R.decide(_reviews(c, version_id))


def _count(c, version_id) -> int:
    return c.execute(text("SELECT count(*) FROM rule_review WHERE rule_version_id = :v"), {"v": version_id}).scalar_one()


def _marked(item) -> dict:
    """The wrong sentence split around the planted error's span (offsets into the normalised sentence)."""
    from setu.content.schema import normalise_sentence

    d = dict(item._mapping)
    wrong = normalise_sentence(item.wrong_form or "")
    span = item.one_error_span
    d["before"], d["error"], d["after"] = ((wrong[:span[0]], wrong[span[0]:span[1]], wrong[span[1]:]) if span
                                           else (wrong, "", ""))
    return d


def _ledger(c, actor, rule_id, step, extra):
    c.execute(text("INSERT INTO event_ledger (actor, event_type, payload) VALUES (:a, 'content_reviewed', "
                   "CAST(:p AS jsonb))"),
              {"a": actor, "p": json.dumps({"target_kind": "rule_version", "target_id": rule_id, "step": step, **extra},
                                           ensure_ascii=False, sort_keys=True)})


def _new_version(c, v, actor, *, validity=None, lifecycle, teacher_approved=None, approvals=None, note):
    new_id = c.execute(text(
        f"INSERT INTO rule_version ({RULE_COPY}, version, validity, lifecycle, teacher_approved, speaker_approvals, "
        f"reviewed_at, supersedes_version, change_note) SELECT {RULE_COPY}, version + 1, :validity, :lifecycle, :ta, "
        f"CAST(:ap AS jsonb), now(), id, :note FROM rule_version WHERE id = :v RETURNING id"),
        {"v": v.id, "validity": validity or v.validity, "lifecycle": lifecycle,
         "ta": v.teacher_approved if teacher_approved is None else teacher_approved,
         "ap": json.dumps(v.speaker_approvals if approvals is None else approvals), "note": note}).scalar_one()
    _ledger(c, actor, v.rule_id, lifecycle, {"rule_version_id": str(new_id), "validity": validity or v.validity})
    return new_id


def _approve_items(c, rule_id, rule_version_id):
    """A new approved version of each item without open issues, pointing at the verified rule version."""
    latest = c.execute(text(
        "SELECT DISTINCT ON (iv.item_id) iv.id, iv.version, jsonb_array_length(iv.validation_issues) AS issues "
        "FROM item_version iv JOIN item i ON i.id = iv.item_id WHERE i.rule_id = :r ORDER BY iv.item_id, iv.version DESC"),
        {"r": rule_id}).all()
    for it in latest:
        if it.issues:
            continue
        new_id = c.execute(text(
            f"INSERT INTO item_version ({ITEM_COPY}, version, rule_version_id, review_status) SELECT {ITEM_COPY}, "
            f"version + 1, :rv, 'approved' FROM item_version WHERE id = :i RETURNING id"),
            {"rv": rule_version_id, "i": it.id}).scalar_one()
        c.execute(text("INSERT INTO accepted_variant (item_version_id, form, register, region, status, approvals, "
                       "provenance) SELECT :n, form, register, region, status, approvals, provenance FROM accepted_variant "
                       "WHERE item_version_id = :o"), {"n": new_id, "o": it.id})
