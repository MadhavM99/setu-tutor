"""Database-side guarantees that do not fit in table definitions (E-01, E-02, data-model.md §3–4, §7).

- group roles (NOLOGIN), created idempotently because roles are cluster-wide;
- the append-only, hash-chained event ledger and `setu_verify_ledger()`;
- immutability of content versions and verdicts;
- `memory_aid` status state machine with immutable content columns;
- a rule version marked verified needs two *distinct* speakers of the rule's target language.
"""
from .grants import ROLES

CREATE_ROLES = [
    f"DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{r}') "
    f"THEN CREATE ROLE {r} NOLOGIN; END IF; END $$" for r in ROLES
]

LEDGER = [
    "CREATE SEQUENCE event_ledger_id_seq OWNED BY event_ledger.id",
    r"""
CREATE FUNCTION setu_ledger_hash(prev text, id bigint, ts timestamptz, actor text, event_type text, payload jsonb)
RETURNS text LANGUAGE sql IMMUTABLE AS $$
  SELECT encode(sha256(convert_to(
    prev || '|' || id::text || '|' ||
    to_char(ts AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US') || '|' ||
    actor || '|' || event_type || '|' || payload::text, 'UTF8')), 'hex')
$$""",
    r"""
CREATE FUNCTION setu_ledger_before_insert() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  last_hash text;
BEGIN
  -- Serialise appends so the chain has one order; the lock is held until commit.
  IF current_setting('transaction_isolation') <> 'read committed' THEN
    RAISE EXCEPTION 'event_ledger appends must run at READ COMMITTED (got %)',
      current_setting('transaction_isolation');
  END IF;
  PERFORM pg_advisory_xact_lock(hashtext('setu.event_ledger'));
  SELECT hash INTO last_hash FROM event_ledger ORDER BY id DESC LIMIT 1;
  NEW.id := nextval('event_ledger_id_seq');
  NEW.ts := clock_timestamp();
  NEW.prev_hash := coalesce(last_hash, repeat('0', 64));
  NEW.hash := setu_ledger_hash(NEW.prev_hash, NEW.id, NEW.ts, NEW.actor, NEW.event_type, NEW.payload);
  RETURN NEW;
END $$""",
    """
CREATE FUNCTION setu_ledger_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'event_ledger is append-only (% rejected)', TG_OP;
END $$""",
    r"""
CREATE FUNCTION setu_verify_ledger() RETURNS bigint LANGUAGE plpgsql STABLE AS $$
-- Returns the id of the first event whose hash or link does not verify, or NULL if the chain is intact.
DECLARE
  r record;
  expected_prev text := repeat('0', 64);
BEGIN
  FOR r IN SELECT * FROM event_ledger ORDER BY id LOOP
    IF r.prev_hash <> expected_prev
       OR r.hash <> setu_ledger_hash(r.prev_hash, r.id, r.ts, r.actor, r.event_type, r.payload) THEN
      RETURN r.id;
    END IF;
    expected_prev := r.hash;
  END LOOP;
  RETURN NULL;
END $$""",
    (
        "CREATE TRIGGER event_ledger_chain BEFORE INSERT ON event_ledger "
        "FOR EACH ROW EXECUTE FUNCTION setu_ledger_before_insert()"
    ),
    (
        "CREATE TRIGGER event_ledger_no_update_delete BEFORE UPDATE OR DELETE ON event_ledger "
        "FOR EACH ROW EXECUTE FUNCTION setu_ledger_append_only()"
    ),
    (
        "CREATE TRIGGER event_ledger_no_truncate BEFORE TRUNCATE ON event_ledger "
        "FOR EACH STATEMENT EXECUTE FUNCTION setu_ledger_append_only()"
    ),
]

IMMUTABLE_TABLES = ("rule_version", "item_version", "hint", "verdict")

IMMUTABILITY = [
    """
CREATE FUNCTION setu_forbid_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION '% is immutable (% rejected); insert a new version instead', TG_TABLE_NAME, TG_OP;
END $$""",
    *[
        f"CREATE TRIGGER {t}_immutable BEFORE UPDATE OR DELETE ON {t} "
        f"FOR EACH ROW EXECUTE FUNCTION setu_forbid_mutation()"
        for t in IMMUTABLE_TABLES
    ],
    *[
        f"CREATE TRIGGER {t}_no_truncate BEFORE TRUNCATE ON {t} "
        f"FOR EACH STATEMENT EXECUTE FUNCTION setu_forbid_mutation()"
        for t in IMMUTABLE_TABLES
    ],
]

MEMORY_AID = [
    """
CREATE FUNCTION setu_memory_aid_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'memory_aid is immutable (DELETE rejected); retire it with a reason instead';
  END IF;
  -- Content columns never change; a correction is a new version.
  IF (to_jsonb(NEW) - 'review_status' - 'reviewers' - 'retired_reason')
     IS DISTINCT FROM (to_jsonb(OLD) - 'review_status' - 'reviewers' - 'retired_reason') THEN
    RAISE EXCEPTION 'memory_aid content is immutable; insert a new version instead';
  END IF;
  IF NEW.review_status IS DISTINCT FROM OLD.review_status AND NOT (
       (OLD.review_status = 'draft'     AND NEW.review_status IN ('in_review', 'rejected'))
    OR (OLD.review_status = 'in_review' AND NEW.review_status IN ('approved', 'rejected', 'draft'))
    OR (OLD.review_status = 'approved'  AND NEW.review_status = 'retired')
  ) THEN
    RAISE EXCEPTION 'memory_aid review_status transition % -> % is not allowed',
      OLD.review_status, NEW.review_status;
  END IF;
  RETURN NEW;
END $$""",
    (
        "CREATE TRIGGER memory_aid_guard BEFORE UPDATE OR DELETE ON memory_aid "
        "FOR EACH ROW EXECUTE FUNCTION setu_memory_aid_guard()"
    ),
]

RULE_APPROVALS = [
    """
CREATE FUNCTION setu_rule_version_speakers() RETURNS trigger LANGUAGE plpgsql AS $$
-- validity = verified needs two distinct native speakers of the rule's target language
-- (Telugu for HI->TE, Hindi for TE->HI); the CHECK constraint alone only counts entries.
DECLARE
  target_lang text;
  speakers int;
BEGIN
  IF NEW.validity <> 'verified' THEN
    RETURN NEW;
  END IF;
  SELECT CASE direction WHEN 'HI->TE' THEN 'te' ELSE 'hi' END INTO target_lang FROM rule WHERE id = NEW.rule_id;
  SELECT count(DISTINCT a->>'reviewer') INTO speakers
    FROM jsonb_array_elements(NEW.speaker_approvals) a
   WHERE a->>'lang' = target_lang AND coalesce(a->>'reviewer', '') <> '';
  IF speakers < 2 THEN
    RAISE EXCEPTION 'rule % v%: verified needs two distinct % speaker approvals (found %)',
      NEW.rule_id, NEW.version, target_lang, speakers;
  END IF;
  RETURN NEW;
END $$""",
    (
        "CREATE TRIGGER rule_version_speakers BEFORE INSERT ON rule_version "
        "FOR EACH ROW EXECUTE FUNCTION setu_rule_version_speakers()"
    ),
]

UPGRADE = [*LEDGER, *IMMUTABILITY, *MEMORY_AID, *RULE_APPROVALS]

DOWNGRADE_FUNCTIONS = [
    "DROP FUNCTION IF EXISTS setu_rule_version_speakers() CASCADE",
    "DROP FUNCTION IF EXISTS setu_memory_aid_guard() CASCADE",
    "DROP FUNCTION IF EXISTS setu_forbid_mutation() CASCADE",
    "DROP FUNCTION IF EXISTS setu_verify_ledger() CASCADE",
    "DROP FUNCTION IF EXISTS setu_ledger_append_only() CASCADE",
    "DROP FUNCTION IF EXISTS setu_ledger_before_insert() CASCADE",
    "DROP FUNCTION IF EXISTS setu_ledger_hash(text, bigint, timestamptz, text, text, jsonb) CASCADE",
]

# ---------------------------------------------------------------- migration 0002 (slice 1.3)

CLASSMATE_GUARD = [
    r"""
CREATE FUNCTION setu_classmate_guard() RETURNS trigger LANGUAGE plpgsql AS $$
-- Every change to what the classmate knows must be backed, in the database, by the evidence the paper allows
-- (P8b-01): unknown -> taught only after a checked correct fix of a planted error of that rule by that learner
-- (or a teacher resolution settling such a fix as correct); taught -> forgotten only by the scheduler when
-- predicted recall < 0.5. Versions move by exactly one, and old evidence cannot be replayed.
DECLARE
  ev event_ledger%ROWTYPE;
  evidence_at timestamptz;
  previous_change_at timestamptz;
BEGIN
  IF TG_OP = 'UPDATE' THEN
    IF NEW.learner_id <> OLD.learner_id OR NEW.rule_id <> OLD.rule_id THEN
      RAISE EXCEPTION 'classmate state: learner and rule cannot change';
    END IF;
    IF NEW.state = OLD.state THEN
      RAISE EXCEPTION 'classmate state: % -> % is not a transition', OLD.state, NEW.state;
    END IF;
    IF NEW.state_version <> OLD.state_version + 1 THEN
      RAISE EXCEPTION 'classmate state: version must move from % to %', OLD.state_version, OLD.state_version + 1;
    END IF;
  ELSIF NEW.state_version <> 1 THEN
    RAISE EXCEPTION 'classmate state: a new row starts at version 1';
  END IF;

  SELECT * INTO ev FROM event_ledger WHERE id = NEW.last_event_id;
  IF NOT FOUND OR ev.payload->>'learner_id' IS DISTINCT FROM NEW.learner_id::text
     OR ev.payload->>'rule_id' IS DISTINCT FROM NEW.rule_id THEN
    RAISE EXCEPTION 'classmate state: event % does not describe this learner and rule', NEW.last_event_id;
  END IF;

  IF NEW.state = 'taught' THEN
    IF ev.event_type <> 'classmate_taught' THEN
      RAISE EXCEPTION 'classmate state: teaching needs a classmate_taught event, got %', ev.event_type;
    END IF;
    IF ev.payload ? 'verdict_id' AND ev.actor = 'checker' THEN
      SELECT v.created_at INTO evidence_at
        FROM verdict v
        JOIN attempt a ON a.id = v.attempt_id
        JOIN exchange e ON e.id = a.exchange_id
        JOIN session s ON s.id = e.session_id
        JOIN rule_version rv ON rv.id = e.rule_version_id
       WHERE v.id = (ev.payload->>'verdict_id')::uuid
         AND v.outcome = 'correct' AND v.kind = 'fix'
         AND e.kind = 'correction' AND e.planted
         AND s.learner_id = NEW.learner_id AND rv.rule_id = NEW.rule_id;
    ELSIF ev.payload ? 'resolution_id' AND ev.actor LIKE 'teacher:%' THEN
      SELECT tr.resolved_at INTO evidence_at
        FROM teacher_resolution tr
        JOIN teacher_queue_item q ON q.id = tr.queue_item_id
        JOIN verdict v ON v.id = q.verdict_id
        JOIN attempt a ON a.id = v.attempt_id
        JOIN exchange e ON e.id = a.exchange_id
        JOIN session s ON s.id = e.session_id
        JOIN rule_version rv ON rv.id = e.rule_version_id
       WHERE tr.id = (ev.payload->>'resolution_id')::uuid
         AND tr.outcome = 'correct' AND ev.actor = 'teacher:' || tr.teacher_id::text
         AND v.kind = 'fix' AND e.kind = 'correction' AND e.planted
         AND s.learner_id = NEW.learner_id AND rv.rule_id = NEW.rule_id;
    END IF;
    IF evidence_at IS NULL THEN
      RAISE EXCEPTION 'classmate state: no checked correct fix of rule % by this learner backs event %',
        NEW.rule_id, NEW.last_event_id;
    END IF;
    IF TG_OP = 'UPDATE' THEN
      SELECT ts INTO previous_change_at FROM event_ledger WHERE id = OLD.last_event_id;
      IF evidence_at <= previous_change_at THEN
        RAISE EXCEPTION 'classmate state: stale evidence (older than the last change to this rule)';
      END IF;
    END IF;
  ELSIF NEW.state = 'forgotten' THEN
    IF TG_OP <> 'UPDATE' OR OLD.state <> 'taught' THEN
      RAISE EXCEPTION 'classmate state: only a taught rule can be forgotten';
    END IF;
    IF ev.event_type <> 'classmate_forgot' OR ev.actor <> 'scheduler'
       OR coalesce((ev.payload->>'predicted_recall')::float8, 1) >= 0.5 THEN
      RAISE EXCEPTION 'classmate state: forgetting needs a scheduler event with predicted recall below 0.5';
    END IF;
  ELSE
    IF TG_OP <> 'INSERT' OR ev.event_type <> 'classmate_initialised' THEN
      RAISE EXCEPTION 'classmate state: unknown is only an initial state';
    END IF;
  END IF;
  RETURN NEW;
END $$""",
    (
        "CREATE TRIGGER classmate_rule_state_guard BEFORE INSERT OR UPDATE ON classmate_rule_state "
        "FOR EACH ROW EXECUTE FUNCTION setu_classmate_guard()"
    ),
    (
        "CREATE TRIGGER classmate_rule_state_no_delete BEFORE DELETE ON classmate_rule_state "
        "FOR EACH ROW EXECUTE FUNCTION setu_forbid_mutation()"
    ),
]

CLASSMATE_GUARD_DOWN = [
    "DROP TRIGGER IF EXISTS classmate_rule_state_no_delete ON classmate_rule_state",
    "DROP TRIGGER IF EXISTS classmate_rule_state_guard ON classmate_rule_state",
    "DROP FUNCTION IF EXISTS setu_classmate_guard()",
]

# ---------------------------------------------------------------- migration 0003 (slice 1.4)

CONTENT_FUNCTIONS = [
    r"""
CREATE FUNCTION setu_no_latin(t text) RETURNS boolean LANGUAGE sql IMMUTABLE AS $fn$
  -- Learner-facing text is Devanagari or Telugu; Latin script never reaches learners (X-NOENG).
  SELECT t IS NULL OR t !~ '[A-Za-z]'
$fn$""",
    r"""
CREATE FUNCTION setu_patterns_anchored(ps text[]) RETURNS boolean LANGUAGE sql IMMUTABLE AS $fn$
  -- Backstop for the Python validator: every pattern starts with ^ and ends with an unescaped $.
  SELECT coalesce(bool_and(p ~ '^\^' AND p ~ '\$$' AND p !~ '\\\$$'), true) FROM unnest(ps) AS p
$fn$""",
]

# Learner-visible content: only the newest version of each rule, and only if it is verified, active and
# teacher-approved; items only if approved with no open validation issues and their rule is visible.
LEARNER_VIEWS = [
    """
CREATE VIEW learner_rule_version AS
SELECT rv.* FROM rule_version rv
 WHERE rv.version = (SELECT max(x.version) FROM rule_version x WHERE x.rule_id = rv.rule_id)
   AND rv.lifecycle = 'active' AND rv.validity = 'verified' AND rv.teacher_approved""",
    """
CREATE VIEW learner_item_version AS
SELECT iv.* FROM item_version iv JOIN item i ON i.id = iv.item_id
 WHERE iv.version = (SELECT max(x.version) FROM item_version x WHERE x.item_id = iv.item_id)
   AND iv.review_status = 'approved' AND iv.validation_issues = '[]'::jsonb
   AND EXISTS (SELECT 1 FROM learner_rule_version r WHERE r.rule_id = i.rule_id)""",
    """
CREATE VIEW learner_accepted_variant AS
SELECT av.* FROM accepted_variant av JOIN learner_item_version iv ON iv.id = av.item_version_id
 WHERE av.status = 'approved'""",
    """
CREATE VIEW learner_hint AS
SELECT h.* FROM hint h JOIN learner_rule_version r ON r.id = h.rule_version_id
 WHERE h.status = 'approved' AND h.validated_no_answer""",
    "CREATE VIEW learner_lexeme AS SELECT * FROM lexeme WHERE review_status = 'approved'",
    "CREATE VIEW learner_scene AS SELECT * FROM scene WHERE review_status = 'approved'",
    """
CREATE VIEW learner_scene_line AS
SELECT l.* FROM scene_line l JOIN learner_scene s ON s.id = l.scene_id WHERE l.review_status = 'approved'""",
    "CREATE VIEW learner_own_task AS SELECT * FROM own_task WHERE review_status = 'approved'",
    """
CREATE VIEW learner_memory_aid AS
SELECT m.* FROM memory_aid m
 WHERE m.review_status = 'approved'
   AND (m.visual_asset_id IS NULL OR EXISTS (
        SELECT 1 FROM visual_asset v WHERE v.id = m.visual_asset_id AND v.review_status = 'approved'))""",
]

LEARNER_VIEWS_DOWN = [
    f"DROP VIEW IF EXISTS {v}" for v in (
        "learner_memory_aid", "learner_own_task", "learner_scene_line", "learner_scene", "learner_lexeme",
        "learner_hint", "learner_accepted_variant", "learner_item_version", "learner_rule_version")
]
CONTENT_FUNCTIONS_DOWN = ["DROP FUNCTION IF EXISTS setu_patterns_anchored(text[])",
                          "DROP FUNCTION IF EXISTS setu_no_latin(text)"]
