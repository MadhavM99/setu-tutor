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
