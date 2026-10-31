"""Teacher console II: rule review and promotion, variant review, agreement (slice 4.2; F1, F2, F4, TS-TCH-*)."""
import json
import re

from sqlalchemy import text

from .helpers import approvals
from .test_correction import rule_bank  # noqa: F401  (fixture)
from .test_letters import client
from .test_teacher_queue import resolution_key, unsure_fix  # noqa: F401  (fixture)
from .test_teacher_review import one, teacher

N = iter(range(910, 1000))  # 901-903 belong to the S5 rule bank


def draft_rule(engine, *, explanation="हिंदी की आदत यहाँ नहीं चलती।", issues=(), variant_status="approved"):
    """A draft HI-TE rule with two practice items (one with a spoken variant) and a target skill."""
    with engine.begin() as c:
        rid = f"HI-TE-{next(N)}"
        while c.execute(text("SELECT 1 FROM rule WHERE id = :r"), {"r": rid}).first():  # other tests pick ids at random
            rid = f"HI-TE-{next(N)}"
        skill = f"L4.rule.{rid}.PR"
        c.execute(text("INSERT INTO skill (id, band, family, target, modality, direction) VALUES (:s, 'L4', 'rule', :r, "
                       "'PR', 'HI->TE') ON CONFLICT DO NOTHING"), {"s": skill, "r": rid})
        c.execute(text("INSERT INTO rule (id, direction, contrast_area) VALUES (:r, 'HI->TE', 'questions')"), {"r": rid})
        rv = c.execute(text(
            "INSERT INTO rule_version (rule_id, version, title_hi, l1_explanation_hi, band, validity, learner_evidence, "
            "lifecycle, teacher_approved, target_skill_id, validation_issues, content_hash) VALUES (:r, 1, 'सवाल का नियम', "
            ":e, 'L4', 'uncertain', 'model_predicted', 'draft', false, :s, CAST(:iss AS jsonb), 'h1') RETURNING id"),
            {"r": rid, "e": explanation, "s": skill, "iss": json.dumps(list(issues))}).scalar_one()
        for k, (meaning, wrong, ok) in enumerate((("तुम आ रहे हो क्या", "క్యా నువ్వు వస్తావు", "నువ్వు వస్తావా"),
                                                  ("यह किताब है क्या", "క్యా ఇది పుస్తకం", "ఇది పుస్తకమా"))):
            iid = f"{rid}-{'ab'[k]}"
            c.execute(text("INSERT INTO item (id, rule_id) VALUES (:i, :r)"), {"i": iid, "r": rid})
            iv = c.execute(text("INSERT INTO item_version (item_id, version, rule_version_id, hindi_meaning, wrong_form, "
                                "one_error_span, correct_form, pool, review_status) VALUES (:i, 1, :rv, :m, :w, "
                                "ARRAY[0, 4], :ok, 'practice', 'draft') RETURNING id"),
                           {"i": iid, "rv": rv, "m": meaning, "w": wrong, "ok": ok}).scalar_one()
            if k == 0:
                a = approvals("s1", "s2") if variant_status == "approved" else "[]"
                c.execute(text("INSERT INTO accepted_variant (item_version_id, form, register, status, approvals) "
                               "VALUES (:iv, 'నువ్వు వస్తున్నావా', 'spoken', :st, CAST(:a AS jsonb))"),
                          {"iv": iv, "st": variant_status, "a": a})
    return rid


def latest(engine, rid):
    return one(engine, "SELECT id, version, validity, lifecycle, teacher_approved, speaker_approvals, change_note "
                       "FROM rule_version WHERE rule_id = :r ORDER BY version DESC LIMIT 1", r=rid)


def review(t, rid, *, decision="approve", category="1", language="te", native="1", version_id=None):
    page = t.get(f"/teacher/rules/{rid}").text
    vid = version_id or re.search(r'name="rule_version_id" value="([^"]+)"', page).group(1)
    data = {"rule_version_id": vid, "language": language, "acceptable_natural": "5", "category_ok": category,
            "explanation_ok": "4", "band_fit": "L4", "confidence": "4", "decision": decision, "comments_hi": ""}
    if native:
        data["native"] = native
    return t.post(f"/teacher/rules/{rid}/review", data=data).text


def test_learners_cannot_review_rules(engine):
    rid = draft_rule(engine)
    c, _ = client(engine)
    assert c.get("/teacher/rules").status_code == 403
    assert c.get(f"/teacher/rules/{rid}").status_code == 403


def test_the_rule_page_shows_items_with_the_error_marked_variants_and_history(engine):
    rid = draft_rule(engine)
    t, _ = teacher(engine)
    assert rid in t.get("/teacher/rules").text
    page = t.get(f"/teacher/rules/{rid}").text
    assert "<mark>క్యా</mark>" in page and "నువ్వు వస్తావా" in page and "నువ్వు వస్తున్నావా" in page
    assert "सवाल का नियम" in page and "संस्करण" in page


def test_one_native_approval_does_not_verify_and_two_agreeing_approvals_do(engine):
    rid = draft_rule(engine)
    a, _ = teacher(engine)
    b, _ = teacher(engine)
    page = review(a, rid)
    assert latest(engine, rid).validity == "uncertain" and "दूसरे" in page
    review(b, rid)
    v = latest(engine, rid)
    assert (v.validity, v.lifecycle, v.teacher_approved, v.version) == ("verified", "verified", False, 2)
    assert len(v.speaker_approvals) == 2 and all(x["native"] for x in v.speaker_approvals)
    items = engine.connect().execute(text(
        "SELECT review_status, rule_version_id FROM item_version iv JOIN item i ON i.id = iv.item_id WHERE i.rule_id = :r "
        "AND iv.version = 2"), {"r": rid}).all()
    assert len(items) == 2 and all(x.review_status == "approved" and x.rule_version_id == v.id for x in items)
    assert one(engine, "SELECT count(*) AS n FROM learner_rule_version WHERE rule_id = :r", r=rid).n == 0


def test_activation_needs_verification_and_then_learners_see_the_rule_and_its_variants(engine):
    rid = draft_rule(engine)
    a, _ = teacher(engine)
    b, _ = teacher(engine)
    page = a.post(f"/teacher/rules/{rid}/activate", data={"rule_version_id": str(latest(engine, rid).id)}).text
    assert "पहले दो तेलुगु मातृभाषी" in page and latest(engine, rid).lifecycle == "draft"
    review(a, rid)
    review(b, rid)
    a.post(f"/teacher/rules/{rid}/activate", data={"rule_version_id": str(latest(engine, rid).id)})
    v = latest(engine, rid)
    assert (v.lifecycle, v.teacher_approved, v.version) == ("active", True, 3)
    assert one(engine, "SELECT count(*) AS n FROM learner_rule_version WHERE rule_id = :r", r=rid).n == 1
    assert one(engine, "SELECT count(*) AS n FROM learner_item_version iv JOIN item i ON i.id = iv.item_id "
                       "WHERE i.rule_id = :r", r=rid).n == 2
    assert one(engine, "SELECT count(*) AS n FROM learner_accepted_variant av JOIN item_version iv ON iv.id = "
                       "av.item_version_id JOIN item i ON i.id = iv.item_id WHERE i.rule_id = :r", r=rid).n == 1
    a.post(f"/teacher/rules/{rid}/deprecate", data={"rule_version_id": str(v.id)})
    assert latest(engine, rid).lifecycle == "deprecated"
    assert one(engine, "SELECT count(*) AS n FROM learner_rule_version WHERE rule_id = :r", r=rid).n == 0


def test_disagreement_asks_for_a_third_reviewer_who_settles_it(engine):
    rid = draft_rule(engine)
    a, _ = teacher(engine)
    b, _ = teacher(engine)
    c3, _ = teacher(engine)
    review(a, rid)
    review(b, rid, category="0")
    assert latest(engine, rid).validity == "uncertain"
    assert "तीसरे" in a.get("/teacher/rules").text
    review(c3, rid)
    assert latest(engine, rid).validity == "verified"


def test_two_rejections_reject_the_rule(engine):
    rid = draft_rule(engine)
    for _ in range(2):
        t, _ = teacher(engine)
        review(t, rid, decision="reject")
    v = latest(engine, rid)
    assert (v.validity, v.lifecycle) == ("rejected", "rejected")


def test_non_native_and_hindi_reviews_are_kept_but_do_not_verify(engine):
    rid = draft_rule(engine)
    a, _ = teacher(engine)
    b, _ = teacher(engine)
    h, _ = teacher(engine)
    review(a, rid)
    review(b, rid, native=None)
    review(h, rid, language="hi", native=None)
    assert latest(engine, rid).validity == "uncertain"
    assert one(engine, "SELECT count(*) AS n FROM rule_review r JOIN rule_version v ON v.id = r.rule_version_id "
                       "WHERE v.rule_id = :r", r=rid).n == 3


def test_a_rule_with_open_issues_or_no_explanation_cannot_be_verified(engine):
    for kwargs, why in (({"explanation": None}, "व्याख्या"), ({"issues": [{"code": "dq_08"}]}, "समस्या")):
        rid = draft_rule(engine, **kwargs)
        a, _ = teacher(engine)
        b, _ = teacher(engine)
        review(a, rid)
        page = review(b, rid)
        assert why in page and latest(engine, rid).validity == "uncertain"


def test_a_review_of_an_old_version_is_refused_and_a_reviewer_reviews_once(engine):
    rid = draft_rule(engine)
    a, _ = teacher(engine)
    old = str(latest(engine, rid).id)
    assert "पहले ही" in (review(a, rid), review(a, rid))[1]
    b, _ = teacher(engine)
    c3, _ = teacher(engine)
    review(b, rid)  # verifies: a new version exists now
    assert "बदल" in review(c3, rid, version_id=old)


# ---------------------------------------------------------------- variants (F4) and proposals from settlement


def test_a_proposed_variant_needs_two_native_approvals_before_the_checker_accepts_it(engine):
    rid = draft_rule(engine, variant_status="proposed")
    a, _ = teacher(engine)
    b, _ = teacher(engine)
    review(a, rid)
    review(b, rid)
    a.post(f"/teacher/rules/{rid}/activate", data={"rule_version_id": str(latest(engine, rid).id)})
    visible = "SELECT count(*) AS n FROM learner_accepted_variant av JOIN item_version iv ON iv.id = " \
              "av.item_version_id JOIN item i ON i.id = iv.item_id WHERE i.rule_id = :r"
    assert one(engine, visible, r=rid).n == 0
    var = one(engine, "SELECT CAST(av.id AS text) AS id FROM accepted_variant av JOIN learner_item_version iv ON "
                      "iv.id = av.item_version_id JOIN item i ON i.id = iv.item_id WHERE i.rule_id = :r", r=rid)
    for t in (a, b):
        page = t.get("/teacher/review/accepted_variant/item", params={"id": var.id}).text
        h = re.search(r'name="content_hash" value="([^"]*)"', page).group(1)
        t.post("/teacher/review/accepted_variant/item",
               data={"id": var.id, "content_hash": h, "decision": "approve", "native": "1"})
    assert one(engine, visible, r=rid).n == 1
    from setu.domain import checker
    from setu.web import routes_rules

    with engine.begin() as c:
        c.execute(text("SET LOCAL ROLE setu_app"))
        _, items = routes_rules._bank(c, None)
    item = next(x for x in items.values() if x.item_id == f"{rid}-a")
    key = routes_rules._key(item, items)
    import uuid
    v = checker.check_fix(attempt_id=uuid.uuid4(), raw="నువ్వు వస్తున్నావా", item=key, response_mode="typed").verdict
    assert v.outcome == "correct"


def test_settling_an_answer_can_propose_it_as_a_variant_which_is_not_yet_accepted(engine, rule_bank,  # noqa: F811
                                                                                  resolution_key):  # noqa: F811
    _, qid, _ = unsure_fix(engine)
    t, t_id = teacher(engine)
    t.post("/teacher/queue/settle", data={"queue_item_id": str(qid), "outcome": "correct", "propose": "1"})
    row = one(engine, "SELECT av.status, av.approvals, av.form, av.provenance FROM accepted_variant av WHERE "
                      "av.form = 'మీరు ఎక్కడ ఉన్నారు' ORDER BY av.id LIMIT 1")
    assert row.status == "proposed" and row.approvals == [] and f"teacher:{t_id}" in json.dumps(row.provenance)


# ---------------------------------------------------------------- agreement (F2)


def test_agreement_is_withheld_below_ten_pairs_then_computed_and_stored(engine):
    t, _ = teacher(engine)
    page = t.get("/teacher/agreement", params={"batch": "kappa-test"}).text
    assert "κ अभी नहीं निकाला जा सकता" in page
    cats_a = [True, True, False, False, True, False, True, True, False, True]
    cats_b = [True, False, False, False, True, False, True, True, True, True]
    with engine.begin() as c:
        for k in range(10):
            rid = draft_rule(engine)
            vid = c.execute(text("SELECT id FROM rule_version WHERE rule_id = :r"), {"r": rid}).scalar_one()
            for who, cat in (("kappa-a", cats_a[k]), ("kappa-b", cats_b[k])):
                c.execute(text("INSERT INTO rule_review (rule_version_id, reviewer_id, language, acceptable_natural, "
                               "category_ok, explanation_ok, band_fit, confidence, decision, native_speaker, batch) "
                               "VALUES (:v, :w, 'te', 4, :c, 4, 'L4', 4, 'approve', true, 'kappa-test')"),
                          {"v": vid, "w": who, "c": cat})
    page = t.post("/teacher/agreement", data={"batch": "kappa-test"}).text
    assert "0.583" in page
    row = one(engine, "SELECT kappa, n FROM kappa_report WHERE batch = 'kappa-test' AND metric = 'category_ok' "
                      "ORDER BY computed_at DESC LIMIT 1")
    assert row.n == 10 and round(row.kappa, 3) == 0.583
