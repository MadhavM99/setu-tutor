# ADR-0003: Self-hosted models only at runtime

**Status:** accepted (user decision D3)

## Context

- The paper says learner data stays on our own server and no commercial API sees learner text (§9).
- setu-tutor currently sends model calls to Google AI Studio, including learner questions via Didi.

## Decision

- Runtime uses only an OpenAI-compatible client (vLLM, Ollama or LM Studio) or a mock. The Gemini and image clients are removed.
- Gemma 3 12B is the baseline. Models are swappable, and a bake-off is run for each language direction.
- Commercial APIs may be used only offline, to draft non-learner content that a teacher reviews.

## Consequences

- A GPU host is needed for evaluations (R-20).
- An egress allow-list test enforces the decision.
