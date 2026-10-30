"""The data types every part of the tutor talks through.

A *Unit* is one thing to learn: one letter group, one word set, one phrase set, or one grammar rule.
Every unit has the same shape at every level, so the same lesson -> check -> Raju -> follow-ups loop works
for letters on day one and for grammar later.
"""
from __future__ import annotations
from typing import Literal, Optional   # Optional[...] (not X | None): the Mac runs Python 3.9
from pydantic import BaseModel, Field, model_validator

Level = Literal[0, 1, 2, 3]                     # 0 letters · 1 words · 2 phrases · 3 rules
LEVEL_NAMES = {0: "letters", 1: "words", 2: "phrases", 3: "rules"}

Status = Literal["draft_unverified", "native_checked", "teacher_verified"]
Verdict = Literal["correct", "wrong", "unsure"]   # unsure: the checker cannot tell -> a teacher decides
RajuState = Literal["unknown", "learning", "taught", "forgotten"]


class LessonLine(BaseModel):
    """One card the learner sees in the lesson, one at a time, before Raju ever appears.
    The memory hooks (shape, mnemonic, example, picture) are drafted by a model and approved by a native
    speaker once; they are never generated live for a learner."""
    hindi: str                     # what the learner already knows (Devanagari)
    telugu: str                    # the new thing
    note: str = ""                 # one short explanation in Hindi / plain words
    shape: str = ""                # what it looks like, said so it can be pictured
    mnemonic: str = ""             # a tiny story that ties the shape to the sound
    example: str = ""              # a Telugu word the learner already knows from Hindi, e.g. "కమలం = कमल"
    picture: str = ""              # an emoji for that word: the stand-in until a real image is approved
    image: str = ""                # path to an APPROVED picture, relative to data/<pair>/ (e.g. "images/L0-07-b.png").
                                   # The letter in it is drawn from a real font by code (never by an image model);
                                   # the model only draws the object around it. Empty until a person approves one.


class Item(BaseModel):
    """One checkable question. The checker only ever compares against `accepted` and `wrong_forms`.

    Letters (level 0) are asked Telugu -> Hindi: the learner sees క and types क. A Hindi speaker can type
    Devanagari on day one; typing Telugu comes later (otherwise the keyboard, not the letter, is the test)."""
    item_id: str                   # e.g. "L0-03-a"
    prompt: str                    # what the learner sees, e.g. "ఖ" (letters) or "किताब" (words, later)
    accepted: list[str]            # every correct answer
    raju_wrong: str                # Raju's planted mistake for this item ("ఖ = क")
    wrong_forms: list[str] = Field(default_factory=list)   # other known mistakes the checker can name
    answer_script: Literal["devanagari", "telugu", "any"] = "devanagari"
    closed: bool = False           # True: any answer not accepted is simply wrong (one letter, one number);
                                   # False: an unknown answer is 'unsure' and goes to a teacher
    kind: Literal["letter", "word", "sentence"] = "letter"   # sentence: a grammar-rule item (Raju plants the error)
    accept_regex: list[str] = Field(default_factory=list)  # rule items: other right forms (bank 'fix_regex')
    wrong_regex: list[str] = Field(default_factory=list)   # rule items: the planted mistake is still there


class FollowUp(BaseModel):
    """A question Raju asks after the learner fixed him, before he 'knows' the unit."""
    kind: Literal["why", "judge", "boundary"]
    ask: str                       # what Raju says (fixed text, Hindi)
    sentence: str = ""             # Raju's sentence for judge / boundary
    item: Optional[Item] = None       # its checkable answer (judge / boundary)
    sentence_is_correct: bool = False   # judge: True means the right answer is "no mistake"
    key_ideas: list[list[str]] = Field(default_factory=list)  # why: every group needs one keyword
    hint: str = ""                 # points back to the lesson


class Word(BaseModel):
    """A real word to READ, built only from letters taught so far. The answer (how it sounds, in Devanagari) is
    computed by rule (text.reading_forms), so it needs no hand-written key. The picture is shown only AFTER the
    learner has read the word, so it is a memory hook, not a clue to guess from."""
    telugu: str                    # "కమలం"
    meaning: str                   # in Hindi: "कमल"
    en: str = ""                   # English, for the picture model only: "a pink lotus flower"
    picture: str = ""              # emoji until an AI picture exists
    image: str = ""                # an approved picture, relative to data/<pair>/
    misread: str                   # how Raju misreads it, in Devanagari: "कमल" (he skipped ం)
    confused: str                  # the one Telugu letter or sign he got wrong: "ం"
    check: bool = False            # the lesson's scored check: a word NOT shown in the reading round


class Unit(BaseModel):
    unit_id: str                   # e.g. "L0-01"
    level: Level
    title: str                     # plain words, shown to the learner
    tip: str = ""                  # the one pattern this unit teaches (shown before the cards)
    lesson: list[LessonLine]
    check: Optional[Item] = None   # the one question after the lesson (reading units: built from `words`)
    items: list[Item] = Field(default_factory=list)   # what Raju gets wrong
    words: list[Word] = Field(default_factory=list)   # reading units: real words to read
    key_ideas: list[list[str]] = Field(default_factory=list)   # rule units: the 'why' the learner must explain
    habit: str = ""                # rule units: the Hindi habit that causes the mistake (for Raju's prompt)
    followups: list[FollowUp] = Field(default_factory=list)
    requires: list[str] = Field(default_factory=list)   # unit_ids that must be learned first
    status: Status = "draft_unverified"
    version: int = 1
    reviewer: Optional[str] = None
    source: str = "team draft"

    @model_validator(mode="after")
    def _words_to_items(self):
        """Reading units: each word becomes a reading item (Raju misreads these); the word marked `check` becomes
        the scored check, so the check is always a word the learner has not read before."""
        from .text import reading_forms
        have = {it.item_id for it in self.items}
        for i, w in enumerate(self.words, 1):
            item = Item(item_id=f"{self.unit_id}-w{i}", prompt=w.telugu, accepted=reading_forms(w.telugu),
                        raju_wrong=w.misread, answer_script="devanagari", closed=True, kind="word")
            if w.check:
                self.check = item
            elif item.item_id not in have:
                self.items.append(item)
        if self.check is None:
            raise ValueError(f"{self.unit_id}: needs a check (or a word with check: true)")
        return self

    def word(self, telugu: str):
        return next((w for w in self.words if w.telugu == telugu), None)


class CheckResult(BaseModel):
    item_id: str
    answer: str
    verdict: Verdict
    reason: str
