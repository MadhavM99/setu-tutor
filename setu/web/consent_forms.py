"""Consent forms the app can record. The Hindi text lives in the catalog under `text_key` (slice 1.6) and must be
the version approved by the institute's ethics process before any pilot learner signs it (gate G4)."""

FORMS = {
    "pilot-v1": {
        "scopes": ("pilot", "audio", "writing_upload", "data_sharing"),
        "text_key": "consent.pilot_v1",
        "status": "draft: awaiting ethics approval",
    },
}
CURRENT = "pilot-v1"


def signable(app_state, version: str) -> bool:
    """A form can be signed only when its approved text is in the catalog (or in development/test builds)."""
    form = FORMS.get(version)
    if form is None:
        return False
    catalog = app_state.catalog
    approved = catalog.has(form["text_key"]) and not catalog.is_pending(form["text_key"])
    return approved or app_state.allow_unapproved_consent
