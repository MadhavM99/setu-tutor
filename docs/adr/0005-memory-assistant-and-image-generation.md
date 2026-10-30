# ADR-0005: Memory Assistant, plus where image and mnemonic generation is allowed

**Status:** accepted (Phase 0 amendment A1, 30 Oct 2026). Amends ADR-0003 and the legacy-migration rows for `aids.py`.

## Context

The approved package removed AI pictures and tricks from runtime because they were unreviewed, slow and gimmicky. Amendment A1 asks for a first-class Memory Assistant with:
- visual mnemonics;
- image generation without embedded text;
- an approved asset library;
- measured effects;
- no identifiable learner data sent to external image services.

## Decision

1. **Generation is an offline content-pipeline activity, never per learner at runtime.**
   - Images and mnemonic drafts are generated in batches from concept-level prompts.
   - They go through automated checks (OCR text, grounding validator) and then teacher review.
   - Only approved, versioned assets reach learners.
   - The runtime app has no image-generation client.
2. **Providers.** A self-hosted open image model is preferred. An external image service is permitted **only** in the offline pipeline environment, with an allow-listed request schema containing concept fields only. ADR-0003 still holds for runtime.
3. **Glyphs and Hindi text are always rendered by the app from fonts and the catalog**, never drawn by a model.
4. **Runtime verbal mnemonic generation** stays behind the flag `mem_runtime_verbal`, off until gate G-MEM-RT.
5. **Every concept has a non-generative fallback.**
6. **Aids never confer mastery.** Only cue-free checked attempts do.

## Consequences

- The legacy `aids.py` ideas are reused (font overlay, SVG sanitiser, text check) inside the offline pipeline.
- There is a budget file and a cost ledger.
- Teacher review load rises, so concepts are prioritised by level.
