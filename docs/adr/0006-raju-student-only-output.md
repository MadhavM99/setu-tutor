# ADR-0006: Raju produces only weaker-student text

**Status:** accepted (user request, 30 Oct 2026). Spec: `specs/classmate-output-contract.md`.

## Context

A general-purpose LLM drifts toward assistant behaviour: helping, explaining, greeting, answering questions, formatting. The legacy app let the model write Raju's Hindi lines as a playful persona.

## Decision

- Raju has a **closed set of turn types**.
- The model fills **only** the L2 sentence slot. It must be one sentence, within VL, with exactly one planted error (or none).
- Every Hindi line Raju says comes from fixed, approved catalog templates chosen deterministically.
- Learners have no free chat with Raju.
- A deterministic student-only filter rejects assistant, teacher, formatting, gloss, answer-leak and competence-ceiling violations. Failures fall back to bank sentences.
- Persona breaks shown to learners must be 0 (M-56).

## Consequences

- Raju is less "lively" than the legacy version, but cannot act as an assistant or out-know the learner.
- Liveliness, if wanted later, comes from more approved template variants, not from model-written chatter.
