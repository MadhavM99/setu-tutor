"""Build an isolated DEMO database (`setu_demo`) for showing the app. Development only.

The real content is still unreviewed, so learners in the real database see nothing. For a demonstration this script
creates a separate database, imports the content tree as drafts, and then approves it through the normal review
path (`ContentReviewer`, `RuleReviewer`) by two accounts named `demo-reviewer-*`. Those approvals are NOT native
speaker review: every page shows a demo banner (SETU_DEMO=1), and nothing here touches the real database.

The imported rules all have open validation issues, so they cannot be verified even here. Three clearly labelled
demo rules (the synthetic test bank, titles start with "डेमो") are added and promoted instead.

    python -m scripts.demo_seed            # prints the demo logins
"""
import json
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
ADMIN = os.environ.get("SETU_TEST_ADMIN_URL", "postgresql+psycopg://setu_migrate:setu-dev-only@localhost:5433/postgres")
DEMO_DB = "setu_demo"
PASS = "डेमो पासवर्ड बारह"
BANK = {
    "HI-TE-901": ("डेमो: हाँ/ना वाले सवाल — ‘क्या’ नहीं, अंत में -आ", [
        ("तुम आ रहे हो क्या", "క్యా నువ్వు వస్తావు", "నువ్వు వస్తావా"),
        ("यह किताब है क्या", "క్యా ఇది పుస్తకం", "ఇది పుస్తకమా")]),
    "HI-TE-902": ("डेमो: ‘नहीं’ के लिए हिंदी शब्द नहीं", [
        ("मैं नहीं जाऊँगा", "నేను నహీ వెళ్తాను", "నేను వెళ్ళను"),
        ("वह नहीं आएगा", "అతను నహీ వస్తాడు", "అతను రాడు")]),
    "HI-TE-903": ("डेमो: ‘है’ के लिए अलग शब्द नहीं", [
        ("यह घर है", "ఇది ఇల్లు ఉంది", "ఇది ఇల్లు"),
        ("वह पेड़ है", "అది చెట్టు ఉంది", "అది చెట్టు")]),
}
EXPLAIN = "डेमो व्याख्या: हिंदी की आदत यहाँ तेलुगु में नहीं चलती। (असली जाँच बाकी)"


def main() -> int:
    from setu.content import importer, validate
    from setu.store.content_review import KINDS, ReviewRefused
    from setu.store.migrate import upgrade
    from setu.store.rule_promotion import RuleForm, RuleReviewer
    from setu.web import auth

    admin = create_engine(ADMIN, isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{DEMO_DB}" WITH (FORCE)'))
        c.execute(text(f'CREATE DATABASE "{DEMO_DB}"'))
    url = ADMIN.rsplit("/", 1)[0] + f"/{DEMO_DB}"
    upgrade(url)
    engine = create_engine(url)
    importer.import_tree(engine, validate.load_tree(ROOT / "content"))

    reviewers = []
    with engine.begin() as c:
        for k in (1, 2):
            reviewers.append(c.execute(text(
                "INSERT INTO learner (handle, passphrase_hash, l1, l2, direction, role) VALUES (:h, :p, 'hi', 'te', "
                "'HI->TE', 'teacher') RETURNING id"), {"h": f"demo-reviewer-{k}", "p": auth.hash_passphrase(PASS)}
            ).scalar_one())
        for rid, (title, items) in BANK.items():  # demo rules, clearly labelled
            skill = f"L4.rule.{rid}.PR"
            c.execute(text("INSERT INTO skill (id, band, family, target, modality, direction) VALUES (:s, 'L4', "
                           "'rule', :r, 'PR', 'HI->TE') ON CONFLICT DO NOTHING"), {"s": skill, "r": rid})
            c.execute(text("INSERT INTO rule (id, direction, contrast_area) VALUES (:r, 'HI->TE', 'demo')"), {"r": rid})
            ck = {"ideas": [["क्या", "नहीं", "है"], ["अंत", "आख़िर", "शब्द"]], "relations": [["नहीं"]]}
            rv = c.execute(text(
                "INSERT INTO rule_version (rule_id, version, title_hi, l1_explanation_hi, concept_key, band, validity, "
                "learner_evidence, lifecycle, teacher_approved, target_skill_id, provenance) VALUES (:r, 1, :t, :e, "
                "CAST(:ck AS jsonb), 'L4', 'uncertain', 'model_predicted', 'draft', false, :s, CAST(:p AS jsonb)) "
                "RETURNING id"), {"r": rid, "t": title, "e": EXPLAIN, "ck": json.dumps(ck, ensure_ascii=False),
                                  "s": skill, "p": json.dumps([{"source": "demo fixture (synthetic), not reviewed"}])}
            ).scalar_one()
            for k, (meaning, wrong, ok) in enumerate(items):
                iid = f"{rid}-{'ab'[k]}"
                c.execute(text("INSERT INTO item (id, rule_id) VALUES (:i, :r)"), {"i": iid, "r": rid})
                c.execute(text("INSERT INTO item_version (item_id, version, rule_version_id, hindi_meaning, wrong_form, "
                               "correct_form, pool, review_status) VALUES (:i, 1, :rv, :m, :w, :ok, 'practice', "
                               "'draft')"), {"i": iid, "rv": rv, "m": meaning, "w": wrong, "ok": ok})

    rr = RuleReviewer(engine)
    approved = {}
    for kind in KINDS:
        if kind in ("scene_reply_variant", "accepted_variant"):
            continue
        n = 0
        for r in rr.pending(kind, reviewers[0], limit=1000):
            for who in reviewers if KINDS[kind].approvals else reviewers[:1]:
                try:
                    rr.review(kind, r["id"], who, decision="approve", native=True, content_hash=r["content_hash"],
                              comment_hi="डेमो मंज़ूरी")
                except ReviewRefused:
                    pass
            n += 1
        approved[kind] = n
    for rid in BANK:
        for who in reviewers:
            vid = str(rr.detail(rid, who)["version"].id)
            rr.review_rule(rid, vid, who, RuleForm("te", True, 4, True, 4, "L4", 4, "approve", "डेमो मंज़ूरी"))
        rr.activate(rid, str(rr.detail(rid, reviewers[0])["version"].id), reviewers[0])

    learner_code = auth.create_invite(engine, role="learner", valid_hours=720)
    teacher_code = auth.create_invite(engine, role="teacher", valid_hours=720)
    with engine.begin() as c:
        c.execute(text("SET LOCAL ROLE setu_app"))
        _, lhandle = auth.redeem_invite(c, learner_code, PASS)
        _, thandle = auth.redeem_invite(c, teacher_code, PASS)
        active = c.execute(text("SELECT count(*) FROM learner_rule_version")).scalar_one()
    print(json.dumps({"database": DEMO_DB, "approved_by_demo_reviewers": approved, "active_demo_rules": active,
                      "learner": {"handle": lhandle, "passphrase": PASS},
                      "teacher": {"handle": thandle, "passphrase": PASS}}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
