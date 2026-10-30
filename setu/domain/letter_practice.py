"""Letter and akshara practice: which task comes next (X-LAD-L0/L1, P8b-04, R-INPUT). Pure and seeded.

A new letter goes through a short chain: see it with its Devanagari twin (`intro`), pick it among a few approved
letters (`choice`: multiple choice, recognition, an assisted cue), recognise it on the full on-screen Devanagari
keyboard (`recognise`: cue-free) and recall it on the full on-screen Telugu keyboard (`recall`: cue-free). After a
wrong answer the rest of the chain counts as "after reveal" and is not mastery evidence. Due reviews come before new
letters, and at most `new_cap` new letters are introduced per day.

Aksharas (L1) use the same chain over units. With `intro_per_group`, only the first unit of a group (one vowel
sign, say) gets the intro card; later units of that group start at the choice step. Choice distractors come from
units with the same `confusable` key first (for aksharas: the same consonant with other signs).
"""
import dataclasses
import datetime as dt
import random

CHAIN = ("intro", "choice", "recognise", "recall")
MODALITY = {"choice": "REC", "recognise": "REC", "recall": "RCL"}


@dataclasses.dataclass(frozen=True)
class LetterView:
    id: str
    telugu: str
    devanagari: str
    label: str
    group: str
    order: int
    confusable: str | None = None  # distractor key; defaults to the group


UnitView = LetterView


@dataclasses.dataclass(frozen=True)
class CardView:
    letter_id: str
    modality: str  # REC | RCL
    due: dt.datetime | None


@dataclasses.dataclass(frozen=True)
class Task:
    type: str  # intro | choice | recognise | recall
    letter_id: str
    options: tuple = ()
    chain: tuple = ()  # the steps still to come for this letter
    revealed: bool = False
    new: bool = False  # the first step for a unit the learner has not seen (counts against the daily cap)


def next_task(*, letters, cards, pending: Task | None, now: dt.datetime, new_today: int, seed: int,
              new_cap: int = 5, intro_per_group: bool = False) -> Task | None:
    letters = sorted(letters, key=lambda x: x.order)
    if not letters:
        return None
    by_id = {x.id: x for x in letters}
    if pending is not None and pending.chain and pending.letter_id in by_id:
        step = pending.chain[0]
        return _make(step, by_id[pending.letter_id], letters, pending.chain[1:], pending.revealed, seed)
    due = sorted((c for c in cards if c.letter_id in by_id and c.due is not None and c.due <= now),
                 key=lambda c: (c.due, by_id[c.letter_id].order))
    if due:
        c = due[0]
        return _make("recall" if c.modality == "RCL" else "recognise", by_id[c.letter_id], letters, (), False, seed)
    seen = {c.letter_id for c in cards}
    fresh = [x for x in letters if x.id not in seen]
    if fresh and new_today < new_cap:
        unit = fresh[0]
        introduced = {by_id[i].group for i in seen if i in by_id}
        if intro_per_group and unit.group in introduced:
            return dataclasses.replace(_make("choice", unit, letters, CHAIN[2:], False, seed), new=True)
        return Task("intro", unit.id, chain=CHAIN[1:], new=True)
    return None


def _make(step, letter, letters, rest, revealed, seed) -> Task:
    if step != "choice":
        return Task(step, letter.id, chain=tuple(rest), revealed=revealed)
    rng = random.Random(f"{seed}:{letter.id}")
    key = letter.confusable or letter.group
    same_group = [x for x in letters if (x.confusable or x.group) == key and x.id != letter.id]
    others = [x for x in letters if x.id != letter.id and x not in same_group]
    distractors = rng.sample(same_group, k=min(3, len(same_group)))  # look-alike letters of the same row first
    distractors += rng.sample(others, k=min(3 - len(distractors), len(others)))
    options = [letter, *distractors]
    rng.shuffle(options)
    return Task("choice", letter.id, options=tuple(x.id for x in options), chain=tuple(rest), revealed=revealed)


def after_answer(task: Task, outcome: str) -> Task:
    """The task as it continues after an answer: a wrong answer reveals the letter for the rest of the chain."""
    return dataclasses.replace(task, revealed=task.revealed or outcome != "correct")
