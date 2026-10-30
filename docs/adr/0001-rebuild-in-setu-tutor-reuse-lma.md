# ADR-0001: Rebuild inside setu-tutor, reusing the LMA research repo

**Status:** accepted (user decision D1, 30 Oct 2026)

## Context

There are two codebases:
- **setu-tutor**: a Streamlit product with a letters-first course.
- **LMA**: the team research repo, with the tool contract, agent loop, study conditions, simulator and scorecard.

They duplicate the engine, the checker, the leak filter and the rule bank.

## Decision

setu-tutor is the product. From LMA we port these, with credit:
- `tools.py`, `agent.py`, `state.py`, `ledger.py`, `planner.py`, `script.py`
- the study code, the simulator and the scorecard
- `tests_v0.jsonl`, the teacher-label sheet and the TE→HI bank
- the reviewer and study packs

The LMA repo is shared with the team, so team consent to reuse its code is recorded before porting.

## Consequences

- There is one engine.
- The LMA validity defects are fixed during the port (audit §6).
- The hosted JS app is retired.

## Team consent

Recorded 31 Oct 2026: the user confirmed that the LMA team agrees to its work being reused in setu-tutor (code ports
and the vendored data snapshot under `content/sources/lma-c11a63a/`). Reused material keeps provenance pointing to
the team repository and commit.

