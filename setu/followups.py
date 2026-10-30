"""Raju's follow-up questions after the learner fixed him.

A unit may define its own follow-ups (why? / judge / boundary). Letters and words don't need hand-written
ones: their follow-ups are built from the unit's other items, which the lesson already showed:
  1. "तो X = Y, ठीक?"  with Y correct      -> the learner must say 'no mistake'
  2. "और Z = W?"       with Raju's mistake -> the learner must fix it
Every follow-up has a fixed answer the checker can verify."""
from __future__ import annotations
from typing import List
from .contracts import FollowUp, Item, Unit


WHY_ASK = "अच्छा, मान गया! पर ऐसा क्यों? Hindi और Telugu में यहाँ क्या अलग है — अपने शब्दों में समझाओ।"


def followups_for(unit: Unit, fixed_item_id: str = "") -> List[FollowUp]:
    if unit.followups:
        return list(unit.followups)
    if unit.level == 3 and unit.key_ideas:
        # Grammar rules (paper §5): Raju asks WHY (self-explanation, scored on the rule's key ideas), then hands
        # over the rule's other sentence: with the planted mistake, or correct when the rule has one sentence
        # (a no-error turn: the learner must notice there is nothing to fix).
        out = [FollowUp(kind="why", ask=WHY_ASK, key_ideas=unit.key_ideas, hint=unit.title)]
        others = [it for it in unit.items if it.item_id != fixed_item_id]
        if others:
            b = others[0]
            out.append(FollowUp(kind="judge", ask="तो फिर ये भी देखो:", sentence=f"{b.prompt} = {b.raju_wrong}", item=b))
        else:
            a = unit.items[0]
            out.append(FollowUp(kind="judge", ask="तो अब ये सही लिखा ना?", sentence=f"{a.prompt} = {a.accepted[0]}",
                                item=a, sentence_is_correct=True))
        return out
    others = [it for it in unit.items if it.item_id != fixed_item_id] or list(unit.items)
    out: List[FollowUp] = []
    if others:
        a = others[0]
        out.append(FollowUp(kind="judge", ask="अच्छा! तो फिर ये ठीक है?", sentence=f"{a.prompt} = {a.accepted[0]}",
                            item=a, sentence_is_correct=True))
    if len(others) > 1:
        b = others[1]
        out.append(FollowUp(kind="judge", ask="और ये?", sentence=f"{b.prompt} = {b.raju_wrong}", item=b))
    return out


def as_item(fu: FollowUp) -> Item:
    assert fu.item is not None
    return fu.item
