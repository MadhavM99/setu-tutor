"""TS-DB-01: constraints and rule-approval protections (data-model.md §2, §3, §7).

Spec IDs: P-BANK-03/04/05, X-BANK-06/07, P-TOOL-01 (item id pattern), A1 (visual assets, FSRS cue cap).
"""
from sqlalchemy import text

from .helpers import approvals, fails, make_learner, make_rule, make_rule_version, ok


def test_verified_needs_two_speaker_approvals(conn):
    make_rule(conn)
    fails(conn, "INSERT INTO rule_version (rule_id, version, title_hi, l1_explanation_hi, band, validity, "
          "learner_evidence, lifecycle, speaker_approvals) VALUES ('HI-TE-001', 1, 'क', 'ख', 'L4', 'verified', "
          "'predicted', 'review', CAST(:a AS jsonb))", {"a": approvals("rev-1")})


def test_verified_needs_two_distinct_speakers_of_the_target_language(conn):
    make_rule(conn)
    # same reviewer twice is still one speaker
    fails(conn, "INSERT INTO rule_version (rule_id, version, title_hi, l1_explanation_hi, band, validity, "
          "learner_evidence, lifecycle, speaker_approvals) VALUES ('HI-TE-001', 1, 'क', 'ख', 'L4', 'verified', "
          "'predicted', 'review', CAST(:a AS jsonb))", {"a": approvals("rev-1", "rev-1")}, match="distinct")
    # two Hindi speakers do not verify a Hindi->Telugu rule (its target language is Telugu)
    fails(conn, "INSERT INTO rule_version (rule_id, version, title_hi, l1_explanation_hi, band, validity, "
          "learner_evidence, lifecycle, speaker_approvals) VALUES ('HI-TE-001', 1, 'क', 'ख', 'L4', 'verified', "
          "'predicted', 'review', CAST(:a AS jsonb))", {"a": approvals("rev-1", "rev-2", lang="hi")},
          match="distinct")


def test_verified_with_two_distinct_speakers_is_accepted(conn):
    make_rule(conn)
    make_rule_version(conn, validity="verified", lifecycle="verified",
                      speaker_approvals=approvals("rev-1", "rev-2"))


def test_lifecycle_verified_or_active_requires_validity_verified(conn):
    make_rule(conn)
    for lifecycle in ("verified", "active"):
        fails(conn, "INSERT INTO rule_version (rule_id, version, title_hi, l1_explanation_hi, band, validity, "
              "learner_evidence, lifecycle, teacher_approved) VALUES ('HI-TE-001', 1, 'क', 'ख', 'L4', "
              "'uncertain', 'predicted', :l, true)", {"l": lifecycle})


def test_active_requires_teacher_approval(conn):
    make_rule(conn)
    fails(conn, "INSERT INTO rule_version (rule_id, version, title_hi, l1_explanation_hi, band, validity, "
          "learner_evidence, lifecycle, teacher_approved, speaker_approvals) VALUES ('HI-TE-001', 1, 'क', 'ख', "
          "'L4', 'verified', 'predicted', 'active', false, CAST(:a AS jsonb))", {"a": approvals("r1", "r2")})
    make_rule_version(conn, version=2, validity="verified", lifecycle="active", teacher_approved=True,
                      speaker_approvals=approvals("r1", "r2"))


def test_validity_and_learner_evidence_are_separate_closed_sets(conn):
    make_rule(conn)
    # an evidence value is not a validity value, and vice versa
    fails(conn, "INSERT INTO rule_version (rule_id, version, title_hi, l1_explanation_hi, band, validity, "
          "learner_evidence, lifecycle) VALUES ('HI-TE-001', 1, 'क', 'ख', 'L4', 'observed', 'predicted', 'draft')")
    fails(conn, "INSERT INTO rule_version (rule_id, version, title_hi, l1_explanation_hi, band, validity, "
          "learner_evidence, lifecycle) VALUES ('HI-TE-001', 1, 'क', 'ख', 'L4', 'uncertain', 'verified', 'draft')")


def test_observed_errors_cannot_exceed_opportunities(conn):
    make_rule(conn)
    fails(conn, "INSERT INTO rule_version (rule_id, version, title_hi, l1_explanation_hi, band, validity, "
          "learner_evidence, lifecycle, opportunities, observed_errors) VALUES ('HI-TE-001', 1, 'क', 'ख', 'L4', "
          "'uncertain', 'predicted', 'draft', 40, 41)")


def test_item_id_pattern(conn):
    make_rule(conn)
    for bad in ("HI-TE-001", "Are you coming?", "hi-te-001-a", "HI-TE-01-a", "HI-TE-001-ab"):
        fails(conn, "INSERT INTO item (id, rule_id) VALUES (:i, 'HI-TE-001')", {"i": bad})
    ok(conn, "INSERT INTO item (id, rule_id) VALUES ('HI-TE-001-a', 'HI-TE-001')")


def test_accepted_variant_needs_two_approvals_to_be_approved(conn):
    make_rule(conn)
    rv = make_rule_version(conn)
    conn.execute(text("INSERT INTO item (id, rule_id) VALUES ('HI-TE-001-a', 'HI-TE-001')"))
    iv = conn.execute(text("INSERT INTO item_version (item_id, version, rule_version_id, correct_form, pool, "
                           "review_status) VALUES ('HI-TE-001-a', 1, :rv, 'నువ్వు వస్తావా', 'practice', 'draft') "
                           "RETURNING id"), {"rv": rv}).scalar_one()
    fails(conn, "INSERT INTO accepted_variant (item_version_id, form, register, status, approvals) VALUES "
          "(:iv, 'నువ్వు వస్తున్నావా', 'spoken', 'approved', CAST(:a AS jsonb))", {"iv": iv, "a": approvals("t1")})
    ok(conn, "INSERT INTO accepted_variant (item_version_id, form, register, status, approvals) VALUES "
       "(:iv, 'నువ్వు వస్తున్నావా', 'spoken', 'approved', CAST(:a AS jsonb))", {"iv": iv, "a": approvals("t1", "t2")})


def test_llm_proposals_are_model_predicted(conn):
    fails(conn, "INSERT INTO content_proposal (kind, payload, origin, evidence, status) VALUES "
          "('rule', '{}', 'llm', 'predicted', 'open')")
    ok(conn, "INSERT INTO content_proposal (kind, payload, origin, evidence, status) VALUES "
       "('rule', '{}', 'llm', 'model_predicted', 'open')")


def test_approved_visual_asset_must_be_text_free_with_alt_text_and_licence(conn):
    base = ("INSERT INTO visual_asset (uri, sha256, prompt, model, provider, ocr_text_found, contrast_ok, "
            "review_status, licence, alt_text_hi) VALUES ('file://x.png', 'abc', 'कमल', 'm', 'self_hosted', "
            ":ocr, true, 'approved', :lic, :alt)")
    fails(conn, base, {"ocr": True, "lic": "CC-BY", "alt": "कमल का फूल"})
    fails(conn, base, {"ocr": False, "lic": "CC-BY", "alt": None})
    fails(conn, base, {"ocr": False, "lic": None, "alt": "कमल का फूल"})
    ok(conn, base, {"ocr": False, "lic": "CC-BY", "alt": "कमल का फूल"})


def test_fsrs_rating_capped_at_hard_when_a_cue_was_visible(conn):
    learner = make_learner(conn)
    card = conn.execute(text("INSERT INTO learner_lexeme_card (learner_id, card_kind, card_ref, modality) "
                             "VALUES (:l, 'letter', 'ళ', 'RCL') RETURNING id"), {"l": learner}).scalar_one()
    fails(conn, "INSERT INTO fsrs_review_log (card_id, rating, cue_level) VALUES (:c, 3, 2)", {"c": card})
    ok(conn, "INSERT INTO fsrs_review_log (card_id, rating, cue_level) VALUES (:c, 2, 2)", {"c": card})
    ok(conn, "INSERT INTO fsrs_review_log (card_id, rating, cue_level) VALUES (:c, 4, 0)", {"c": card})


def test_classmate_state_unique_per_learner_and_rule(conn):
    learner = make_learner(conn)
    make_rule(conn)
    ev = conn.execute(text("INSERT INTO event_ledger (actor, event_type, payload) VALUES "
                           "('checker', 'teach', '{}') RETURNING id")).scalar_one()
    q = ("INSERT INTO classmate_rule_state (learner_id, rule_id, state, state_version, last_event_id) "
         "VALUES (:l, 'HI-TE-001', 'taught', 1, :e)")
    ok(conn, q, {"l": learner, "e": ev})
    fails(conn, q, {"l": learner, "e": ev})
    fails(conn, "UPDATE classmate_rule_state SET state = 'mastered' WHERE learner_id = :l", {"l": learner})


def test_attempt_idempotency_key_is_unique(conn):
    learner = make_learner(conn)
    s = conn.execute(text("INSERT INTO session (learner_id, mode, config_snapshot, seed) VALUES "
                          "(:l, 'learn', '{}', 7) RETURNING id"), {"l": learner}).scalar_one()
    e = conn.execute(text("INSERT INTO exchange (session_id, kind, source) VALUES (:s, 'own', 'template') "
                          "RETURNING id"), {"s": s}).scalar_one()
    q = "INSERT INTO attempt (exchange_id, n, raw_text, idempotency_key) VALUES (:e, :n, 'x', 'k-1')"
    ok(conn, q, {"e": e, "n": 1})
    fails(conn, q, {"e": e, "n": 2})


def test_aid_event_references_an_aid_or_a_fallback_but_not_both(conn):
    learner = make_learner(conn)
    conn.execute(text("INSERT INTO concept (id, kind, content_ref, fact_sheet) VALUES ('c-ళ', 'letter', 'ళ', '{}')"))
    q = ("INSERT INTO aid_event (learner_id, concept_id, memory_aid_id, fallback_kind, event, recommended_by) "
         "VALUES (:l, 'c-ళ', NULL, :f, 'presented', 'policy')")
    fails(conn, q, {"l": learner, "f": None})
    ok(conn, q, {"l": learner, "f": "twin_view"})
