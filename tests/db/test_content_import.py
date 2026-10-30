"""Importing content into Postgres (slice 1.4). Each test gets a fresh, freshly migrated database so counts are
exact. Nothing imported may be active, verified, approved or visible to learners."""
import copy
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

from setu.content import importer, validate

from .conftest import ADMIN_URL
from .helpers import approvals

ROOT = Path(__file__).resolve().parents[2]
LEARNER_VIEWS = ("learner_rule_version", "learner_item_version", "learner_accepted_variant", "learner_hint",
                 "learner_lexeme", "learner_scene", "learner_scene_line", "learner_memory_aid")


@pytest.fixture
def fresh(db_url):
    from setu.store.migrate import upgrade

    name = f"setu_imp_{uuid.uuid4().hex[:8]}"
    admin = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f'CREATE DATABASE "{name}"'))
    url = ADMIN_URL.rsplit("/", 1)[0] + f"/{name}"
    upgrade(url)
    eng = create_engine(url)
    yield eng
    eng.dispose()
    with admin.connect() as c:
        c.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
    admin.dispose()


@pytest.fixture(scope="module")
def tree():
    return validate.load_tree(ROOT / "content")


def count(eng, sql, **p):
    with eng.connect() as c:
        return c.execute(text(sql), p).scalar_one()


def test_import_everything_as_drafts_and_nothing_reaches_learners(fresh, tree):
    result = importer.import_tree(fresh, tree)
    assert result.new_rule_versions == 25 and result.new_item_versions == 49
    assert count(fresh, "SELECT count(*) FROM rule_version WHERE validity <> 'uncertain' OR lifecycle <> 'draft' "
                        "OR teacher_approved OR jsonb_array_length(speaker_approvals) > 0") == 0
    assert count(fresh, "SELECT count(*) FROM item_version WHERE review_status <> 'draft'") == 0
    assert count(fresh, "SELECT count(*) FROM accepted_variant WHERE status <> 'proposed'") == 0
    assert count(fresh, "SELECT count(*) FROM lexeme WHERE review_status <> 'draft'") == 0
    assert count(fresh, "SELECT count(*) FROM data_source") == len(tree.data_sources)
    for view in LEARNER_VIEWS:
        assert count(fresh, f"SELECT count(*) FROM {view}") == 0, view


def test_provenance_from_both_repositories_is_stored(fresh, tree):
    importer.import_tree(fresh, tree)
    with fresh.connect() as c:
        repos = c.execute(text("SELECT ARRAY(SELECT DISTINCT p->>'repo' FROM jsonb_array_elements(provenance) p "
                               "ORDER BY 1) FROM rule_version WHERE rule_id = 'HI-TE-001'")).scalar_one()
        item_prov = c.execute(text("SELECT provenance FROM item_version WHERE item_id = 'HI-TE-001-a'")).scalar_one()
        issues = c.execute(text("SELECT validation_issues FROM item_version WHERE item_id = 'HI-TE-010-a'")
                           ).scalar_one()
    assert repos == ["LMA---Reverse-learning-Tutor", "setu-tutor"]
    assert {p["repo"] for p in item_prov} == {"LMA---Reverse-learning-Tutor", "setu-tutor"}
    assert any(i["code"] == "more_than_one_error" for i in issues)


def test_reimport_is_idempotent(fresh, tree):
    importer.import_tree(fresh, tree)
    again = importer.import_tree(fresh, tree)
    assert again.new_rule_versions == 0 and again.new_item_versions == 0 and again.new_variants == 0
    assert count(fresh, "SELECT count(*) FROM rule_version") == 25


def test_a_change_creates_a_new_version_and_keeps_history(fresh, tree):
    importer.import_tree(fresh, tree)
    changed = copy.deepcopy(tree)
    rule = next(r for r in changed.rules if r["rule_id"] == "HI-TE-002")
    rule["title_l1"] = rule["title_l1"] + " (संशोधित)"
    rule["items"][0]["l1_meaning"] = rule["items"][0]["l1_meaning"] + " (नया)"
    result = importer.import_tree(fresh, changed)
    assert result.new_rule_versions == 1
    with fresh.connect() as c:
        rows = c.execute(text("SELECT version, title_hi, supersedes_version, id FROM rule_version "
                              "WHERE rule_id = 'HI-TE-002' ORDER BY version")).all()
        item_rows = c.execute(text("SELECT version, rule_version_id FROM item_version WHERE item_id = 'HI-TE-002-a' "
                                   "ORDER BY version")).all()
    assert [r.version for r in rows] == [1, 2]
    assert rows[1].supersedes_version == rows[0].id and not rows[0].title_hi.endswith("(संशोधित)")
    assert [r.version for r in item_rows] == [1, 2] and item_rows[1].rule_version_id == rows[1].id


def test_import_never_supersedes_a_version_that_is_under_review(fresh, tree):
    importer.import_tree(fresh, tree)
    with fresh.begin() as c:  # a reviewer moved HI-TE-003 into review (owner connection stands in for the console)
        c.execute(text("INSERT INTO rule_version (rule_id, version, title_hi, l1_explanation_hi, band, validity, "
                       "learner_evidence, lifecycle, supersedes_version) SELECT rule_id, 2, coalesce(title_hi, 'क'), "
                       "coalesce(l1_explanation_hi, 'ख'), band, 'uncertain', learner_evidence, 'review', id "
                       "FROM rule_version WHERE rule_id = 'HI-TE-003' AND version = 1"))
    changed = copy.deepcopy(tree)
    next(r for r in changed.rules if r["rule_id"] == "HI-TE-003")["band"] = "L3"
    with pytest.raises(importer.ImportRefused) as e:
        importer.import_tree(fresh, changed)
    assert "HI-TE-003" in str(e.value)
    assert count(fresh, "SELECT count(*) FROM rule_version WHERE rule_id = 'HI-TE-003'") == 2


def test_import_refuses_content_with_errors_and_writes_nothing(fresh, tree):
    bad = copy.deepcopy(tree)
    next(r for r in bad.rules if r["rule_id"] == "HI-TE-001")["lifecycle"] = "active"
    with pytest.raises(importer.ImportRefused):
        importer.import_tree(fresh, bad)
    assert count(fresh, "SELECT count(*) FROM rule_version") == 0


def test_importer_works_with_content_privileges_only(fresh):
    assert importer.effective_role(fresh) == "setu_content"


# ---------------------------------------------------------------- database guards added in migration 0003


def _fails(eng, sql, params=None, match=None):
    with eng.connect() as c, pytest.raises(DBAPIError) as e:
        c.execute(text(sql), params or {})
    if match:
        assert match in str(e.value.orig), str(e.value.orig)


def test_database_rejects_latin_in_learner_facing_text(fresh):
    with fresh.begin() as c:
        c.execute(text("INSERT INTO rule (id, direction, contrast_area) VALUES ('HI-TE-001', 'HI->TE', 'q')"))
    _fails(fresh, "INSERT INTO rule_version (rule_id, version, title_hi, band, validity, learner_evidence, lifecycle) "
                  "VALUES ('HI-TE-001', 1, 'Questions', 'L4', 'uncertain', 'predicted', 'draft')", match="latin")
    _fails(fresh, "INSERT INTO lexeme (id, telugu, hindi_gloss) VALUES ('te:x', 'అవును', 'yes')", match="latin")


def test_database_rejects_unanchored_patterns(fresh):
    with fresh.begin() as c:
        c.execute(text("INSERT INTO rule (id, direction, contrast_area) VALUES ('HI-TE-001', 'HI->TE', 'q')"))
        rv = c.execute(text("INSERT INTO rule_version (rule_id, version, band, validity, learner_evidence, "
                            "lifecycle) VALUES ('HI-TE-001', 1, 'L4', 'uncertain', 'predicted', 'draft') RETURNING id")
                       ).scalar_one()
        c.execute(text("INSERT INTO item (id, rule_id) VALUES ('HI-TE-001-a', 'HI-TE-001')"))
    for bad in (["అమ్మను"], ["^అమ్మను"], ["అమ్మను$"], ["^అమ్మను\\$"]):
        _fails(fresh, "INSERT INTO item_version (item_id, version, rule_version_id, correct_form, pool, "
                      "accept_patterns) VALUES ('HI-TE-001-a', 1, :rv, 'అమ్మను', 'practice', :p)",
               {"rv": rv, "p": bad}, match="anchored")


def test_database_rejects_approving_an_item_with_validation_issues(fresh):
    with fresh.begin() as c:
        c.execute(text("INSERT INTO rule (id, direction, contrast_area) VALUES ('HI-TE-001', 'HI->TE', 'q')"))
        rv = c.execute(text("INSERT INTO rule_version (rule_id, version, band, validity, learner_evidence, "
                            "lifecycle) VALUES ('HI-TE-001', 1, 'L4', 'uncertain', 'predicted', 'draft') RETURNING id")
                       ).scalar_one()
        c.execute(text("INSERT INTO item (id, rule_id) VALUES ('HI-TE-001-a', 'HI-TE-001')"))
    _fails(fresh, "INSERT INTO item_version (item_id, version, rule_version_id, correct_form, pool, review_status, "
                  "validation_issues) VALUES ('HI-TE-001-a', 1, :rv, 'ఇది', 'practice', 'approved', "
                  "'[{\"code\": \"more_than_one_error\"}]')", {"rv": rv})


def test_database_requires_learner_text_before_a_rule_is_verified(fresh):
    with fresh.begin() as c:
        c.execute(text("INSERT INTO rule (id, direction, contrast_area) VALUES ('HI-TE-001', 'HI->TE', 'q')"))
    _fails(fresh, "INSERT INTO rule_version (rule_id, version, band, validity, learner_evidence, lifecycle, "
                  "speaker_approvals) VALUES ('HI-TE-001', 1, 'L4', 'verified', 'predicted', 'verified', "
                  "CAST(:a AS jsonb))", {"a": approvals("s1", "s2")})


def test_learner_views_show_only_verified_approved_current_content(fresh):
    with fresh.begin() as c:
        c.execute(text("INSERT INTO rule (id, direction, contrast_area) VALUES ('HI-TE-001', 'HI->TE', 'q')"))
        rv = c.execute(text("INSERT INTO rule_version (rule_id, version, title_hi, l1_explanation_hi, band, validity, "
                            "learner_evidence, lifecycle, teacher_approved, speaker_approvals) VALUES ('HI-TE-001', 1, "
                            "'सवाल', 'व्याख्या', 'L4', 'verified', 'predicted', 'active', true, CAST(:a AS jsonb)) "
                            "RETURNING id"), {"a": approvals("s1", "s2")}).scalar_one()
        c.execute(text("INSERT INTO item (id, rule_id) VALUES ('HI-TE-001-a', 'HI-TE-001'), "
                       "('HI-TE-001-b', 'HI-TE-001')"))
        c.execute(text("INSERT INTO item_version (item_id, version, rule_version_id, correct_form, pool, review_status) "
                       "VALUES ('HI-TE-001-a', 1, :rv, 'నువ్వు వస్తావా', 'practice', 'approved'), "
                       "('HI-TE-001-b', 1, :rv, 'ఇది పుస్తకమా', 'practice', 'draft')"), {"rv": rv})
    assert count(fresh, "SELECT count(*) FROM learner_rule_version") == 1
    assert count(fresh, "SELECT count(*) FROM learner_item_version") == 1  # the draft item stays hidden

    with fresh.begin() as c:  # a newer, deprecated version retires the rule for learners
        c.execute(text("INSERT INTO rule_version (rule_id, version, title_hi, l1_explanation_hi, band, validity, "
                       "learner_evidence, lifecycle, supersedes_version) VALUES ('HI-TE-001', 2, 'सवाल', 'व्याख्या', "
                       "'L4', 'uncertain', 'predicted', 'deprecated', :rv)"), {"rv": rv})
    assert count(fresh, "SELECT count(*) FROM learner_rule_version") == 0
    assert count(fresh, "SELECT count(*) FROM learner_item_version") == 0


def test_read_role_sees_learner_views_not_draft_tables(fresh):
    with fresh.connect() as c:
        c.execute(text("SET ROLE setu_read"))
        for view in LEARNER_VIEWS:
            c.execute(text(f"SELECT count(*) FROM {view}"))
        for table in ("rule_version", "item_version", "accepted_variant", "hint", "lexeme", "scene_line",
                      "memory_aid"):
            sp = c.begin_nested()
            with pytest.raises(DBAPIError) as e:
                c.execute(text(f"SELECT * FROM {table}"))
            sp.rollback()
            assert "permission denied" in str(e.value.orig)
        c.execute(text("RESET ROLE"))


def test_database_refuses_a_verified_rule_with_open_issues(fresh):
    with fresh.begin() as c:
        c.execute(text("INSERT INTO rule (id, direction, contrast_area) VALUES ('HI-TE-001', 'HI->TE', 'q')"))
    _fails(fresh, "INSERT INTO rule_version (rule_id, version, title_hi, l1_explanation_hi, band, validity, "
                  "learner_evidence, lifecycle, speaker_approvals, validation_issues) VALUES ('HI-TE-001', 1, 'क', "
                  "'ख', 'L4', 'verified', 'predicted', 'verified', CAST(:a AS jsonb), "
                  "'[{\"code\": \"needs_rewrite\"}]')", {"a": approvals("s1", "s2")}, match="no_issues")


def test_an_approved_variant_of_a_draft_item_stays_hidden(fresh, tree):
    importer.import_tree(fresh, tree)
    with fresh.begin() as c:  # someone approves one variant (two approvals) while its item is still a draft
        c.execute(text("UPDATE accepted_variant SET status = 'approved', approvals = CAST(:a AS jsonb) "
                       "WHERE id = (SELECT id FROM accepted_variant LIMIT 1)"), {"a": approvals("t1", "t2")})
    assert count(fresh, "SELECT count(*) FROM accepted_variant WHERE status = 'approved'") == 1
    assert count(fresh, "SELECT count(*) FROM learner_accepted_variant") == 0
