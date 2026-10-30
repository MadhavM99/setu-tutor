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
GRANT_PLAN = {
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

# Sequences used by identity-less tables: only the ledger sequence, used by the writer via its trigger.
SEQUENCE_GRANTS = {"event_ledger_id_seq": ("setu_writer",)}


def grant_statements():
    stmts = [
        "REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC",
        "REVOKE CREATE ON SCHEMA public FROM PUBLIC",
    ]
    for role in ROLES:
        stmts.append(f"GRANT USAGE ON SCHEMA public TO {role}")
    for role, specs in GRANT_PLAN.items():
        for table, privs, cols in specs:
            if cols:
                collist = ", ".join(cols)
                for p in privs.split(","):
                    stmts.append(f"GRANT {p.strip()} ({collist}) ON public.{table} TO {role}")
            else:
                stmts.append(f"GRANT {privs} ON public.{table} TO {role}")
    for seq, roles in SEQUENCE_GRANTS.items():
        for role in roles:
            stmts.append(f"GRANT USAGE ON SEQUENCE public.{seq} TO {role}")
    return stmts


def revoke_statements():
    return [f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {r}" for r in ROLES] + [
        f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM {r}" for r in ROLES
    ] + [f"REVOKE USAGE ON SCHEMA public FROM {r}" for r in ROLES]
