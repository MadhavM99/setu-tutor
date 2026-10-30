"""Consent is collected in person by the facilitator before an invite is handed out (decision D5, 31 Oct 2026).

The app does not ask learners for consent and shows no consent screens. When an invite is redeemed it records the
in-person consent (all scopes) so the database can keep enforcing "no session without consent" and the record
shows how consent was obtained. Withdrawal also happens in person; a researcher records it through
`POST /api/research/participants/{id}/withdraw`.
"""

FORMS = {
    "in-person-v1": {
        "scopes": ("pilot", "audio", "writing_upload", "data_sharing"),
        "how": "signed on paper with the facilitator at enrolment",
    },
}
CURRENT = "in-person-v1"
