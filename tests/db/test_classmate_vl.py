"""classmate_vl (migration 0006): a learner's seen words come from their word cards and the item sentences shown to
them, and are readable by the agents' read-only role."""
from sqlalchemy import text

from .helpers import make_learner, make_rule, make_rule_version


def test_seen_words_come_from_cards_and_shown_items(conn):
    learner, other = make_learner(conn), make_learner(conn)
    conn.execute(text("INSERT INTO lexeme (id, telugu, hindi_gloss) VALUES ('te:అవును', 'అవును', 'हाँ')"))
    conn.execute(text("INSERT INTO learner_lexeme_card (learner_id, card_kind, card_ref, modality) VALUES "
                      "(:l, 'lexeme', 'te:అవును', 'RCL')"), {"l": learner})
    make_rule(conn)
    rv = make_rule_version(conn)
    conn.execute(text("INSERT INTO item (id, rule_id) VALUES ('HI-TE-001-a', 'HI-TE-001')"))
    iv = conn.execute(text("INSERT INTO item_version (item_id, version, rule_version_id, correct_form, pool) VALUES "
                           "('HI-TE-001-a', 1, :rv, 'నువ్వు వస్తావా', 'practice') RETURNING id"), {"rv": rv}).scalar_one()
    s = conn.execute(text("INSERT INTO session (learner_id, mode, config_snapshot, seed) VALUES (:l, 'learn', '{}', 1) "
                          "RETURNING id"), {"l": learner}).scalar_one()
    conn.execute(text("INSERT INTO exchange (session_id, kind, item_version_id, source) VALUES (:s, 'learn', :iv, "
                      "'bank')"), {"s": s, "iv": iv})
    conn.execute(text("SET ROLE setu_read"))
    forms = set(conn.execute(text("SELECT form FROM classmate_vl WHERE learner_id = :l"), {"l": learner}).scalars())
    none = conn.execute(text("SELECT count(*) FROM classmate_vl WHERE learner_id = :l"), {"l": other}).scalar_one()
    conn.execute(text("RESET ROLE"))
    assert forms == {"అవును", "నువ్వు", "వస్తావా"} and none == 0
