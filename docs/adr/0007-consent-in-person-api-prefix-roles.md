# ADR-0007: Consent is collected in person; `/api` is the JSON prefix; the five-role model stands

**Status:** accepted (user decisions, 31 Oct 2026)

## Decisions

1. **Consent (D5).** Every learner gives consent in person to the facilitator before receiving an invite, for all
   scopes. The app does not ask for consent and shows no consent screens or endpoints. When an invite is
   redeemed, the app records the in-person consent (`form_version = in-person-v1`, all scopes), so the
   database rule "no session without consent" keeps holding and the record shows how consent was obtained.
   Withdrawal also happens in person; a researcher records it with
   `POST /api/research/participants/{id}/withdraw`, which runs `setu_withdraw_consent()` (raw learner text
   redacted, background deleted, sessions revoked).
2. **`/api` prefix.** JSON endpoints live under `/api`; the Hindi pages use the plain paths.
3. **Roles.** The five database roles (`setu_read`, `setu_app`, `setu_writer`, `setu_content`, `setu_migrate`)
   are accepted. Withdrawal keeps learning state (the default). Sign-in and role checks remain: they protect
   learners' records and are not part of consent.

## Consequences

- The slice 1.5–1.6 consent page, `GET/POST /api/consent`, `POST /api/consent/withdraw`, the consent catalog
  strings and the pending consent-text gate were removed. Gate G4 no longer needs an in-app consent text; the
  paper forms and the ethics approval stay with the facilitator.
- The traceability rows P-ETH-04 and P8b-12 are met by the in-person process plus the automatic record.
