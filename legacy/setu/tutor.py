"""The tutor engine: one place that ties lessons, Raju, the checker, memory and the planner together.
It returns plain dicts, so a terminal, a web page or tests can all drive it the same way.

    t = Tutor(Store("runs"))
    t.next("me")            -> a lesson, a Raju line, a follow-up, or "done for today"
    t.answer("me", "ख")     -> verdict + what comes next (next drill letter, the check, Raju's next follow-up)

After the cards comes a DRILL: every letter of the unit, one at a time, not scored. A miss shows the same
card again and you retry it straight away; a letter you missed must then be right once more, a couple of
letters later. Three misses on one letter: the answer is shown, you move on, and the letter is marked weak
(its unit fades sooner and Raju picks that letter first). Only after the drill does the scored check open.
    t.skip_days("me", 3)    -> testing/demo: move the clock forward and watch Raju forget
Only checked answers change anything; 'unsure' goes to the teacher queue and changes nothing."""
from __future__ import annotations
import random
from typing import Dict, List, Optional
from .bank import load_units, all_items
from .checker import check, check_why, NO_ERROR
from .contracts import CheckResult, Item, Unit
from .course import Course, Module, load_course, singles
from .followups import followups_for
from .leakfilter import seen_telugu
from .memory import LearnerRecord, Store, DAY
from .planner import choose
from . import raju as rj
from .text import normalize
from .writer import TemplateWriter, raju_line, raju_reaction, writer_from_env

GOT_IT = "Raju अब ये जानता है ✓"          # the system's verdict; Raju's own words come in "raju_says"
THANKS = "सही! Raju अभी सीख रहा है…"


def check_spot(item: Item, answer: str) -> CheckResult:
    """Raju's line was CORRECT. 'No mistake' (or repeating the right form) is right; changing it is a false alarm."""
    n = normalize(answer)
    r = lambda v, why: CheckResult(item_id=item.item_id, answer=answer, verdict=v, reason=why)
    if answer.strip() == NO_ERROR or n in {normalize(a) for a in item.accepted}:
        return r("correct", "it was already right")
    if n == normalize(item.raju_wrong) or item.closed:
        return r("wrong", "false alarm: it was already right")
    return r("unsure", "changed a correct line; a teacher will check")


class Tutor:
    def __init__(self, store: Store, writer=None, seed: Optional[int] = None, pair: str = "hi-te",
                 new_per_day: int = 3, p_spot: float = 0.2, max_variety: int = 3,
                 drill: bool = True, max_misses: int = 3, course=None):
        self.units: List[Unit] = load_units(pair)
        self.by_id: Dict[str, Unit] = {u.unit_id: u for u in self.units}
        self.items = all_items(self.units)
        self.store, self.rng = store, random.Random(seed)
        self.fallback = TemplateWriter(self.rng)
        self.writer = writer if writer is not None else writer_from_env(self.rng)
        self.new_per_day, self.p_spot, self.max_variety = new_per_day, p_spot, max_variety
        self.drill, self.max_misses = drill, max_misses
        # the course map: "singles" = Raju right after every lesson (used by tests of Raju's mechanics)
        self.course: Course = singles(self.units) if course == "singles" else course or load_course(self.units, pair)

    # ---------------- helpers ----------------
    def _hint(self, unit: Unit, item: Item) -> str:
        if item.kind == "sentence":                       # a rule: point at the rule, never at the answer
            return f"याद करो: {unit.title}"
        for line in unit.lesson:
            if normalize(line.telugu) == normalize(item.prompt) or normalize(line.hindi).startswith(normalize(item.accepted[0])) \
               or normalize(item.prompt) in normalize(line.hindi):
                return f"Lesson याद करो: {line.hindi} → {line.telugu}"
        return "Lesson याद करो।"

    @staticmethod
    def _card(unit: Unit, item: Item):
        """The lesson card an item is about (to show it again after a miss)."""
        accepted = {normalize(a) for a in item.accepted}
        for line in unit.lesson:
            t = normalize(line.telugu)
            if t == normalize(item.prompt) or t in accepted:
                return line
        return None

    def _short_how(self, item: Item) -> str:
        if item.kind == "sentence":
            return "Telugu में लिखो (Hindi keyboard चलेगा: नुव्वु → నువ్వు)"
        return self._how(item).split(",")[0].replace("गलत है तो सही", "").strip()

    def _drill_prompt(self, iid: str, left: int) -> dict:
        item = self.items[iid][1]
        return {"item": iid, "prompt": item.prompt, "how": self._short_how(item), "left": left, "item_kind": item.kind}

    def _check_prompt(self, unit: Unit) -> dict:
        q = f"Telugu में लिखो: “{unit.check.prompt}”" if unit.check.kind == "sentence" else f"'{unit.check.prompt}' = ?"
        return {"question": q, "how": self._short_how(unit.check), "item_kind": unit.check.kind}

    def _fus(self, rec: LearnerRecord, unit: Unit):
        return followups_for(unit, rec.fu_from.get(unit.unit_id, ""))

    def _raju_context(self, unit: Unit, item: Item, claim: str, mistake: bool) -> str:
        """What Raju 'studied': the lesson cards, so his line is about THIS lesson. On a mistake turn he only gets
        shapes (no sounds, no tricks), so the right answer is not in front of the model at all. Any Telugu other
        than the letter in question is blanked, so the model has no other letter to slip in."""
        import re
        keep = {normalize(item.prompt), normalize(claim)}

        hide = [normalize(a) for a in item.accepted] if mistake else []

        def clean(text: str) -> str:
            text = re.sub(r"[\u0C00-\u0C7F]+", lambda m: m.group(0) if normalize(m.group(0)) in keep else "…", text or "")
            for a in hide:                                # on a mistake turn the right answer is blanked everywhere
                text = re.sub(r"(?<![\u0900-\u097F\u0C00-\u0C7F])" + re.escape(a) + r"(?![\u0900-\u097F\u0C00-\u0C7F])", "…", text)
            return text
        if item.kind == "sentence":
            m = self.course.of_unit.get(unit.unit_id)
            parts = [f"SCENE: {m.scene}" if m is not None and m.scene else "",
                     f"You want to say in Telugu: “{item.prompt}” (Hindi).",
                     f"Your Hindi habit that causes the slip: {unit.habit}." if unit.habit else ""]
            if not mistake:
                parts.append(f"The lesson taught: {clean(unit.tip)}")
            return " ".join(p for p in parts if p)
        card = self._card(unit, item)
        parts = [f"LESSON: {clean(unit.title)}."]
        if unit.tip:
            parts.append(f"Tip from the teacher: {clean(unit.tip)}.")
        if mistake:
            if card is not None and card.shape:
                parts.append(f"Card of {item.prompt}: it looks like: {clean(card.shape)}.")
            other = next((l for u in self.units for l in u.lesson if normalize(l.hindi) == normalize(claim)), None)
            if other is not None and other.shape:
                parts.append(f"Card of the letter that sounds '{claim}': it looks like: {clean(other.shape)}.")
        elif card is not None:
            parts.append(f"Card of {item.prompt} = {item.accepted[0]}: looks like: {clean(card.shape)}; "
                         f"memory trick: {clean(card.mnemonic)}.")
        return " ".join(parts)

    def _seen_words(self, rec: LearnerRecord) -> set:
        """Every Telugu word the learner has met in a lesson (paper Eq. 1: V_L)."""
        ids = {u for u, m in rec.units.items() if m.introduced_at is not None}
        out = set()
        for u in self.units:
            if u.unit_id in ids:
                for l in u.lesson:
                    out |= {normalize(w) for w in l.telugu.split()}
        return out

    def _ask_followup(self, rec: LearnerRecord, unit: Unit) -> dict:
        fus = self._fus(rec, unit)
        idx = rec.fu_done.get(unit.unit_id, 0)
        fu = fus[idx]
        say, how, source = f"{fu.ask} {fu.sentence}".strip(), self._how(fu.item), "template"
        if fu.item is not None and fu.item.kind == "sentence" and "=" in fu.sentence:
            hi, te = [x.strip() for x in fu.sentence.split("=", 1)]
            say = f"{fu.ask} मुझे कहना था “{hi}”, तो मैंने लिखा: {te}"
        if fu.kind == "why":
            how = "अपने शब्दों में लिखो (Hindi या Hinglish)"
        if fu.item is not None and "=" in fu.sentence and getattr(self.writer, "name", "template") != "template":
            claim = fu.sentence.split("=", 1)[1].strip()          # Raju's follow-up, in his words, about this lesson
            mistake = not fu.sentence_is_correct
            seen = seen_telugu(self.units, [u for u, m in rec.units.items() if m.introduced_at is not None])
            line, src, rejected, calls = raju_line(self.writer, self.fallback, fu.item, claim, mistake, self.units,
                                                   rec.raju, seen, unit.unit_id,
                                                   context=self._raju_context(unit, fu.item, claim, mistake),
                                                   seen_words=self._seen_words(rec))
            rec.model_calls += calls
            if src == "model":
                say, source = line, "model"
        rec.pending = {"kind": "followup", "unit": unit.unit_id, "idx": idx, "attempt": 0, "say": say, "how": how,
                       "number": idx + 1, "of": len(fus), "source": source, "fu_kind": fu.kind}
        rec.last_unit = unit.unit_id; rec.turns += 1
        rec.note(step="followup", unit=unit.unit_id, n=idx + 1)
        return {"kind": "followup", "unit": unit.unit_id, "raju": say,
                "number": idx + 1, "of": len(fus), "how": how, "source": source}

    @staticmethod
    def _how(item: Optional[Item]) -> str:
        if item is None:
            return "अपने शब्दों में लिखो"
        if item.kind == "sentence":
            return "गलत है तो पूरा सही Telugu वाक्य लिखो (Hindi keyboard चलेगा: नुव्वु → నువ్వు), सही है तो /ok"
        if item.answer_script == "telugu":
            return "गलत है तो सही Telugu लिखो (Hindi keyboard भी चलेगा: पुस्तकं → పుస్తకం), सही है तो /ok"
        return "गलत है तो सही जवाब Hindi में लिखो, सही है तो /ok"

    # ---------------- what comes next ----------------
    # ---------------- the course: modules ----------------
    def _complete_modules(self, rec: LearnerRecord) -> List[Module]:
        """A module is finished once Raju knows every lesson in it (it stays finished if he forgets later)."""
        new = []
        for m in self.course.modules:
            if m.index not in rec.modules_done and all(rec.raju.get(u) == "taught" for u in m.units):
                rec.modules_done.append(m.index)
                rec.note(step="module_done", module=m.label)
                new.append(m)
        return new

    def _current_module(self, rec: LearnerRecord) -> Optional[Module]:
        return next((m for m in self.course.modules if m.index not in rec.modules_done), None)

    def _step_info(self, m: Module, kind: str, unit_id: Optional[str] = None) -> dict:
        st = self.course.step_of_unit[unit_id] if kind == "lesson" else m.raju_step
        return {"no": st.no, "title": st.title, "module": m.label, "chapter": f"अध्याय {m.chapter} · {m.chapter_title}"}

    def _new_today(self, rec: LearnerRecord, now: float) -> int:
        today = int(now // DAY)
        return sum(1 for m in rec.units.values() if m.introduced_at is not None and int(m.introduced_at // DAY) == today)

    # ---------------- what comes next ----------------
    def next(self, lid: str) -> dict:
        """In course order: the module's lessons one by one (cards -> drill -> check), then the module's Raju
        lesson ("Raju needs your help", only on that module's lessons), then the next module.
        A lesson Raju forgot from a finished module is revised first ("🔁")."""
        rec = self.store.load(lid)
        if rec.pending:
            return {"kind": "waiting", "message": "पहले पिछले सवाल का जवाब दो।", "pending": rec.pending}
        now = rec.now()
        for u in rj.forget(rec.raju, rec.fu_done, {u: rec.mem(u).p_recall(now) for u in rec.raju}):
            rec.note(step="raju_forgot", unit=u)
        self._complete_modules(rec)
        weights = {u: 1 + rec.mem(u).wrong for u in rec.raju}
        done_units = [u for m in self.course.modules if m.index in rec.modules_done for u in m.units]

        # 1. revision: a finished module's lesson that Raju forgot (or is re-learning)
        review = {u: rec.raju[u] for u in done_units if rec.raju.get(u) in ("forgotten", "learning", "unknown")}
        if review:
            kind, uid = choose(review, self.rng, rec.last_unit, 0.0, weights, False)
            m = self.course.of_unit[uid]
            step = {"no": "🔁", "title": "दोहराओ: Raju भूल गया", "module": m.label,
                    "chapter": f"अध्याय {m.chapter} · {m.chapter_title}"}
            return self._raju_turn(rec, kind, uid, step)

        m = self._current_module(rec)
        if m is not None:
            nxt = next((u for u in m.units if rec.mem(u).introduced_at is None), None)
            if nxt is None:                                # 2. the module's Raju lesson
                sub = {u: rec.raju.get(u, "unknown") for u in m.units}
                choice = choose(sub, self.rng, rec.last_unit, self.p_spot, weights, False)
                if choice is not None:
                    return self._raju_turn(rec, choice[0], choice[1], self._step_info(m, "raju"))
            elif self._new_today(rec, now) < self.new_per_day:   # 3. the next lesson of the module
                return self._lesson(rec, self.by_id[nxt], now, self._step_info(m, "lesson", nxt))

        # 4. nothing new today: a few spot checks on what Raju knows, then stop
        taught = {u: "taught" for u in done_units if rec.raju.get(u) == "taught"}
        day = str(int(now // DAY))
        if taught and rec.variety.get(day, 0) < self.max_variety:
            rec.variety[day] = rec.variety.get(day, 0) + 1
            uid = choose(taught, self.rng, rec.last_unit, 0.0, weights, False)[1]
            mm = self.course.of_unit[uid]
            step = {"no": "⭐", "title": "Raju की जाँच", "module": mm.label, "chapter": f"अध्याय {mm.chapter} · {mm.chapter_title}"}
            return self._raju_turn(rec, "spot", uid, step)
        self.store.save(rec)
        msg = "🎉 पूरा course हो गया!" if m is None else "आज के लिए बस! कल अगला lesson खुलेगा।"
        return {"kind": "done", "message": msg + " जब आप भूलने लगेंगे, Raju भी भूलेगा और आपकी मदद माँगेगा।"}

    def _lesson(self, rec: LearnerRecord, u: Unit, now: float, step: dict) -> dict:
        rec.mem(u.unit_id).introduced_at = now
        queue = [it.item_id for it in u.items] if self.drill else []
        self.rng.shuffle(queue)
        out = {"kind": "lesson", "unit": u.unit_id, "level": u.level, "title": u.title, "tip": u.tip,
               "lesson": [l.model_dump() for l in u.lesson], "step": step}
        if queue:
            rec.pending = {"kind": "drill", "unit": u.unit_id, "queue": queue, "need": {}, "misses": {}, "attempt": 0,
                           "step": step}
            out["drill"] = self._drill_prompt(queue[0], len(queue))
        else:
            rec.pending = {"kind": "check", "unit": u.unit_id, "item": u.check.item_id, "attempt": 0, "step": step}
            out["check"] = self._check_prompt(u)
        rec.note(step="lesson", unit=u.unit_id); self.store.save(rec)
        return out

    def _raju_turn(self, rec: LearnerRecord, kind: str, uid: str, step: dict) -> dict:
        unit = self.by_id[uid]
        if kind == "followup":
            out = self._ask_followup(rec, unit)
            rec.pending["step"] = step; out["step"] = step
            self.store.save(rec); return out
        mistake = kind == "mistake"
        weak = [it for it in unit.items if it.item_id in rec.weak]
        item = self.rng.choice(weak if (mistake and weak) else unit.items)   # weak letters first
        claim = item.raju_wrong if mistake else item.accepted[0]
        seen = seen_telugu(self.units, [u for u, m in rec.units.items() if m.introduced_at is not None])
        line, source, rejected, calls = raju_line(self.writer, self.fallback, item, claim, mistake,
                                                  self.units, rec.raju, seen, unit.unit_id,
                                                  context=self._raju_context(unit, item, claim, mistake),
                                                  seen_words=self._seen_words(rec))
        rec.model_calls += calls; rec.turns += 1; rec.last_unit = unit.unit_id
        rec.pending = {"kind": "raju", "unit": unit.unit_id, "item": item.item_id, "mistake": mistake, "attempt": 0,
                       "say": line, "how": self._how(item), "source": source, "step": step}
        rec.note(step="raju", unit=unit.unit_id, mistake=mistake, source=source,
                 rejected=[r["reasons"] for r in rejected], calls=calls)
        self.store.save(rec)
        return {"kind": "raju", "unit": unit.unit_id, "raju": line, "how": self._how(item),
                "source": source, "rejected_drafts": len(rejected), "step": step}

    # ---------------- answers ----------------
    def answer(self, lid: str, text: str) -> dict:
        rec = self.store.load(lid)
        p = rec.pending
        if not p:
            return {"error": "अभी कोई सवाल नहीं है। अगला सवाल लो।"}
        unit = self.by_id[p["unit"]]
        now = rec.now()
        p["attempt"] += 1
        out = {"drill": self._answer_drill, "check": self._answer_check, "raju": self._answer_raju,
               "followup": self._answer_followup}[p["kind"]](rec, p, unit, text, now)
        if out.get("followup") and rec.pending is not None and "step" in p:
            rec.pending["step"] = p["step"]; out["followup"]["step"] = p["step"]
        for m in self._complete_modules(rec):
            nxt = self._current_module(rec)
            out["module_done"] = {"module": m.label, "chapter": f"अध्याय {m.chapter} · {m.chapter_title}",
                                  "next": nxt.label if nxt else None}
        event = out.pop("_event", None)
        if event is not None:                              # Raju reacts to the checker's verdict, in his own words
            seen = seen_telugu(self.units, [u for u, m in rec.units.items() if m.introduced_at is not None])
            ctx = self._raju_context(unit, event[1], event[1].accepted[0], False) if event[1] is not None else ""
            line, source, rejected, calls = raju_reaction(self.writer, self.fallback, event[0], event[1], self.units,
                                                          seen, context=ctx)
            rec.model_calls += calls
            rec.note(step="reaction", unit=unit.unit_id, event=event[0], source=source,
                     rejected=[r["reasons"] for r in rejected], calls=calls)
            out["raju_says"], out["raju_source"] = line, source
        self.store.save(rec)
        return out

    def _answer_drill(self, rec, p, unit, text, now) -> dict:
        """Not scored. Stay on a letter until it is right; a missed letter comes back once more later."""
        q, need, misses = p["queue"], p["need"], p["misses"]
        iid = q[0]
        item = self.items[iid][1]
        res = check(item, text)
        out = {"verdict": res.verdict, "answer": item.accepted[0]}
        if res.verdict == "correct":
            q.pop(0)
            left = need.pop(iid, 1) - 1
            if left > 0:                                   # it was missed: ask it once more, two letters later
                need[iid] = left
                at = min(2, len(q))
                q.insert(at, iid)
                out["message"] = "सही! ये थोड़ी देर में फिर आएगा।" if at else "सही! एक बार और:"
            else:
                out["message"] = "सही!"
        elif res.verdict == "unsure":                      # open item, answer not in our list: show ours, move on
            q.pop(0); need.pop(iid, None)
            out["message"] = f"हम्म, ये हमारी list में नहीं है। हमारा जवाब: {item.accepted[0]}"
        else:
            misses[iid] = misses.get(iid, 0) + 1
            if misses[iid] >= self.max_misses:             # don't get stuck: show it, mark weak, move on
                q.pop(0); need.pop(iid, None)
                if iid not in rec.weak:
                    rec.weak.append(iid)
                m = rec.mem(unit.unit_id)
                m.half_life = max(0.5, m.half_life / 2)    # this unit fades sooner -> Raju asks it sooner
                out["message"] = f"सही जवाब: {item.accepted[0]}। कोई बात नहीं — Raju ये जल्दी फिर पूछेगा।"
                out["weak"] = True
            else:                                          # same card again, try again right now
                need[iid] = 2                              # now: right once here, and once more later
                card = self._card(unit, item)
                if card is not None:
                    out["card"] = card.model_dump()
                out["message"] = "कार्ड फिर से देखो और दोबारा लिखो।"
        rec.note(step="drill", unit=unit.unit_id, item=iid, verdict=res.verdict)
        if q:
            out["next"] = self._drill_prompt(q[0], len(q))
        else:
            rec.pending = {"kind": "check", "unit": unit.unit_id, "item": unit.check.item_id, "attempt": 0}
            out["check"] = self._check_prompt(unit)
        return out

    def _answer_check(self, rec, p, unit, text, now) -> dict:
        item = self.items[p["item"]][1]
        res = check(item, text)
        rec.mem(unit.unit_id).update(res.verdict, now)
        if res.verdict == "correct":
            rec.mem(unit.unit_id).ready = True
            rj.add_unit(rec.raju, unit.unit_id)
            rec.pending = None
            m = self.course.of_unit[unit.unit_id]
            later = [u for u in m.units if not rec.mem(u).ready]
            step = self.course.step_of_unit[unit.unit_id].no
            msg = (f"सही! ✅ {step} पूरा। अब Raju को आपकी मदद चाहिए ({m.raju_step.no})।" if not later else
                   f"सही! ✅ {step} पूरा। Raju को ये {m.raju_step.no} में सिखाओगे।")
            return {"verdict": "correct", "message": msg}
        if res.verdict == "unsure":
            self.store.queue_for_teacher({"learner": rec.learner_id, "item": item.item_id, "answer": text, "kind": "check"})
        if p["attempt"] >= 2:
            p["attempt"] = 0                      # learn first: the check stays open until answered correctly once
            return {"verdict": res.verdict, "message": f"{res.reason}. सही जवाब: {item.accepted[0]} — अब इसे लिखकर देखो।"}
        return {"verdict": res.verdict, "message": f"{res.reason}. {self._hint(unit, item)}"}

    def _answer_raju(self, rec, p, unit, text, now) -> dict:
        item = self.items[p["item"]][1]
        if p["mistake"]:
            res = check(item, text) if text.strip() != NO_ERROR else \
                CheckResult(item_id=item.item_id, answer=text, verdict="wrong", reason="Raju की बात में गलती थी")
        else:
            res = check_spot(item, text)
        rec.mem(unit.unit_id).update(res.verdict, now, recognition=not p["mistake"])
        rec.note(step="checked", unit=unit.unit_id, verdict=res.verdict, mistake=p["mistake"])
        if res.verdict == "unsure":
            self.store.queue_for_teacher({"learner": rec.learner_id, "item": item.item_id, "answer": text, "kind": "raju"})
            rec.pending = None
            return {"verdict": "unsure", "message": "हम्म… मैं सोचता हूँ। (टीचर देखेंगे, अभी कुछ नहीं बदला)"}
        if res.verdict == "correct":
            rec.pending = None
            if not p["mistake"]:
                return {"verdict": "correct", "message": "हाँ, कोई गलती नहीं थी।", "_event": ("spot_ok", item)}
            rec.fu_from[unit.unit_id] = item.item_id
            if item.item_id in rec.weak:                   # taught Raju the weak letter: no longer weak
                rec.weak.remove(item.item_id)
            state = rj.fixed(rec.raju, rec.fu_done, unit.unit_id, len(self._fus(rec, unit)))
            if state == "learning":
                return {"verdict": "correct", "message": THANKS, "raju_state": state,
                        "followup": self._ask_followup(rec, unit), "_event": ("fixed", item)}
            return {"verdict": "correct", "message": GOT_IT, "raju_state": state, "_event": ("knows", item)}
        if p["attempt"] >= 2:
            rec.pending = None
            right = "कोई गलती नहीं थी" if not p["mistake"] else item.accepted[0]
            return {"verdict": "wrong", "message": f"{res.reason}. सही जवाब: {right}", "raju_state": rec.raju.get(unit.unit_id)}
        return {"verdict": "wrong", "message": f"{res.reason}. {self._hint(unit, item)}", "_event": ("doubt", item)}

    def _answer_followup(self, rec, p, unit, text, now) -> dict:
        fus = self._fus(rec, unit)
        fu = fus[p["idx"]]
        item = fu.item
        if fu.kind == "why":                       # self-explanation, scored on the rule's key ideas (no model)
            res = check_why(fu.key_ideas, "" if text.strip() == NO_ERROR else text)
            rec.note(step="why_checked", unit=unit.unit_id, verdict=res.verdict, reason=res.reason)
            if res.verdict == "correct":
                rec.mem(unit.unit_id).update("correct", now, recognition=True)
                rec.pending = None
                if rj.followup_passed(rec.raju, rec.fu_done, unit.unit_id, len(fus)):
                    return {"verdict": "correct", "message": GOT_IT, "raju_state": "taught", "_event": ("knows", None)}
                return {"verdict": "correct", "message": f"सही समझाया! ({res.reason})", "raju_state": "learning",
                        "followup": self._ask_followup(rec, unit), "_event": ("fixed", None)}
            if res.verdict == "unsure":
                p["attempt"] -= 1
                return {"verdict": "unsure", "message": "कुछ तो लिखो — Hindi या Hinglish में चलेगा।", "raju_state": "learning"}
            if res.reason == "partial" and p["attempt"] >= 2:   # half the idea twice: accept, show the full one
                rec.mem(unit.unit_id).update("correct", now, recognition=True)
                rec.pending = None
                msg = f"ठीक है, काफ़ी हद तक सही। पूरी बात: {unit.tip}"
                if rj.followup_passed(rec.raju, rec.fu_done, unit.unit_id, len(fus)):
                    return {"verdict": "correct", "message": msg, "raju_state": "taught", "_event": ("knows", None)}
                return {"verdict": "correct", "message": msg, "raju_state": "learning",
                        "followup": self._ask_followup(rec, unit), "_event": ("fixed", None)}
            if p["attempt"] >= 2:                  # second miss: the explanation is shown; Raju asks again later
                rec.pending = None
                return {"verdict": "wrong", "message": f"समझो: {unit.tip}", "raju_state": "learning"}
            if res.reason == "partial":
                return {"verdict": "wrong", "message": "आधा सही! थोड़ा और समझाओ: Hindi में क्या होता है, और Telugu में क्या?",
                        "raju_state": "learning", "_event": ("doubt", None)}
            return {"verdict": "wrong", "message": f"मुझे अभी भी समझ नहीं आया… सोचो: {unit.title}",
                    "raju_state": "learning", "_event": ("doubt", None)}
        res = check_spot(item, text) if fu.sentence_is_correct else check(item, text)
        if fu.sentence_is_correct is False and text.strip() == NO_ERROR:
            res = CheckResult(item_id=item.item_id, answer=text, verdict="wrong", reason="इसमें गलती थी")
        rec.mem(unit.unit_id).update(res.verdict, now, recognition=fu.sentence_is_correct)
        rec.note(step="followup_checked", unit=unit.unit_id, n=p["idx"] + 1, verdict=res.verdict)
        if res.verdict == "correct":
            rec.pending = None
            if rj.followup_passed(rec.raju, rec.fu_done, unit.unit_id, len(fus)):
                return {"verdict": "correct", "message": GOT_IT, "raju_state": "taught", "_event": ("knows", item)}
            return {"verdict": "correct", "message": "सही!", "raju_state": "learning",
                    "followup": self._ask_followup(rec, unit),
                    "_event": ("spot_ok" if fu.sentence_is_correct else "fixed", item)}
        if res.verdict == "unsure":
            self.store.queue_for_teacher({"learner": rec.learner_id, "item": item.item_id, "answer": text, "kind": "followup"})
            rec.pending = None
            return {"verdict": "unsure", "message": "हम्म… मैं सोचता हूँ। (टीचर देखेंगे)", "raju_state": "learning"}
        if p["attempt"] >= 2:                      # second miss: show the answer; this follow-up comes back later
            rec.pending = None
            right = "कोई गलती नहीं थी" if fu.sentence_is_correct else item.accepted[0]
            return {"verdict": "wrong", "message": f"सही जवाब: {right}", "raju_state": "learning"}
        return {"verdict": "wrong", "message": self._hint(unit, item), "raju_state": "learning", "_event": ("doubt", item)}

    # ---------------- what is on screen right now (for the web app: it redraws from saved state) ----------------
    def screen(self, lid: str) -> dict:
        """The open question, rebuilt from the saved record, so a page refresh or a restart loses nothing."""
        rec = self.store.load(lid)
        p = rec.pending
        if not p:
            return {"kind": "idle"}
        unit = self.by_id[p["unit"]]
        base = {"kind": p["kind"], "unit": unit.unit_id, "level": unit.level, "title": unit.title, "step": p.get("step")}
        if p["kind"] == "drill":
            return {**base, **self._drill_prompt(p["queue"][0], len(p["queue"])), "tip": unit.tip,
                    "lesson": [l.model_dump() for l in unit.lesson]}
        if p["kind"] == "check":
            return {**base, **self._check_prompt(unit)}
        return {**base, "raju": p.get("say", ""), "how": p.get("how", ""), "source": p.get("source", ""),
                "number": p.get("number"), "of": p.get("of"), "fu_kind": p.get("fu_kind", "")}

    def raju_notebook(self, lid: str) -> list:
        """One row per unit the learner has met: their memory and what Raju knows."""
        rec = self.store.load(lid); now = rec.now()
        rows = []
        for u in self.units:
            m = rec.units.get(u.unit_id)
            if m is None or m.introduced_at is None:
                continue
            rows.append({"unit": u.unit_id, "title": u.title, "level": u.level, "ready": m.ready,
                         "recall": round(m.p_recall(now), 2), "raju": rec.raju.get(u.unit_id, "-"),
                         "right": m.correct, "wrong": m.wrong,
                         "weak": " ".join(self.items[i][1].prompt for i in rec.weak if self.items[i][0].unit_id == u.unit_id)})
        return rows

    def course_map(self, lid: str) -> dict:
        """The side panel: chapters -> modules -> numbered steps, each done / now / open / locked.
        A module's Raju step shows how much Raju has learned; a finished module shows when its revision is due
        (Raju forgets a lesson when YOUR memory of it falls to 50%, i.e. after its half-life without practice)."""
        rec = self.store.load(lid)
        now = rec.now()
        cur = self._current_module(rec)
        pend = rec.pending or {}
        chapters = []
        for ch, mods in self.course.chapters().items():
            cmods = []
            for m in mods:
                done = m.index in rec.modules_done
                locked = not done and (cur is None or m.index > cur.index)
                lessons_ready = all(rec.mem(u).ready for u in m.units)
                steps = []
                for st in m.steps:
                    if st.kind == "lesson":
                        mem = rec.units.get(st.unit)
                        ready = bool(mem and mem.ready)
                        state = "done" if ready else "now" if pend.get("unit") == st.unit else "locked" if locked else "open"
                        steps.append({"no": st.no, "kind": "lesson", "title": st.title, "state": state})
                    else:
                        score = 0.0
                        for u in m.units:
                            r = rec.raju.get(u)
                            n_fu = max(len(self._fus(rec, self.by_id[u])), 1)
                            score += 1.0 if r == "taught" else 0.5 + 0.5 * min(rec.fu_done.get(u, 0), n_fu) / n_fu if r == "learning" else 0.0
                        knows = sum(rec.raju.get(u) == "taught" for u in m.units)
                        state = "done" if done else "now" if (lessons_ready and not locked) else "locked"
                        steps.append({"no": st.no, "kind": "raju", "title": st.title, "state": state,
                                      "progress": round(score / len(m.units), 2),
                                      "detail": f"Raju जानता है {knows}/{len(m.units)}"})
                review = None
                if done:
                    forgot = [u for u in m.units if rec.raju.get(u) in ("forgotten", "learning", "unknown")]
                    if forgot:
                        review = 0.0
                    else:
                        dues = [(rec.units[u].last or now) / DAY + rec.units[u].half_life - now / DAY
                                for u in m.units if u in rec.units]
                        review = max(0.0, min(dues)) if dues else None
                cmods.append({"label": m.label, "number": m.number, "state": "done" if done else "locked" if locked else "now",
                              "steps": steps, "review_days": None if review is None else round(review, 2)})
            first = mods[0]
            state = "done" if all(x["state"] == "done" for x in cmods) else \
                    "locked" if all(x["state"] == "locked" for x in cmods) else "now"
            chapters.append({"no": ch, "title": first.chapter_title, "icon": first.chapter_icon,
                             "state": state, "modules": cmods})
        lessons = [st for m in self.course.modules for st in m.steps if st.kind == "lesson"]
        learned = sum(1 for st in lessons if rec.units.get(st.unit) and rec.units[st.unit].ready)
        return {"chapters": chapters, "learned": learned, "total": len(lessons),
                "new_left_today": max(0, self.new_per_day - self._new_today(rec, now)), "weak": len(rec.weak)}

    def jump_to(self, lid: str, module_index: int) -> None:
        """Start at a later module: everything before it counts as learned and taught to Raju (like passing a
        placement test; paper §5: 'a learner who already knows a rule at the pre-test can teach it at once')."""
        rec = self.store.load(lid)
        now = rec.now()
        for m in self.course.modules[:module_index]:
            for u in m.units:
                mem = rec.mem(u)
                if mem.introduced_at is None:
                    mem.introduced_at = now - DAY
                mem.ready, mem.last, mem.correct = True, now, max(mem.correct, 1)
                mem.half_life = max(mem.half_life, 7.0)
                rec.raju[u] = "taught"
                rec.fu_done[u] = len(self._fus(rec, self.by_id[u]))
            if m.index not in rec.modules_done:
                rec.modules_done.append(m.index)
        rec.pending = None
        rec.note(step="jump", module=self.course.modules[module_index].label if module_index < len(self.course.modules) else "end")
        self.store.save(rec)

    # ---------------- testing / demo ----------------
    def skip_days(self, lid: str, days: float) -> None:
        rec = self.store.load(lid); rec.day_offset += days; rec.note(step="skip", days=days); self.store.save(rec)

    def status(self, lid: str) -> dict:
        rec = self.store.load(lid); now = rec.now()
        return {"day": round(rec.day_offset, 1), "turns": rec.turns, "model_calls": rec.model_calls, "weak": list(rec.weak),
                "writer": getattr(self.writer, "name", "template"),
                "units": {u: {"ready": m.ready, "recall": round(m.p_recall(now), 2), "raju": rec.raju.get(u, "-"),
                              "right": m.correct, "wrong": m.wrong}
                          for u, m in rec.units.items() if m.introduced_at is not None}}
