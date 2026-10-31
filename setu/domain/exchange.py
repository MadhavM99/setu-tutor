"""Correction exchange v1 (P-SESS-07..11, P8b-02, F-EXCH, F-COACH, F-OWN; session-and-exchange.md §3–4). Pure.

One exchange is one planned turn: the classmate's planted sentence, a no-error sentence, or the learner's own
sentence for a Hindi meaning. The step ladder after each checked answer:
- the first answer is cue-free (`answer`, attempt 1);
- a wrong or partial answer gets one fixed hint (`hint`, attempt 2; the hint never contains the corrected form);
- a second miss shows the correct sentence and asks the learner to type it once (`copy`, attempt 3, after reveal:
  never mastery evidence and never teaches the classmate);
- a false alarm on a no-error turn closes with the sentence shown as already right;
- unsure closes at once (a teacher decides; nothing is updated);
- after every third checked, cue-free correct fix the learner is asked "why?" (`why`). The explanation is checked
  and logged but changes neither mastery nor the classmate (P8b-02).
Then the exchange closes with the planted error shown next to its correction (R-13).
"""
import dataclasses
import random
from collections.abc import Sequence

from . import leakfilter

VERSION = "exchange-1"
WHY_EVERY = 3
NEW_RULES_PER_SESSION = 2
HINT_ORDER = ("recast", "l1_rule", "contrast")
COPY_REASONS = ("planted_error_present", "planted_error_unchanged")


@dataclasses.dataclass(frozen=True)
class Answer:
    n: int
    kind: str  # the verdict kind: fix | no_error | own | explanation
    outcome: str


@dataclasses.dataclass(frozen=True)
class Step:
    name: str  # answer | hint | copy | why | close
    n: int | None = None  # the attempt number the step asks for
    revealed: bool = False


@dataclasses.dataclass(frozen=True)
class OwnRule:
    rule_id: str
    ready: bool  # the learner has a checked, cue-free correct answer on the rule
    seen: bool  # the rule has been introduced to the learner before


@dataclasses.dataclass(frozen=True)
class ItemView:
    item_id: str
    version_id: object
    rule_id: str


def step(kind: str, answers: Sequence[Answer], *, why_due: bool) -> Step:
    """The next step of an exchange of `kind` (planted | no_error | own) after the checked `answers`."""
    if not answers:
        return Step("answer", 1)
    last = max(answers, key=lambda x: x.n)
    if last.kind == "explanation" or last.outcome == "unsure":
        return Step("close")
    if last.outcome == "correct":
        if kind == "planted" and last.n == 1 and why_due:
            return Step("why", 2)
        return Step("close")
    if kind == "no_error" or last.n >= 3:
        return Step("close")
    if last.n == 1:
        return Step("hint", 2)
    return Step("copy", 3, revealed=True)


def asks_why(correct_fixes: int) -> bool:
    """True when this checked correct fix is the third, sixth, ... one (P8b-02)."""
    return correct_fixes > 0 and correct_fixes % WHY_EVERY == 0


def choose_hint(hints: Sequence[tuple[str, str]], item, *, only: str | None = None) -> tuple[str, str | None]:
    """The first approved hint (in HINT_ORDER, or only the `only` type for the hint-type arm) that passes
    `check_hint_has_no_answer`; otherwise the generic template (`None` text: the catalog line is shown)."""
    order = (only,) if only else HINT_ORDER
    for t in order:
        for kind, text in hints:
            if kind == t and not leakfilter.check_hint(item, text):
                return kind, text
    return "generic", None


def own_rule(rules: Sequence[OwnRule], *, new_this_session: int, seed: int, turn: int):
    """(rule_id, introduce) for an own-sentence turn: an unseen rule first (with its intro card) while fewer than
    NEW_RULES_PER_SESSION were introduced this session, otherwise a seeded choice among seen rules."""
    unseen = sorted((r for r in rules if not r.seen), key=lambda r: r.rule_id)
    if unseen and new_this_session < NEW_RULES_PER_SESSION:
        return unseen[0].rule_id, True
    seen = sorted((r for r in rules if r.seen), key=lambda r: r.rule_id)
    if not seen:
        return None
    return random.Random(f"{seed}:own:{turn}").choice(seen).rule_id, False


def pick_item(items: Sequence[ItemView], rule_id: str, *, last_item: str | None, seed: int, turn: int):
    """A practice item of the rule; never the item used last time when the rule has another (spec §5)."""
    pool = sorted((i for i in items if i.rule_id == rule_id), key=lambda i: i.item_id)
    if not pool:
        return None
    fresh = [i for i in pool if i.item_id != last_item] or pool
    return random.Random(f"{seed}:item:{turn}").choice(fresh)


def is_copy(reason_code: str) -> bool:
    """An own sentence that still has the Hindi habit the learner corrected in the classmate (M-37)."""
    return reason_code in COPY_REASONS
