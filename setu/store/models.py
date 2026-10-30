"""Relational schema (docs/specs/data-model.md).

Content versions are immutable, learning state is written only by OutcomeWriter (enforced by the grants in
`grants.py`), and every event goes to the append-only `event_ledger` (triggers in `sql.py`).
Closed value sets are CHECK constraints so the database rejects anything outside them.
"""
from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    Numeric,
    PrimaryKeyConstraint,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import DeclarativeBase

NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)


def one_of(column, *values):
    quoted = ", ".join("'" + v.replace("'", "''") + "'" for v in values)
    return CheckConstraint(f"{column} IN ({quoted})", name=f"{column}_values")


def uuid_pk():
    return Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))


def now():
    return Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))


def fk(target, nullable=False, **kw):
    return Column(ForeignKey(target), nullable=nullable, **kw)


DIRECTIONS = ("HI->TE", "TE->HI")
BANDS = ("L0", "L1", "L2", "L3", "L4", "L5")
MODALITIES = ("REC", "RCL", "RD", "LS", "SP", "EX", "PR")
REVIEW = ("draft", "in_review", "approved", "rejected")
CUE_LEVEL = "cue_level BETWEEN 0 AND 3"

# ---------------------------------------------------------------- identity and consent


class Learner(Base):
    __tablename__ = "learner"
    id = uuid_pk()
    handle = Column(Text, nullable=False, unique=True)
    passphrase_hash = Column(Text, nullable=False)
    l1 = Column(Text, nullable=False)
    l2 = Column(Text, nullable=False)
    direction = Column(Text, nullable=False)
    role = Column(Text, nullable=False, server_default="learner")
    created_at = now()
    cohort = Column(Text)
    romanisation_enabled = Column(Boolean, nullable=False, server_default=text("false"))
    __table_args__ = (
        one_of("l1", "hi", "te"),
        one_of("l2", "hi", "te"),
        CheckConstraint("l1 <> l2", name="l1_differs_from_l2"),
        one_of("direction", *DIRECTIONS),
        one_of("role", "learner", "teacher", "researcher", "admin"),
    )


class Consent(Base):
    __tablename__ = "consent"
    id = uuid_pk()
    learner_id = fk("learner.id")
    form_version = Column(Text, nullable=False)
    signed_at = now()
    scope = Column(ARRAY(Text), nullable=False)
    withdrawn_at = Column(TIMESTAMP(timezone=True))
    __table_args__ = (
        CheckConstraint("scope <@ ARRAY['pilot','audio','writing_upload','data_sharing']::text[]",
                        name="scope_values"),
    )


class Background(Base):
    __tablename__ = "background"
    learner_id = Column(ForeignKey("learner.id"), primary_key=True)
    answers = Column(JSONB, nullable=False)


# ---------------------------------------------------------------- data sources


class DataSource(Base):
    __tablename__ = "data_source"
    id = Column(Text, primary_key=True)
    name = Column(Text, nullable=False)
    use = Column(Text, nullable=False)
    licence = Column(Text)
    status = Column(Text, nullable=False, server_default="to-check")
    notes = Column(Text)
    __table_args__ = (one_of("status", "verified", "to-check", "n/a"),)


# ---------------------------------------------------------------- skills and words


class Skill(Base):
    __tablename__ = "skill"
    id = Column(Text, primary_key=True)
    band = Column(Text, nullable=False)
    family = Column(Text, nullable=False)
    target = Column(Text, nullable=False)
    modality = Column(Text, nullable=False)
    direction = Column(Text, nullable=False)
    content_ref = Column(Text)
    active = Column(Boolean, nullable=False, server_default=text("true"))
    __table_args__ = (one_of("band", *BANDS), one_of("modality", *MODALITIES), one_of("direction", *DIRECTIONS))


class SkillPrereq(Base):
    __tablename__ = "skill_prereq"
    skill_id = Column(ForeignKey("skill.id"), nullable=False)
    requires_id = Column(ForeignKey("skill.id"), nullable=False)
    __table_args__ = (
        PrimaryKeyConstraint("skill_id", "requires_id"),
        CheckConstraint("skill_id <> requires_id", name="not_self"),
    )


class EventLedger(Base):
    __tablename__ = "event_ledger"
    # id, ts, prev_hash and hash are set by the BEFORE INSERT trigger (sql.py), whatever the client sends.
    id = Column(BigInteger, primary_key=True, autoincrement=False)
    ts = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("clock_timestamp()"))
    actor = Column(Text, nullable=False)
    event_type = Column(Text, nullable=False)
    payload = Column(JSONB, nullable=False)
    prev_hash = Column(Text, nullable=False)
    hash = Column(Text, nullable=False, unique=True)
    __table_args__ = (
        CheckConstraint("actor IN ('checker', 'scheduler') OR actor ~ '^teacher:[A-Za-z0-9_-]+$'",
                        name="actor_values"),
    )


class LearnerSkillState(Base):
    __tablename__ = "learner_skill_state"
    learner_id = Column(ForeignKey("learner.id"), nullable=False)
    skill_id = Column(ForeignKey("skill.id"), nullable=False)
    mastery_mean = Column(Float, nullable=False, server_default=text("0"))
    mastery_lo = Column(Float, nullable=False, server_default=text("0"))
    mastery_hi = Column(Float, nullable=False, server_default=text("1"))
    evidence_n = Column(Integer, nullable=False, server_default=text("0"))
    distinct_items = Column(Integer, nullable=False, server_default=text("0"))
    distinct_task_types = Column(Integer, nullable=False, server_default=text("0"))
    distinct_days = Column(Integer, nullable=False, server_default=text("0"))
    cuefree_successes = Column(Integer, nullable=False, server_default=text("0"))
    production_successes = Column(Integer, nullable=False, server_default=text("0"))
    last_practised = Column(TIMESTAMP(timezone=True))
    due_at = Column(TIMESTAMP(timezone=True))
    common_errors = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    status = Column(Text, nullable=False, server_default="locked")
    source = Column(Text, nullable=False, server_default="observed")
    updated_by_event = fk("event_ledger.id", nullable=True)
    __table_args__ = (
        PrimaryKeyConstraint("learner_id", "skill_id"),
        CheckConstraint("0 <= mastery_lo AND mastery_lo <= mastery_mean AND mastery_mean <= mastery_hi "
                        "AND mastery_hi <= 1", name="mastery_interval"),
        CheckConstraint("evidence_n >= 0 AND distinct_items >= 0 AND distinct_task_types >= 0 "
                        "AND distinct_days >= 0 AND cuefree_successes >= 0 AND production_successes >= 0",
                        name="counts_non_negative"),
        one_of("status", "locked", "available", "learning", "mastered", "due", "relearning", "placed"),
        one_of("source", "observed", "placed"),
    )


class AudioAsset(Base):
    __tablename__ = "audio_asset"
    id = uuid_pk()
    uri = Column(Text, nullable=False)
    kind = Column(Text, nullable=False)
    speaker_consent_ref = Column(Text)
    rights = Column(Text)
    review_status = Column(Text, nullable=False, server_default="draft")
    __table_args__ = (
        one_of("kind", "native_recording", "tts_reviewed"),
        one_of("review_status", *REVIEW, "retired"),
        CheckConstraint("review_status <> 'approved' OR rights IS NOT NULL", name="approved_has_rights"),
        CheckConstraint("kind <> 'native_recording' OR review_status <> 'approved' "
                        "OR speaker_consent_ref IS NOT NULL", name="recording_has_consent"),
    )


class Lexeme(Base):
    __tablename__ = "lexeme"
    id = Column(Text, primary_key=True)
    telugu = Column(Text, nullable=False)
    hindi_gloss = Column(Text, nullable=False)
    pos = Column(Text)
    freq_rank = Column(Integer)
    freq_source = Column(Text)
    cognate_of = Column(Text)
    false_friend = Column(Boolean, nullable=False, server_default=text("false"))
    false_friend_note_hi = Column(Text)
    audio_asset_id = fk("audio_asset.id", nullable=True)
    source_id = fk("data_source.id", nullable=True)
    review_status = Column(Text, nullable=False, server_default="draft")
    __table_args__ = (
        one_of("review_status", *REVIEW),
        CheckConstraint("NOT false_friend OR false_friend_note_hi IS NOT NULL", name="false_friend_has_note"),
    )


class LearnerLexemeCard(Base):
    """FSRS card per (learner, discrete item, modality). Discrete items: letters, akshara, lexemes, chunks."""

    __tablename__ = "learner_lexeme_card"
    id = uuid_pk()
    learner_id = fk("learner.id")
    card_kind = Column(Text, nullable=False)
    card_ref = Column(Text, nullable=False)
    modality = Column(Text, nullable=False)
    stability = Column(Float)
    difficulty = Column(Float)
    due = Column(TIMESTAMP(timezone=True))
    last_review = Column(TIMESTAMP(timezone=True))
    reps = Column(Integer, nullable=False, server_default=text("0"))
    lapses = Column(Integer, nullable=False, server_default=text("0"))
    fsrs_version = Column(Text)
    __table_args__ = (
        UniqueConstraint("learner_id", "card_kind", "card_ref", "modality", name="uq_learner_lexeme_card_key"),
        one_of("card_kind", "letter", "akshara", "lexeme", "chunk"),
        one_of("modality", *MODALITIES),
    )


# ---------------------------------------------------------------- rules and items


class Rule(Base):
    __tablename__ = "rule"
    id = Column(Text, primary_key=True)
    direction = Column(Text, nullable=False)
    contrast_area = Column(Text, nullable=False)
    created_at = now()
    __table_args__ = (one_of("direction", *DIRECTIONS),)


class RuleVersion(Base):
    __tablename__ = "rule_version"
    id = uuid_pk()
    rule_id = fk("rule.id")
    version = Column(Integer, nullable=False)
    title_hi = Column(Text, nullable=False)
    l1_explanation_hi = Column(Text, nullable=False)
    concept_key = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    band = Column(Text, nullable=False)
    target_skill_id = fk("skill.id", nullable=True)
    validity = Column(Text, nullable=False)
    learner_evidence = Column(Text, nullable=False)
    lifecycle = Column(Text, nullable=False)
    teacher_approved = Column(Boolean, nullable=False, server_default=text("false"))
    sources = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    licence = Column(Text)
    reviewers = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    reviewed_at = Column(TIMESTAMP(timezone=True))
    speaker_approvals = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    region_register_notes = Column(Text)
    opportunities = Column(Integer, nullable=False, server_default=text("0"))
    observed_errors = Column(Integer, nullable=False, server_default=text("0"))
    supersedes_version = fk("rule_version.id", nullable=True)
    change_note = Column(Text)
    created_at = now()
    __table_args__ = (
        UniqueConstraint("rule_id", "version", name="uq_rule_version_rule_id_version"),
        CheckConstraint("version >= 1", name="version_positive"),
        one_of("band", *BANDS),
        one_of("validity", "verified", "uncertain", "rejected"),
        one_of("learner_evidence", "model_predicted", "predicted", "proxy", "observed", "replicated"),
        one_of("lifecycle", "draft", "review", "verified", "active", "deprecated", "rejected"),
        CheckConstraint("jsonb_typeof(speaker_approvals) = 'array'", name="approvals_is_array"),
        # data-model.md §7, verbatim
        CheckConstraint("validity <> 'verified' OR jsonb_array_length(speaker_approvals) >= 2",
                        name="verified_needs_two_approvals"),
        CheckConstraint("lifecycle <> 'active' OR (validity = 'verified' AND teacher_approved)",
                        name="active_needs_verified_and_teacher"),
        # data-model.md §3: verified (and therefore active) lifecycle requires validity = verified
        CheckConstraint("lifecycle NOT IN ('verified', 'active') OR validity = 'verified'",
                        name="lifecycle_verified_needs_validity"),
        CheckConstraint("opportunities >= 0 AND observed_errors >= 0 AND observed_errors <= opportunities",
                        name="error_rate_counts"),
    )


class Item(Base):
    __tablename__ = "item"
    id = Column(Text, primary_key=True)
    rule_id = fk("rule.id")
    __table_args__ = (CheckConstraint("id ~ '^(HI-TE|TE-HI)-[0-9]{3}-[a-z]$'", name="item_id_pattern"),)


class ItemVersion(Base):
    __tablename__ = "item_version"
    id = uuid_pk()
    item_id = fk("item.id")
    version = Column(Integer, nullable=False)
    rule_version_id = fk("rule_version.id")
    template = Column(Text)
    hindi_meaning = Column(Text)
    wrong_form = Column(Text)
    one_error_span = Column(ARRAY(Integer))
    correct_form = Column(Text, nullable=False)
    no_error_equivalent = Column(Text)
    wrong_patterns = Column(ARRAY(Text), nullable=False, server_default=text("'{}'::text[]"))
    accept_patterns = Column(ARRAY(Text), nullable=False, server_default=text("'{}'::text[]"))
    vocab_prereqs = Column(ARRAY(Text), nullable=False, server_default=text("'{}'::text[]"))
    allowed_target_forms = Column(ARRAY(Text), nullable=False, server_default=text("'{}'::text[]"))
    analyser_requirements = Column(JSONB)
    band = Column(Text)
    band_reason = Column(Text)
    leveler_version = Column(Text)
    pool = Column(Text, nullable=False)
    review_status = Column(Text, nullable=False, server_default="draft")
    created_at = now()
    __table_args__ = (
        UniqueConstraint("item_id", "version", name="uq_item_version_item_id_version"),
        CheckConstraint("version >= 1", name="version_positive"),
        CheckConstraint("one_error_span IS NULL OR (cardinality(one_error_span) = 2 "
                        "AND one_error_span[1] >= 0 AND one_error_span[1] < one_error_span[2])",
                        name="one_error_span_shape"),
        CheckConstraint("band IS NULL OR band IN ('L0','L1','L2','L3','L4','L5')", name="band_values"),
        one_of("pool", "practice", "test_heldout", "diagnostic"),
        one_of("review_status", *REVIEW),
    )


class AcceptedVariant(Base):
    __tablename__ = "accepted_variant"
    id = uuid_pk()
    item_version_id = fk("item_version.id")
    form = Column(Text, nullable=False)
    register = Column(Text, nullable=False)
    region = Column(Text)
    status = Column(Text, nullable=False, server_default="proposed")
    approvals = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    __table_args__ = (
        one_of("register", "written", "spoken"),
        one_of("status", "proposed", "approved", "rejected"),
        CheckConstraint("jsonb_typeof(approvals) = 'array'", name="approvals_is_array"),
        CheckConstraint("status <> 'approved' OR jsonb_array_length(approvals) >= 2", name="approved_needs_two"),
    )


class RuleReview(Base):
    __tablename__ = "rule_review"
    id = uuid_pk()
    rule_version_id = fk("rule_version.id")
    reviewer_id = Column(Text, nullable=False)
    language = Column(Text, nullable=False)
    acceptable_natural = Column(Integer, nullable=False)
    category_ok = Column(Boolean, nullable=False)
    explanation_ok = Column(Integer, nullable=False)
    band_fit = Column(Text, nullable=False)
    confidence = Column(Integer, nullable=False)
    comments_hi = Column(Text)
    round = Column(Integer, nullable=False, server_default=text("1"))
    created_at = now()
    __table_args__ = (
        UniqueConstraint("rule_version_id", "reviewer_id", "round", name="uq_rule_review_once_per_round"),
        one_of("language", "hi", "te"),
        CheckConstraint("acceptable_natural BETWEEN 1 AND 5 AND explanation_ok BETWEEN 1 AND 5 "
                        "AND confidence BETWEEN 1 AND 5", name="likert_1_to_5"),
        one_of("band_fit", *BANDS),
        CheckConstraint("round BETWEEN 1 AND 3", name="round_1_to_3"),
    )


class KappaReport(Base):
    __tablename__ = "kappa_report"
    id = uuid_pk()
    batch = Column(Text, nullable=False)
    metric = Column(Text, nullable=False)
    kappa = Column(Float)
    n = Column(Integer, nullable=False)
    computed_at = now()


class Hint(Base):
    __tablename__ = "hint"
    id = uuid_pk()
    rule_version_id = fk("rule_version.id")
    type = Column(Text, nullable=False)
    text_hi = Column(Text, nullable=False)
    status = Column(Text, nullable=False, server_default="draft")
    validated_no_answer = Column(Boolean, nullable=False, server_default=text("false"))
    __table_args__ = (
        one_of("type", "recast", "l1_rule", "contrast"),
        one_of("status", *REVIEW),
        CheckConstraint("status <> 'approved' OR validated_no_answer", name="approved_hint_validated"),
    )


class Scene(Base):
    __tablename__ = "scene"
    id = Column(Text, primary_key=True)
    title_hi = Column(Text, nullable=False)
    setup_hi = Column(Text, nullable=False)
    review_status = Column(Text, nullable=False, server_default="draft")
    __table_args__ = (one_of("review_status", *REVIEW),)


class SceneLine(Base):
    __tablename__ = "scene_line"
    id = uuid_pk()
    scene_id = fk("scene.id")
    n = Column(Integer, nullable=False)
    speaker = Column(Text, nullable=False)
    telugu = Column(Text, nullable=False)
    expected_reply_frames = Column(ARRAY(Text), nullable=False, server_default=text("'{}'::text[]"))
    review_status = Column(Text, nullable=False, server_default="draft")
    __table_args__ = (
        UniqueConstraint("scene_id", "n", name="uq_scene_line_scene_id_n"),
        one_of("review_status", *REVIEW),
    )


class OwnTask(Base):
    __tablename__ = "own_task"
    id = uuid_pk()
    target_skill = fk("skill.id")
    goal_hi = Column(Text, nullable=False)
    frames = Column(ARRAY(Text), nullable=False)
    slot_lexicon = Column(ARRAY(Text), nullable=False, server_default=text("'{}'::text[]"))
    review_status = Column(Text, nullable=False, server_default="draft")
    __table_args__ = (one_of("review_status", *REVIEW),)


class ContentProposal(Base):
    __tablename__ = "content_proposal"
    id = uuid_pk()
    kind = Column(Text, nullable=False)
    payload = Column(JSONB, nullable=False)
    origin = Column(Text, nullable=False)
    evidence = Column(Text, nullable=False)
    status = Column(Text, nullable=False, server_default="open")
    created_at = now()
    __table_args__ = (
        one_of("kind", "rule", "variant", "span"),
        one_of("origin", "llm", "upload", "teacher", "typology"),
        one_of("evidence", "model_predicted", "predicted", "proxy", "observed", "replicated"),
        one_of("status", "open", "accepted", "rejected"),
        CheckConstraint("origin <> 'llm' OR evidence = 'model_predicted'", name="llm_is_model_predicted"),
    )


# ---------------------------------------------------------------- memory assistant (amendment A1)


class Concept(Base):
    __tablename__ = "concept"
    id = Column(Text, primary_key=True)
    kind = Column(Text, nullable=False)
    content_ref = Column(Text, nullable=False)
    fact_sheet = Column(JSONB, nullable=False)
    __table_args__ = (one_of("kind", "letter", "sound", "akshara", "lexeme", "false_friend", "rule", "chunk",
                             "scene"),)


class TechniquePolicy(Base):
    __tablename__ = "technique_policy"
    version = Column(Integer, nullable=False)
    unit_kind = Column(Text, nullable=False)
    technique = Column(Text, nullable=False)
    default_rank = Column(Integer, nullable=False)
    active = Column(Boolean, nullable=False, server_default=text("true"))
    __table_args__ = (PrimaryKeyConstraint("version", "unit_kind", "technique"),)


class VisualAsset(Base):
    __tablename__ = "visual_asset"
    id = uuid_pk()
    uri = Column(Text, nullable=False)
    sha256 = Column(Text, nullable=False)
    phash = Column(Text)
    prompt = Column(Text, nullable=False)
    negative_prompt = Column(Text)
    model = Column(Text, nullable=False)
    provider = Column(Text, nullable=False)
    seed = Column(BigInteger)
    ocr_result = Column(JSONB)
    ocr_text_found = Column(Boolean)
    safety_result = Column(JSONB)
    contrast_ok = Column(Boolean)
    review_status = Column(Text, nullable=False, server_default="draft")
    licence = Column(Text)
    alt_text_hi = Column(Text)
    created_at = now()
    __table_args__ = (
        one_of("provider", "self_hosted", "external_offline", "manual"),
        one_of("review_status", *REVIEW, "retired"),
        CheckConstraint("review_status <> 'approved' OR (ocr_text_found = false AND contrast_ok "
                        "AND alt_text_hi IS NOT NULL AND licence IS NOT NULL)", name="approved_is_checked"),
    )


class MemoryAid(Base):
    __tablename__ = "memory_aid"
    id = uuid_pk()
    concept_id = fk("concept.id")
    technique = Column(Text, nullable=False)
    version = Column(Integer, nullable=False)
    text_hi = Column(Text)
    telugu_spans = Column(ARRAY(Text), nullable=False, server_default=text("'{}'::text[]"))
    uses_facts = Column(ARRAY(Text), nullable=False, server_default=text("'{}'::text[]"))
    lures = Column(ARRAY(Text), nullable=False, server_default=text("'{}'::text[]"))
    visual_asset_id = fk("visual_asset.id", nullable=True)
    audio_asset_id = fk("audio_asset.id", nullable=True)
    audio_alt_hi_id = fk("audio_asset.id", nullable=True)
    alt_text_hi = Column(Text)
    generation = Column(JSONB, nullable=False, server_default=text("'{\"tool\": \"manual\"}'::jsonb"))
    validator_results = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    review_status = Column(Text, nullable=False, server_default="draft")
    reviewers = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    licence = Column(Text)
    provenance = Column(Text)
    retired_reason = Column(Text)
    supersedes = fk("memory_aid.id", nullable=True)
    created_at = now()
    __table_args__ = (
        UniqueConstraint("concept_id", "technique", "version", name="uq_memory_aid_version"),
        one_of("review_status", *REVIEW, "retired"),
        CheckConstraint("review_status <> 'retired' OR retired_reason IS NOT NULL", name="retired_has_reason"),
        CheckConstraint("visual_asset_id IS NULL OR review_status NOT IN ('approved') OR alt_text_hi IS NOT NULL",
                        name="visual_aid_has_alt_text"),
    )


class Session(Base):
    __tablename__ = "session"
    id = uuid_pk()
    learner_id = fk("learner.id")
    mode = Column(Text, nullable=False)
    config_snapshot = Column(JSONB, nullable=False)
    seed = Column(BigInteger, nullable=False)
    started_at = now()
    ended_at = Column(TIMESTAMP(timezone=True))
    time_on_task_s = Column(Integer)
    __table_args__ = (
        one_of("mode", "learn", "study_A", "study_B", "study_C", "study_M_A", "study_M_B", "study_M_C",
               "study_M_D", "diagnostic", "test_pre", "test_post", "test_delayed", "test_transfer",
               "test_day1", "test_day7", "test_day30"),
    )


class AidEvent(Base):
    __tablename__ = "aid_event"
    id = uuid_pk()
    learner_id = fk("learner.id")
    concept_id = fk("concept.id")
    memory_aid_id = fk("memory_aid.id", nullable=True)
    fallback_kind = Column(Text)
    event = Column(Text, nullable=False)
    recommended_by = Column(Text, nullable=False)
    rank = Column(Integer)
    exploration = Column(Boolean, nullable=False, server_default=text("false"))
    dwell_ms = Column(Integer)
    session_id = fk("session.id", nullable=True)
    ts = now()
    __table_args__ = (
        CheckConstraint("(memory_aid_id IS NULL) <> (fallback_kind IS NULL)", name="aid_or_fallback"),
        one_of("event", "presented", "selected", "used", "dismissed"),
        one_of("recommended_by", "policy", "teacher_model", "study_fixed"),
    )


class ConceptCueState(Base):
    __tablename__ = "concept_cue_state"
    learner_id = Column(ForeignKey("learner.id"), nullable=False)
    concept_id = Column(ForeignKey("concept.id"), nullable=False)
    cue_level = Column(Integer, nullable=False, server_default=text("3"))
    updated_by_event = fk("event_ledger.id")
    __table_args__ = (PrimaryKeyConstraint("learner_id", "concept_id"), CheckConstraint(CUE_LEVEL, name="cue_level"))


class TechniqueEffect(Base):
    __tablename__ = "technique_effect"
    id = uuid_pk()
    scope = Column(Text, nullable=False)
    learner_id = fk("learner.id", nullable=True)
    technique = Column(Text, nullable=False)
    alpha = Column(Float, nullable=False, server_default=text("1"))
    beta = Column(Float, nullable=False, server_default=text("1"))
    n = Column(Integer, nullable=False, server_default=text("0"))
    updated_at = now()
    __table_args__ = (
        UniqueConstraint("scope", "learner_id", "technique", name="uq_technique_effect_key",
                         postgresql_nulls_not_distinct=True),
        one_of("scope", "learner", "population"),
        CheckConstraint("(scope = 'population') = (learner_id IS NULL)", name="scope_matches_learner"),
        CheckConstraint("alpha > 0 AND beta > 0 AND n >= 0", name="beta_params"),
    )


class GenerationCost(Base):
    __tablename__ = "generation_cost"
    id = uuid_pk()
    batch_id = Column(Text, nullable=False)
    provider = Column(Text, nullable=False)
    model = Column(Text, nullable=False)
    units = Column(Float, nullable=False)
    cost = Column(Numeric(12, 4), nullable=False)
    ts = now()
    __table_args__ = (CheckConstraint("units >= 0 AND cost >= 0", name="non_negative"),)


# ---------------------------------------------------------------- sessions and outcomes


class Exchange(Base):
    __tablename__ = "exchange"
    id = uuid_pk()
    session_id = fk("session.id")
    kind = Column(Text, nullable=False)
    rule_version_id = fk("rule_version.id", nullable=True)
    item_version_id = fk("item_version.id", nullable=True)
    planted = Column(Boolean)
    shown_text = Column(Text)
    source = Column(Text, nullable=False)
    model_versions = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    prompt_version = Column(Text)
    leveler_version = Column(Text)
    tokenizer_version = Column(Text)
    tmr = Column(Float)
    created_at = now()
    __table_args__ = (
        one_of("kind", "correction", "no_error", "own", "review", "learn", "scene", "mirror"),
        one_of("source", "model", "bank", "template"),
        CheckConstraint("tmr IS NULL OR (tmr >= 0 AND tmr <= 1)", name="tmr_range"),
    )


class Attempt(Base):
    __tablename__ = "attempt"
    id = uuid_pk()
    exchange_id = fk("exchange.id")
    n = Column(Integer, nullable=False)
    raw_text = Column(Text, nullable=False)
    normalised_text = Column(Text)
    input_script = Column(Text)
    forgiveness_applied = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    aid_visible = Column(Boolean, nullable=False, server_default=text("false"))
    cue_level = Column(Integer, nullable=False, server_default=text("0"))
    aid_visible_before_answer = Column(Boolean, nullable=False, server_default=text("false"))
    hint_type = Column(Text)
    hint_id = fk("hint.id", nullable=True)
    after_reveal = Column(Boolean, nullable=False, server_default=text("false"))
    confidence = Column(Integer)
    latency_ms = Column(Integer)
    idempotency_key = Column(Text, nullable=False, unique=True)
    created_at = now()
    __table_args__ = (
        UniqueConstraint("exchange_id", "n", name="uq_attempt_exchange_id_n"),
        CheckConstraint("n >= 1", name="n_positive"),
        CheckConstraint(CUE_LEVEL, name="cue_level"),
        CheckConstraint("input_script IS NULL OR input_script IN ('telugu','devanagari','latin','mixed','none')",
                        name="input_script_values"),
        CheckConstraint("hint_type IS NULL OR hint_type IN ('recast','l1_rule','contrast','generic')",
                        name="hint_type_values"),
        CheckConstraint("confidence IS NULL OR confidence BETWEEN 1 AND 5", name="confidence_range"),
    )


class Verdict(Base):
    __tablename__ = "verdict"
    id = uuid_pk()
    attempt_id = Column(ForeignKey("attempt.id"), nullable=False, unique=True)
    outcome = Column(Text, nullable=False)
    kind = Column(Text, nullable=False)
    reason_code = Column(Text)
    checker_version = Column(Text, nullable=False)
    false_alarm = Column(Boolean, nullable=False, server_default=text("false"))
    created_at = now()
    __table_args__ = (
        one_of("outcome", "correct", "partial", "wrong", "unsure"),
        one_of("kind", "fix", "no_error", "explanation", "own", "recall"),
    )


class FsrsReviewLog(Base):
    __tablename__ = "fsrs_review_log"
    id = uuid_pk()
    card_id = fk("learner_lexeme_card.id")
    verdict_id = fk("verdict.id", nullable=True)
    rating = Column(Integer, nullable=False)
    cue_level = Column(Integer, nullable=False, server_default=text("0"))
    reviewed_at = now()
    __table_args__ = (
        CheckConstraint("rating BETWEEN 1 AND 4", name="rating_range"),
        CheckConstraint(CUE_LEVEL, name="cue_level"),
        # memory-assistant.md F-MEM-8: with a cue visible, the rating is capped at Hard (2)
        CheckConstraint("cue_level = 0 OR rating <= 2", name="cue_caps_rating_at_hard"),
    )


class CopyEvent(Base):
    __tablename__ = "copy_event"
    id = uuid_pk()
    learner_id = fk("learner.id")
    rule_id = fk("rule.id")
    attempt_id = fk("attempt.id")


class AidMisassociation(Base):
    __tablename__ = "aid_misassociation"
    id = uuid_pk()
    attempt_id = fk("attempt.id")
    memory_aid_id = fk("memory_aid.id")
    lure = Column(Text, nullable=False)


class ModelCall(Base):
    __tablename__ = "model_call"
    id = uuid_pk()
    exchange_id = fk("exchange.id", nullable=True)
    agent = Column(Text, nullable=False)
    model = Column(Text, nullable=False)
    prompt_version = Column(Text, nullable=False)
    request_hash = Column(Text, nullable=False)
    response_text = Column(Text)
    latency_ms = Column(Integer)
    error = Column(Text)
    created_at = now()
    __table_args__ = (one_of("agent", "classmate", "coach", "friend", "teacher"),)


class ToolCall(Base):
    __tablename__ = "tool_call"
    id = uuid_pk()
    model_call_id = fk("model_call.id")
    tool = Column(Text, nullable=False)
    args = Column(JSONB, nullable=False)
    result = Column(JSONB)
    valid = Column(Boolean, nullable=False)


class TeacherQueueItem(Base):
    __tablename__ = "teacher_queue_item"
    id = uuid_pk()
    verdict_id = Column(ForeignKey("verdict.id"), nullable=False, unique=True)
    status = Column(Text, nullable=False, server_default="open")
    created_at = now()
    __table_args__ = (one_of("status", "open", "resolved", "escalated"),)


class TeacherResolution(Base):
    __tablename__ = "teacher_resolution"
    id = uuid_pk()
    queue_item_id = Column(ForeignKey("teacher_queue_item.id"), nullable=False, unique=True)
    teacher_id = fk("learner.id")
    outcome = Column(Text, nullable=False)
    note_hi = Column(Text)
    variant_proposal = Column(JSONB)
    resolved_at = now()
    __table_args__ = (one_of("outcome", "correct", "partial", "wrong"),)


class TeacherOverride(Base):
    __tablename__ = "teacher_override"
    id = uuid_pk()
    attempt_id = fk("attempt.id")
    teacher_id = fk("learner.id")
    old_outcome = Column(Text, nullable=False)
    new_outcome = Column(Text, nullable=False)
    reason_hi = Column(Text, nullable=False)
    created_at = now()
    __table_args__ = (
        CheckConstraint("length(btrim(reason_hi)) > 0", name="reason_required"),
        CheckConstraint("old_outcome <> new_outcome", name="changes_outcome"),
    )


# ---------------------------------------------------------------- learning state (OutcomeWriter only)


class ClassmateRuleState(Base):
    __tablename__ = "classmate_rule_state"
    learner_id = Column(ForeignKey("learner.id"), nullable=False)
    rule_id = Column(ForeignKey("rule.id"), nullable=False)
    state = Column(Text, nullable=False)
    state_version = Column(Integer, nullable=False)
    last_event_id = fk("event_ledger.id")
    __table_args__ = (
        PrimaryKeyConstraint("learner_id", "rule_id"),  # data-model.md §7: unique (learner_id, rule_id)
        one_of("state", "unknown", "taught", "forgotten"),
        CheckConstraint("state_version >= 1", name="version_positive"),
    )


# ---------------------------------------------------------------- study


class Study(Base):
    __tablename__ = "study"
    id = uuid_pk()
    name = Column(Text, nullable=False, unique=True)
    prereg_ref = Column(Text, nullable=False)
    threshold_file_hash = Column(Text, nullable=False)
    square = Column(JSONB, nullable=False)
    created_at = now()


class StudyAssignment(Base):
    __tablename__ = "study_assignment"
    id = uuid_pk()
    study_id = fk("study.id")
    learner_id = fk("learner.id")
    rule_id = fk("rule.id", nullable=True)
    concept_set = Column(Text)
    condition = Column(Text, nullable=False)
    order = Column(Integer, nullable=False)
    __table_args__ = (
        one_of("condition", "A", "B", "C", "M-A", "M-B", "M-C", "M-D"),
        CheckConstraint("(rule_id IS NULL) <> (concept_set IS NULL)", name="rule_or_concept_set"),
        UniqueConstraint("study_id", "learner_id", "rule_id", "concept_set", name="uq_study_assignment_key",
                         postgresql_nulls_not_distinct=True),
    )


class TestAdministration(Base):
    __tablename__ = "test_administration"
    id = uuid_pk()
    study_id = fk("study.id")
    learner_id = fk("learner.id")
    phase = Column(Text, nullable=False)
    item_version_id = fk("item_version.id", nullable=True)
    concept_id = fk("concept.id", nullable=True)
    scheduled_for = Column(TIMESTAMP(timezone=True), nullable=False)
    __table_args__ = (
        one_of("phase", "pre", "post", "delayed", "transfer", "day1", "day7", "day30"),
        CheckConstraint("(item_version_id IS NULL) <> (concept_id IS NULL)", name="item_or_concept"),
    )


class BlindMark(Base):
    __tablename__ = "blind_mark"
    id = uuid_pk()
    export_id = Column(Text, nullable=False)
    rater_id = Column(Text, nullable=False)
    response_id = Column(Text, nullable=False)
    score = Column(Float, nullable=False)
    rubric_version = Column(Text, nullable=False)
    __table_args__ = (UniqueConstraint("export_id", "rater_id", "response_id", name="uq_blind_mark_key"),)
