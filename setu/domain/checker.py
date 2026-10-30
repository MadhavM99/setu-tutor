"""Deterministic checker v1 (P-ARCH-06, P-SESS-09/10, P-LSP-02, R-INPUT).

The only producer of verdicts. Every check returns exactly one of correct / partial / wrong / unsure, with a fixed
reason code and the checker version; no language model is involved. When the checker cannot tell, it says `unsure`
and the answer goes to a teacher; it never guesses.

Order for a fix of a planted sentence (session-and-exchange.md §3.1):
1. the planted error is still there → wrong (the planted sentence itself, a wrong pattern, or a word that appears in
   the planted sentence and in none of the accepted forms);
2. an accepted form or approved variant (with Hindi-keyboard forgiveness, reported) → correct;
3. an anchored accept pattern, applied with full match → correct;
4. the correct sentence of another item → wrong;
5. one character away from an accepted form and further from the planted sentence → partial (spelling);
6. the fix is right but one non-target word is added or missing → partial;
7. anything else → unsure.
Romanised answers are never automatically correct (X-CHK-01): a transliterated match is `unsure`.
"""
import dataclasses
import re
from collections.abc import Iterable, Mapping

from . import normalise
from .verdict import _CHECKER_CAPABILITY, Verdict

VERSION = "checker-1"
RESPONSE_MODES = ("multiple_choice", "tiles", "onscreen_keyboard", "typed", "spoken")
INDEPENDENT_MODES = ("onscreen_keyboard", "typed", "spoken")
_UNREADABLE = ("too_long", "foreign_script", "mixed_script", "unconvertible", "needs_transliteration")


def _issue_verdict(*, attempt_id, outcome, kind, reason_code, false_alarm=False) -> Verdict:
    """The single place a Verdict is minted. Private: callers use the check_* functions."""
    return Verdict._mint_verdict(_CHECKER_CAPABILITY, attempt_id=attempt_id, outcome=outcome, kind=kind,
                                 reason_code=reason_code, checker_version=VERSION, false_alarm=false_alarm)


@dataclasses.dataclass(frozen=True)
class ItemKey:
    item_id: str
    target_script: str
    correct_form: str
    accepted_forms: Iterable[str] = ()
    wrong_form: str | None = None
    accept_patterns: Iterable[str] = ()
    wrong_patterns: Iterable[str] = ()
    other_items: Mapping[str, Iterable[str]] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True)
class CheckResult:
    verdict: Verdict
    normalised: normalise.Normalised | None = None
    forgiveness: tuple = ()
    matched_form: str | None = None
    response_mode: str | None = None


def _mode(response_mode: str) -> str:
    if response_mode not in RESPONSE_MODES:
        raise ValueError(f"response_mode must be one of {RESPONSE_MODES}")
    return response_mode


def _levenshtein(a: str, b: str, limit: int = 2) -> int:
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


_fold = normalise.forgiving_fold


# ---------------------------------------------------------------- fixes


def check_fix(*, attempt_id, raw: str, item: ItemKey, response_mode: str, no_error_turn: bool = False,
              says_correct: bool = False, transliterator=None) -> CheckResult:
    """Check a learner's correction of the classmate's sentence (or their judgement that it was already right)."""
    mode = _mode(response_mode)
    if mode == "multiple_choice":
        raise ValueError("multiple-choice answers are recognition: use check_choice")
    kind = "no_error" if no_error_turn else "fix"

    def result(outcome, reason, n=None, *, forgiveness=(), matched=None, false_alarm=False):
        v = _issue_verdict(attempt_id=attempt_id, outcome=outcome, kind=kind, reason_code=reason,
                           false_alarm=false_alarm)
        return CheckResult(v, n, forgiveness, matched, mode)

    if says_correct:
        return result("correct", "confirmed_correct") if no_error_turn else result("wrong", "missed_error")

    n = normalise.normalise_answer(raw, target_script=item.target_script, transliterator=transliterator)
    if n.status == "empty":
        return result("wrong", "empty", n)
    if n.status in _UNREADABLE:
        return result("unsure", f"input_{n.status}", n)

    accepted = [normalise.canonical(f) for f in [item.correct_form, *item.accepted_forms] if f]
    outcome, reason, match = _classify(n, item, accepted)
    if n.status == "transliterated":
        return result("unsure", "romanised_match" if outcome == "correct" else f"romanised_{reason}", n)
    forgiveness = match.forgiveness if match else ()
    matched = match.form if match else None
    if no_error_turn:
        if outcome == "correct":
            return result("correct", "confirmed_correct", n, forgiveness=forgiveness, matched=matched)
        return result("wrong", "false_alarm", n, false_alarm=True)
    return result(outcome, reason, n, forgiveness=forgiveness, matched=matched)


def _classify(n: normalise.Normalised, item: ItemKey, accepted: list[str]):
    texts = n.candidates or (n.text,)
    wrong = normalise.canonical(item.wrong_form) if item.wrong_form else None
    accepted_tokens = {t for f in accepted for t in f.split()}
    planted_only = set(wrong.split()) - accepted_tokens if wrong else set()

    # 1. the planted error is still present
    for text in texts:
        folded = _fold(n, text)
        if wrong and (text == wrong or folded == _fold(n, wrong)):
            return "wrong", "planted_error_unchanged", None
        if any(re.fullmatch(p, text) for p in item.wrong_patterns):
            return "wrong", "planted_error_present", None
        if planted_only & set(text.split()):
            return "wrong", "planted_error_present", None
    # 2. accepted forms, with reported forgiveness
    match = normalise.match_forgiving(n, accepted)
    if match:
        return "correct", "accepted_form", match
    # 3. anchored patterns, full match only
    for text in texts:
        if any(re.fullmatch(p, text) for p in item.accept_patterns):
            return "correct", "accepted_pattern", normalise.Match(text, ())
    # 4. another item's correct sentence
    others = [normalise.canonical(f) for forms in item.other_items.values() for f in forms]
    if others and normalise.match_forgiving(n, others):
        return "wrong", "other_item_sentence", None
    # 5. a one-character slip, clearly closer to the right answer than to the planted error
    for text in texts:
        folded = _fold(n, text)
        for form in accepted:
            if _levenshtein(folded, _fold(n, form)) == 1 and (
                    wrong is None or _levenshtein(folded, _fold(n, wrong)) > 1):
                return "partial", "spelling_near_miss", None
    # 6. the fix is right, but one non-target word was added or left out
    target = (set(accepted[0].split()) - set(wrong.split())) if wrong else set()
    for text in texts:
        tokens = _fold(n, text).split()
        for form in accepted:
            ftokens = _fold(n, form).split()
            if target and {_fold(n, t) for t in target} <= set(tokens) and _one_word_apart(tokens, ftokens):
                return "partial", "extra_or_missing_word", None
    return "unsure", "unknown_form", None


def _one_word_apart(a: list[str], b: list[str]) -> bool:
    if abs(len(a) - len(b)) != 1:
        return False
    longer, shorter = (a, b) if len(a) > len(b) else (b, a)
    return any(longer[:i] + longer[i + 1:] == shorter for i in range(len(longer)))


# ---------------------------------------------------------------- recognition and recall


def check_choice(*, attempt_id, chosen: str, correct: str) -> CheckResult:
    """A multiple-choice answer is recognition evidence only (R-INPUT): it never counts as recall."""
    ok = str(chosen) == str(correct)
    v = _issue_verdict(attempt_id=attempt_id, outcome="correct" if ok else "wrong", kind="recognition",
                       reason_code="chose_correct_option" if ok else "chose_other_option")
    return CheckResult(v, None, (), None, "multiple_choice")


def check_recall(*, attempt_id, raw: str, accepted: Iterable[str], target_script: str, response_mode: str,
                 closed: bool = True, transliterator=None) -> CheckResult:
    """Recall of a letter, syllable or word. `closed` items have a fixed answer set (anything else is wrong)."""
    mode = _mode(response_mode)
    if mode == "multiple_choice":
        raise ValueError("multiple-choice answers are recognition: use check_choice")

    def result(outcome, reason, n, match=None):
        v = _issue_verdict(attempt_id=attempt_id, outcome=outcome, kind="recall", reason_code=reason)
        return CheckResult(v, n, match.forgiveness if match else (), match.form if match else None, mode)

    n = normalise.normalise_answer(raw, target_script=target_script, transliterator=transliterator)
    if n.status == "empty":
        return result("wrong", "empty", n)
    if n.status in _UNREADABLE:
        return result("unsure", f"input_{n.status}", n)
    match = normalise.match_forgiving(n, accepted)
    if n.status == "transliterated":
        return result("unsure", "romanised_match" if match else "romanised_unknown", n)
    if match:
        return result("correct", "accepted_form", n, match)
    return result("wrong", "not_accepted", n) if closed else result("unsure", "unknown_form", n)


# ---------------------------------------------------------------- explanations


def check_explanation(*, attempt_id, raw: str, concept_key: Mapping) -> CheckResult:
    """Score a "why?" answer on the rule's key ideas (P-LSP-02). Whole words or phrases only.

    correct: every idea and every relation phrase is present. Without relations in the concept key the checker
    cannot tell an explanation from a list of keywords, so even all ideas give `unsure` (a teacher decides).
    """
    n = normalise.normalise_explanation(raw)
    tokens = normalise.canonical(n.text).split()

    def has(term: str) -> bool:
        words = normalise.canonical(term).split()
        return bool(words) and any(tokens[i:i + len(words)] == words for i in range(len(tokens) - len(words) + 1))

    def result(outcome, reason):
        v = _issue_verdict(attempt_id=attempt_id, outcome=outcome, kind="explanation", reason_code=reason)
        return CheckResult(v, n)

    if not tokens:
        return result("wrong", "empty")
    ideas = [g for g in concept_key.get("ideas", []) if g]
    relations = [g for g in concept_key.get("relations", []) if g]
    found = [any(has(t) for t in group) for group in ideas]
    if not any(found):
        return result("unsure", "no_key_idea")
    if not all(found):
        return result("partial", "some_key_ideas")
    if not relations:
        return result("unsure", "ideas_without_relation")
    if all(any(has(t) for t in group) for group in relations):
        return result("correct", "concept_key_met")
    return result("unsure", "ideas_without_relation")

