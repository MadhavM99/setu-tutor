"""Database roles and privileges (E-01, architecture.md §2).

| Role          | Used by                                   | May write                                         |
|---------------|-------------------------------------------|---------------------------------------------------|
| setu_read     | agents' read-only tools                   | nothing                                           |
| setu_app      | web layer                                 | operational records (sessions, attempts, logs)   |
| setu_writer   | OutcomeWriter only                        | verdicts, learning state, append to the ledger   |
| setu_content  | content importer, teacher review          | content and its reviews (never learner data)     |
| setu_migrate  | migrations (owner)                        | schema                                            |

Every table must appear here; tests fail on a table without an explicit decision. All roles are NOLOGIN
group roles; deployments create login users and grant membership. Nobody gets DELETE or TRUNCATE.
"""

ROLES = ("setu_read", "setu_app", "setu_writer", "setu_content")

# Learner columns visible to roles that must not see secrets.
LEARNER_PUBLIC_COLUMNS = ("id", "handle", "l1", "l2", "direction", "role", "created_at", "cohort",
                          "romanisation_enabled")

CONTENT = ("data_source", "skill", "skill_prereq", "lexeme", "rule", "rule_version", "item", "item_version",
           "accepted_variant", "hint", "scene", "scene_line", "own_task", "concept", "technique_policy",
           "memory_aid", "visual_asset", "audio_asset")
STATE = ("learner_skill_state", "learner_lexeme_card", "classmate_rule_state", "concept_cue_state",
         "technique_effect")
OPERATIONAL = ("consent", "background", "session", "exchange", "attempt", "model_call", "tool_call",
               "aid_event", "study", "study_assignment", "test_administration", "blind_mark")
OUTCOMES = ("verdict", "fsrs_review_log", "copy_event", "aid_misassociation", "teacher_queue_item",
            "teacher_resolution", "teacher_override", "event_ledger")
CONTENT_WORK = ("rule_review", "kappa_report", "content_proposal", "generation_cost")

# (table, privileges, columns or None). Column lists restrict SELECT/UPDATE to those columns.
PLAN_V1 = {
    "setu_read": [
        *[(t, "SELECT", None) for t in CONTENT + STATE],
        ("learner", "SELECT", LEARNER_PUBLIC_COLUMNS),
    ],
    "setu_app": [
        *[(t, "SELECT", None) for t in CONTENT + STATE + OUTCOMES + CONTENT_WORK],
        ("learner", "SELECT, INSERT", None),
        ("learner", "UPDATE", ("passphrase_hash", "romanisation_enabled")),
        *[(t, "SELECT, INSERT", None) for t in OPERATIONAL],
        ("consent", "UPDATE", ("withdrawn_at",)),
        ("session", "UPDATE", ("ended_at", "time_on_task_s")),
    ],
    "setu_writer": [
        *[(t, "SELECT", None) for t in CONTENT + OPERATIONAL + CONTENT_WORK],
        ("learner", "SELECT", LEARNER_PUBLIC_COLUMNS),
        *[(t, "SELECT, INSERT, UPDATE", None) for t in STATE],
        *[(t, "SELECT, INSERT", None) for t in OUTCOMES],
        ("teacher_queue_item", "UPDATE", ("status",)),
        ("content_proposal", "INSERT", None),  # a teacher resolution may propose a variant
    ],
    "setu_content": [
        *[(t, "SELECT, INSERT", None) for t in CONTENT + CONTENT_WORK],
        ("learner", "SELECT", LEARNER_PUBLIC_COLUMNS),
        *[(t, "UPDATE", None) for t in ("data_source", "skill", "lexeme", "scene", "scene_line", "own_task",
                                         "concept", "technique_policy", "visual_asset", "audio_asset")],
        ("accepted_variant", "UPDATE", ("status", "approvals")),
        ("content_proposal", "UPDATE", ("status",)),
        ("memory_aid", "UPDATE", ("review_status", "reviewers", "retired_reason")),
        ("aid_event", "SELECT", None),  # per-aid effect estimates for review
    ],
}


# Plan V2 (migration 0003, slice 1.4): the agents' read role no longer sees draft or unreviewed content at all.
# It reads learner-visible content only through the learner_* views, which show verified, teacher-approved,
# current versions (no unreviewed Telugu reaches learners or the model-facing tools).
DRAFT_BEARING = ("rule_version", "item_version", "accepted_variant", "hint", "scene", "scene_line", "own_task",
                 "lexeme", "memory_aid", "visual_asset", "audio_asset")
LEARNER_VIEWS = ("learner_rule_version", "learner_item_version", "learner_accepted_variant", "learner_hint",
                 "learner_lexeme", "learner_scene", "learner_scene_line", "learner_own_task", "learner_memory_aid")

PLAN_V2 = {role: list(specs) for role, specs in PLAN_V1.items()}
PLAN_V2["setu_read"] = [s for s in PLAN_V1["setu_read"] if s[0] not in DRAFT_BEARING]
VIEW_GRANTS = {view: ("setu_read", "setu_app", "setu_writer", "setu_content") for view in LEARNER_VIEWS}

# Plan V3 (migration 0004, slice 1.5): accounts. Only the web layer touches invites, sessions and login attempts;
# no other role can read them. Consent withdrawal runs through `setu_withdraw_consent()` (EXECUTE: setu_app).
PLAN_V3 = {role: list(specs) for role, specs in PLAN_V2.items()}
PLAN_V3["setu_app"] += [
    ("invite", "SELECT, INSERT", None),
    ("invite", "UPDATE", ("used_at", "used_by")),
    ("auth_session", "SELECT, INSERT", None),
    ("auth_session", "UPDATE", ("revoked_at",)),
    ("login_attempt", "SELECT, INSERT", None),
]

# Plan V4 (migration 0007, slice 2.6): skill evidence. Written only by the OutcomeWriter (insert; immutable),
# readable by the read and web roles.
PLAN_V4 = {role: list(specs) for role, specs in PLAN_V3.items()}
PLAN_V4["setu_read"] += [("skill_evidence", "SELECT", None)]
PLAN_V4["setu_app"] += [("skill_evidence", "SELECT", None)]
PLAN_V4["setu_writer"] += [("skill_evidence", "SELECT, INSERT", None)]

# Plan V5 (migration 0008, slice S1): letters. Content writes them; the web layer and the writer read them; the
# read role sees approved letters only through `learner_letter`.
PLAN_V5 = {role: list(specs) for role, specs in PLAN_V4.items()}
PLAN_V5["setu_content"] += [("letter", "SELECT, INSERT, UPDATE", None)]
PLAN_V5["setu_app"] += [("letter", "SELECT", None)]
PLAN_V5["setu_writer"] += [("letter", "SELECT", None)]
VIEW_GRANTS_V2 = {**VIEW_GRANTS, "learner_letter": VIEW_GRANTS["learner_rule_version"],
                  "classmate_vl": ("setu_read", "setu_app", "setu_writer")}

# Plan V6 (migration 0009, slice S2): aksharas, like letters.
PLAN_V6 = {role: list(specs) for role, specs in PLAN_V5.items()}
PLAN_V6["setu_content"] += [("akshara", "SELECT, INSERT, UPDATE", None)]
PLAN_V6["setu_app"] += [("akshara", "SELECT", None)]
PLAN_V6["setu_writer"] += [("akshara", "SELECT", None)]
VIEW_GRANTS_V3 = {**VIEW_GRANTS_V2, "learner_akshara": VIEW_GRANTS["learner_rule_version"]}

# Plan V7 (migration 0011, slice S4): chunks, like aksharas.
PLAN_V7 = {role: list(specs) for role, specs in PLAN_V6.items()}
PLAN_V7["setu_content"] += [("chunk", "SELECT, INSERT, UPDATE", None)]
PLAN_V7["setu_app"] += [("chunk", "SELECT", None)]
PLAN_V7["setu_writer"] += [("chunk", "SELECT", None)]
VIEW_GRANTS_V4 = {**VIEW_GRANTS_V3, "learner_chunk": VIEW_GRANTS["learner_rule_version"]}

# Plan V8 (migration 0012, slice S8): L5 scene scripts and reply variants are draft-bearing content (the read role
# sees them only through the learner views); scene telemetry is an operational record written by the web layer.
PLAN_V8 = {role: list(specs) for role, specs in PLAN_V7.items()}
PLAN_V8["setu_content"] += [(t, "SELECT, INSERT, UPDATE", None) for t in ("scene_script", "scene_reply_variant")]
PLAN_V8["setu_app"] += [("scene_script", "SELECT", None), ("scene_reply_variant", "SELECT", None),
                        ("scene_event", "SELECT, INSERT", None)]
PLAN_V8["setu_writer"] += [("scene_script", "SELECT", None), ("scene_reply_variant", "SELECT", None),
                           ("scene_event", "SELECT", None)]
VIEW_GRANTS_V5 = {**VIEW_GRANTS_V4, "learner_scene_script": VIEW_GRANTS["learner_rule_version"],
                  "learner_scene_reply_variant": VIEW_GRANTS["learner_rule_version"]}

GRANT_PLAN = PLAN_V8  # the current plan

# Sequences used by identity-less tables: only the ledger sequence, used by the writer via its trigger.
SEQUENCE_GRANTS = {"event_ledger_id_seq": ("setu_writer",)}


def grant_statements(plan=None, views=None):
    """Statements that set privileges to `plan` (default: the current plan) from a clean slate."""
    plan = GRANT_PLAN if plan is None else plan
    views = VIEW_GRANTS if views is None else views
    stmts = [
        "REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC",
        "REVOKE CREATE ON SCHEMA public FROM PUBLIC",
        *[f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {r}" for r in ROLES],
    ]
    for role in ROLES:
        stmts.append(f"GRANT USAGE ON SCHEMA public TO {role}")
    for role, specs in plan.items():
        for table, privs, cols in specs:
            if cols:
                collist = ", ".join(cols)
                for p in privs.split(","):
                    stmts.append(f"GRANT {p.strip()} ({collist}) ON public.{table} TO {role}")
            else:
                stmts.append(f"GRANT {privs} ON public.{table} TO {role}")
    for view, roles in views.items():
        for role in roles:
            stmts.append(f"GRANT SELECT ON public.{view} TO {role}")
    for seq, roles in SEQUENCE_GRANTS.items():
        for role in roles:
            stmts.append(f"GRANT USAGE ON SEQUENCE public.{seq} TO {role}")
    return stmts


def revoke_statements():
    return [f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {r}" for r in ROLES] + [
        f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM {r}" for r in ROLES
    ] + [f"REVOKE USAGE ON SCHEMA public FROM {r}" for r in ROLES]
