"""The match game: which words a round holds and how it is marked. Pure and seeded.

A round pairs up to four words the learner has already met with their meanings (or with their pictures). It is a
repetition game, not a lesson: it never introduces a word, and its answers go to the learner's flash-card schedule
only, with no skill evidence, because choosing among four shared answers lets a learner finish by elimination.
"""
import dataclasses
import datetime as dt
import random

ROUND_SIZE = 4
MIN_WORDS = 3  # fewer met words than this and there is nothing to pair


@dataclasses.dataclass(frozen=True)
class Word:
    id: str
    telugu: str
    meaning: str
    has_picture: bool = False
    due: dt.datetime | None = None


def pick_round(words, *, now: dt.datetime, seed, size: int = ROUND_SIZE) -> list:
    """Due words first (the game then helps the review), then the rest in a seeded shuffle. [] if too few."""
    words = list(words)
    if len(words) < MIN_WORDS:
        return []
    rng = random.Random(f"match:{seed}")
    due = sorted((w for w in words if w.due is not None and w.due <= now), key=lambda w: (w.due, w.id))
    rest = [w for w in words if w not in due]
    rng.shuffle(rest)
    return (due + rest)[:min(size, len(words))]


def round_mode(chosen, *, seed) -> str:
    """'picture' when every word has a picture and the seed says so (about half of such rounds); else 'meaning'."""
    if len(chosen) >= MIN_WORDS and all(w.has_picture for w in chosen) and random.Random(f"mode:{seed}").random() < .5:
        return "picture"
    return "meaning"


def option_order(chosen, *, seed) -> list:
    """The shared answer list, shuffled once per round so the order is not the order of the words."""
    ids = [w.id for w in chosen]
    random.Random(f"opts:{seed}").shuffle(ids)
    return ids


def summary(results) -> str:
    """'great' (all right), 'good' (more right than wrong), 'keep' (the rest). Drives the encouragement line."""
    right = sum(1 for ok in results if ok)
    return "great" if right == len(results) else "good" if right * 2 >= len(results) else "keep"
