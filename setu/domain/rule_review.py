"""Rule review decisions (F1; P-EVAL-11, X-TCH-02). Pure.

Only reviews by native Telugu speakers reviewing in Telugu (`language = te`, `native`) decide a rule's validity;
Hindi reviews judge the explanation and are kept, but do not count here.
- two approvals that agree the contrast category is right → verify;
- two reviews that disagree (approve vs reject, or on the category) → a third reviewer;
- with three or more reviews, the majority decides: at least two approvals whose majority says the category is
  right → verify; at least two rejections → reject; otherwise it still needs a reviewer;
- two rejections → reject; `uncertain` changes nothing (another review is needed).
"""
import dataclasses

DECISIONS = ("approve", "reject", "uncertain")


@dataclasses.dataclass(frozen=True)
class Review:
    reviewer: str
    language: str
    decision: str
    category_ok: bool
    native: bool


@dataclasses.dataclass(frozen=True)
class Decision:
    state: str  # pending | needs_third | verify | reject
    approvers: tuple = ()


def decide(reviews) -> Decision:
    te = [r for r in reviews if r.language == "te" and r.native]
    approve = [r for r in te if r.decision == "approve"]
    reject = [r for r in te if r.decision == "reject"]
    if len(reject) >= 2:
        return Decision("reject")
    if len(te) >= 3:
        if len(approve) >= 2 and sum(r.category_ok for r in te) * 2 > len(te):
            return Decision("verify", tuple(r.reviewer for r in approve if r.category_ok))
        return Decision("needs_third")
    if len(te) == 2:
        a, b = te
        if a.decision == b.decision == "approve":
            if a.category_ok and b.category_ok:
                return Decision("verify", (a.reviewer, b.reviewer))
            return Decision("needs_third")
        if {a.decision, b.decision} == {"approve", "reject"}:
            return Decision("needs_third")
    return Decision("pending")
