"""Answer-pattern validation (DQ-06, DQ-07; data-model.md item_version).

A pattern is accepted only if it is fully anchored (`^…$` around the whole expression), cannot backtrack
catastrophically, matches no empty string, uses no wildcard, lookaround, backreference or inline flag, and is
written in the item's target script. The checker always applies patterns with `re.fullmatch` on normalised text.
Semantic checks then make sure accept patterns accept the right sentence and nothing shorter or wrong, and wrong
patterns catch the planted error but never a correct answer.
"""
import difflib
import re
import re._constants as C
import re._parser as sre_parse

from .schema import LATIN, OTHER_SCRIPT, Issue, normalise_sentence

MAX_LEN = 300
MAX_REPEAT = 10
INLINE_FLAG = re.compile(r"\(\?[aiLmsux-]")
ALLOWED_CATEGORIES = {C.CATEGORY_SPACE, C.CATEGORY_DIGIT}


def check_pattern(pattern: str, *, script: str) -> list[Issue]:
    issues: list[Issue] = []

    def add(code, detail=""):
        if code not in {i.code for i in issues}:
            issues.append(Issue(code, detail))

    if "\n" in pattern or "\r" in pattern:
        add("newline")
    if len(pattern) > MAX_LEN:
        add("too_long", f"{len(pattern)} > {MAX_LEN} characters")
    if INLINE_FLAG.search(pattern):
        add("inline_flag")
        return issues
    try:
        re.compile(pattern)
        parsed = sre_parse.parse(pattern)
    except re.error as e:
        add("invalid_regex", str(e))
        return issues

    top = list(parsed)
    # `^a|b$` parses as one branch whose alternatives hold the anchors; `^(?:a|b)$` keeps them outside.
    if any(op is C.BRANCH and any(o is C.AT for b in av[1] for o, _ in b) for op, av in top):
        add("top_level_alternation", "anchors bind only the outer alternatives; wrap them in a group")
    if not (top and top[0] == (C.AT, C.AT_BEGINNING) and top[-1] == (C.AT, C.AT_END)):
        add("not_anchored", "the whole pattern must be written as ^…$")
    inner = top[1:-1] if len(top) >= 2 else top

    def walk(items, inside_repeat=False):
        for op, av in items:
            if op is C.AT:
                add("not_anchored", "anchors may appear only at the very start and end")
            elif op in (C.ASSERT, C.ASSERT_NOT):
                add("lookaround")
                walk(av[1], inside_repeat)
            elif op in (C.GROUPREF, C.GROUPREF_EXISTS):
                add("backreference")
            elif op is C.ANY:
                add("wildcard", "'.' matches anything")
            elif op is C.CATEGORY:
                if av not in ALLOWED_CATEGORIES:
                    add("wildcard", "character categories other than \\s and \\d")
            elif op is C.IN:
                if any(o is C.NEGATE for o, _ in av):
                    add("wildcard", "negated character class")
                for o, a in av:
                    if o is C.CATEGORY and a not in ALLOWED_CATEGORIES:
                        add("wildcard", "character categories other than \\s and \\d")
            elif op is C.SUBPATTERN:
                walk(av[-1], inside_repeat)
            elif op is C.BRANCH:
                if inside_repeat:
                    add("nested_repeat", "alternation under a repeat can backtrack exponentially")
                for branch in av[1]:
                    walk(branch, inside_repeat)
            elif op in (C.MAX_REPEAT, C.MIN_REPEAT, getattr(C, "POSSESSIVE_REPEAT", None)):
                _lo, hi, sub = av
                if hi is C.MAXREPEAT or hi > MAX_REPEAT:
                    add("unbounded_or_large_repeat", "use ? or a small {m,n}")
                if inside_repeat or _contains_repeat(sub):
                    add("nested_repeat", "a repeat inside a repeat can backtrack exponentially")
                walk(sub, True)

    walk(inner)

    if re.fullmatch(pattern, "") is not None:
        add("matches_empty")

    literals = "".join(chr(av) for op, av in _iter_literals(parsed))
    if LATIN.search(literals) or OTHER_SCRIPT[script].search(literals):
        add("wrong_script", f"pattern must be written in {script} script")
    return issues


def _contains_repeat(items) -> bool:
    for op, av in items:
        if op in (C.MAX_REPEAT, C.MIN_REPEAT, getattr(C, "POSSESSIVE_REPEAT", None)):
            return True
        if op is C.SUBPATTERN and _contains_repeat(av[-1]):
            return True
        if op is C.BRANCH and any(_contains_repeat(b) for b in av[1]):
            return True
    return False


def _iter_literals(items):
    for op, av in items:
        if op is C.LITERAL:
            yield op, av
        elif op is C.IN:
            for o, a in av:
                if o is C.LITERAL:
                    yield o, a
                elif o is C.RANGE:
                    yield C.LITERAL, a[0]
                    yield C.LITERAL, a[1]
        elif op is C.SUBPATTERN:
            yield from _iter_literals(av[-1])
        elif op is C.BRANCH:
            for b in av[1]:
                yield from _iter_literals(b)
        elif op in (C.MAX_REPEAT, C.MIN_REPEAT, C.ASSERT, C.ASSERT_NOT):
            yield from _iter_literals(av[-1] if op in (C.MAX_REPEAT, C.MIN_REPEAT) else av[1])


def _fragments(sentence: str):
    tokens = sentence.split()
    n = len(tokens)
    for length in range(1, n):
        for start in range(n - length + 1):
            yield " ".join(tokens[start:start + length])


def check_item_patterns(*, correct, accepted, wrong, accept_patterns, wrong_patterns, script) -> list[Issue]:
    """Semantic checks for patterns that are individually valid (call check_pattern first)."""
    issues: list[Issue] = []
    correct = normalise_sentence(correct)
    wrong = normalise_sentence(wrong) if wrong else None
    accepted = [normalise_sentence(a) for a in accepted] or [correct]
    for p in accept_patterns:
        if not re.fullmatch(p, correct):
            issues.append(Issue("misses_correct_form", p))
        if wrong and re.fullmatch(p, wrong):
            issues.append(Issue("accepts_wrong_form", p))
        hit = next((f for form in accepted for f in _fragments(form) if re.fullmatch(p, f)), None)
        if hit:
            issues.append(Issue("accepts_fragment", f"{p} accepts '{hit}'"))
    for p in wrong_patterns:
        if wrong and not re.fullmatch(p, wrong):
            issues.append(Issue("misses_wrong_form", p))
        if any(re.fullmatch(p, form) for form in [correct, *accepted]):
            issues.append(Issue("rejects_correct_form", p))
    return issues


def one_error_span(*, wrong: str, correct: str):
    """Locate the planted error as one contiguous token span of the wrong sentence.

    Returns (span, issue). span is [start, end) character offsets into the normalised wrong sentence, or None.
    issue is None (exactly one error), 'omission_error' (the error is a missing word: no span to mark),
    'more_than_one_error' or 'no_error'.
    """
    wrong, correct = normalise_sentence(wrong), normalise_sentence(correct)
    w, c = wrong.split(), correct.split()
    ops = [op for op in difflib.SequenceMatcher(a=w, b=c, autojunk=False).get_opcodes() if op[0] != "equal"]
    if not ops:
        return None, "no_error"
    if len(ops) > 1:
        return None, "more_than_one_error"
    tag, i1, i2, _, _ = ops[0]
    if tag == "insert":
        return None, "omission_error"
    starts = []
    pos = 0
    for tok in w:
        starts.append(pos)
        pos += len(tok) + 1
    start = starts[i1]
    end = starts[i2 - 1] + len(w[i2 - 1])
    return [start, end], None
