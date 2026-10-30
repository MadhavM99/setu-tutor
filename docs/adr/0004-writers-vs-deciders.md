# ADR-0004: Models write, rules decide; one writer of learning state

**Status:** accepted (paper requirements P-ARCH-01, P-CLS-*; prompt rule X-RULES-06)

## Decision

Language models (classmate, coach, native friend):
- only produce text;
- call only read-only tools;
- have every output validated before it is shown.

OutcomeWriter is the only code that writes learning state:
- mastery
- FSRS
- the classmate's state
- the event ledger

It accepts only checker verdicts or signed teacher resolutions. This is enforced by types, import rules and Postgres grants (E-01).

A smaller model is not used as the "weak" classmate. It would be weak in uncontrolled ways rather than missing exactly the untaught rules (paper §2).

## Consequences

- Injection cannot change state (target M-14 = 0).
- Every state change is auditable.
