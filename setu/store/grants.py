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

GRANT_PLAN = PLAN_V2  # the current plan

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
