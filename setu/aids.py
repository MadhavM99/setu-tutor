"""AI teaching aids for every lesson card: a fresh memory trick (Gemma) and a picture (Google's image model).

The model teaches, but inside guards:
  trick    Gemma gets only the VERIFIED facts of the card (the letter, its sound, the shape description that was
           checked against the real font, the example word) and writes a new memory story. Rules then check it
           (leakfilter.check_trick): Hindi only, short, names this letter and its sound, no other Telugu letter,
           never pairs the letter with a different sound. A rejected draft goes back with the reasons (3 tries).
  picture  The image model draws ONLY the object of the example word (lotus for కమలం) and is told to write no
           text. Image models draw letters wrong, so the real letter is never drawn by a model: the app puts the
           letter from the real font on top of the picture. Gemma then looks at the picture and must answer
           TEXT=NO (no stray writing) and OBJECT=YES (the object is really there), or the picture is redrawn
           once and otherwise not shown.
Both are made once per card and kept in <store>/ai/ for every learner (fast, and cheap on the free tier).
Learners can ask for another trick or like one; a teacher approves or rejects them on the Teacher page.
"""
from __future__ import annotations
import hashlib
import json
import re
import threading
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional
from .contracts import LessonLine, Unit
from .leakfilter import check_trick
from .llm import clean_line, describe_error

TRICK_SYSTEM = ("You are a warm, creative teacher helping a Hindi speaker remember a Telugu letter for life. "
                "Write in simple Hindi (Devanagari) only. No English letters. Use no Telugu letters except the "
                "one letter you are given. Reply with the trick only, as one line.")
PICTURE_PROMPT = ("A bright, simple, friendly flat illustration for a children's alphabet flashcard: {obj} {emoji}. "
                  "One clear object in the centre, plain white background, soft colours. "
                  "IMPORTANT: absolutely no text, letters, numbers, words, signs or symbols anywhere in the image.")
PICTURE_CHECK = ("Look at this picture. Answer with exactly two words. First: TEXT=YES if there is ANY writing, "
                 "letter, number or symbol in it, otherwise TEXT=NO. Second: OBJECT=YES if it clearly shows {obj}, "
                 "otherwise OBJECT=NO.")


def picture_object(line: LessonLine) -> str:
    """The thing to draw: the Hindi meaning of the example word ("కమలం = कमल" -> "कमल")."""
    if "=" not in line.example:
        return ""
    return line.example.split("=", 1)[1].split("(")[0].strip()


SVG_SYSTEM = ("You draw simple, friendly, colourful flat illustrations as SVG code for a children's flashcard. "
              "Reply with ONE <svg> element only (viewBox=\"0 0 256 256\"), using only shapes: circle, ellipse, rect, "
              "path, polygon, polyline, line, g, and gradients. NO <text>, no letters, numbers or writing of any kind, "
              "no images, no scripts. Keep it under 6000 characters.")
SVG_TAGS = {"svg", "g", "circle", "ellipse", "rect", "path", "polygon", "polyline", "line", "defs",
            "linearGradient", "radialGradient", "stop"}


def clean_svg(text: str) -> Optional[str]:
    """Accept a model's SVG only if it is pure shapes: no text, no scripts, no links, no outside images.
    So whatever the model draws, it can never show a (wrong) letter."""
    m = re.search(r"<svg[\s\S]*?</svg>", text or "")
    if not m or len(m.group(0)) > 30000:
        return None
    svg = m.group(0)
    try:
        root = ET.fromstring(svg)
    except ET.ParseError:
        return None
    for el in root.iter():
        if el.tag.split("}")[-1] not in SVG_TAGS or (el.text or "").strip():
            return None
        for k, v in el.attrib.items():
            k = k.split("}")[-1].lower()
            if k.startswith("on") or "href" in k or ("url(" in v and "url(#" not in v):
                return None
    if "xmlns" not in svg[:200]:
        svg = svg.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)
    return svg


_LOCK = threading.Lock()


class Aids:
    def __init__(self, root: str, llm=None, images=None):
        self.dir = Path(root) / "ai"
        (self.dir / "images").mkdir(parents=True, exist_ok=True)
        self.path = self.dir / "aids.json"
        self.llm, self.images = llm, images

    # ---------- storage ----------
    def all(self) -> dict:
        if self.path.exists():
            return json.loads(self.path.read_text(encoding="utf-8"))
        return {}

    def _put(self, key: str, kind: str, entry: dict) -> None:
        with _LOCK:                                        # pictures are also made in a background thread
            d = self.all()
            d.setdefault(key, {})[kind] = entry
            self.path.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")

    @staticmethod
    def key(unit: Unit, line: LessonLine) -> str:
        return f"{unit.unit_id}:{line.telugu}"

    def get(self, unit: Unit, line: LessonLine) -> dict:
        """What is already made for this card (shown instantly, nothing is generated)."""
        out = dict(self.all().get(self.key(unit, line), {}))
        pic = out.get("picture")
        if pic and pic.get("file"):
            pic = dict(pic, path=str(self.dir / pic["file"]))
            out["picture"] = pic
        return {k: v for k, v in out.items() if v and v.get("status") != "rejected"}

    def mark(self, key: str, kind: str, status: str) -> None:
        """status: liked (learner) / approved / rejected (teacher)."""
        d = self.all()
        if kind in d.get(key, {}):
            d[key][kind]["status"] = status
            self.path.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---------- making them ----------
    def trick(self, unit: Unit, line: LessonLine, fresh: bool = False) -> Optional[dict]:
        k = self.key(unit, line)
        old = self.all().get(k, {}).get("trick")
        if old and not fresh and old.get("status") != "rejected":
            return old
        if self.llm is None:
            return None
        before = [old["text"]] + old.get("before", []) if old and old.get("text") else []
        facts = (f"Telugu letter: {line.telugu}. It sounds like Hindi '{line.hindi}'. "
                 f"What it looks like (checked, use ONLY these features, do not invent others): {line.shape or '-'}. "
                 f"Example word: {line.example or '-'}. An example of a good trick: {line.mnemonic or '-'}. ")
        ask = (facts + f"Write a NEW, vivid, funny memory trick (at most 2 short sentences, under 150 characters) "
               f"that links this shape to the sound. It MUST contain '{line.telugu}' and '{line.hindi}'.")
        if before:
            ask += " It must be different from these: " + " | ".join(before[:3])
        rejected, feedback = [], ""
        for _ in range(3):
            try:
                text = clean_line(self.llm.chat(TRICK_SYSTEM, ask + feedback, max_tokens=120, temperature=1.0))
            except Exception as e:
                rejected.append({"draft": "", "reasons": [f"MODEL_ERROR: {describe_error(e)}"]})
                break
            dec = check_trick(text, line)
            if dec.ok:
                entry = {"text": text, "model": getattr(self.llm, "name", ""), "status": "ai",
                         "before": before[:5], "rejected": rejected}
                self._put(k, "trick", entry)
                return entry
            rejected.append({"draft": text, "reasons": dec.reasons})
            feedback = f" Your last trick was rejected ({', '.join(dec.reasons)}); fix that."
        return {"text": "", "status": "failed", "rejected": rejected}

    def picture(self, unit: Unit, line: LessonLine, fresh: bool = False) -> Optional[dict]:
        k = self.key(unit, line)
        old = self.all().get(k, {}).get("picture")
        if old and not fresh and old.get("status") != "rejected" and (self.dir / old["file"]).exists():
            return dict(old, path=str(self.dir / old["file"]))
        obj = picture_object(line)
        if not obj or (self.images is None and self.llm is None):
            return None
        prompt = PICTURE_PROMPT.format(obj=obj, emoji=line.picture)
        tries = []
        for _ in range(2 if self.images is not None else 0):   # one redraw if the check fails
            try:
                data, mime = self.images.draw(prompt)
            except Exception as e:
                tries.append(f"IMAGE_ERROR: {describe_error(e)}")
                break
            verdict = self._look(data, mime, obj)
            tries.append(verdict)
            if "TEXT=YES" in verdict or "OBJECT=NO" in verdict:
                continue                                       # stray writing or wrong object: redraw
            name = hashlib.md5(k.encode()).hexdigest()[:12] + (".jpg" if "jpeg" in mime else ".png")
            (self.dir / "images" / name).write_bytes(data)
            entry = {"file": f"images/{name}", "object": obj, "model": getattr(self.images, "model", ""),
                     "check": verdict, "status": "ai", "prompt": prompt}
            self._put(k, "picture", entry)
            return dict(entry, path=str(self.dir / entry["file"]))
        drawn = self._draw_svg(k, obj, line.picture)               # no image model (or it failed): Gemma draws
        if drawn is not None:
            return drawn
        tries.append("SVG: Gemma's drawing was not usable")
        return {"status": "failed", "tries": tries, "attempts": getattr(self.images, "attempts", [])}

    def _draw_svg(self, k: str, obj: str, emoji: str) -> Optional[dict]:
        """Your own language model draws the picture as SVG shapes. clean_svg() throws out anything with text in
        it, so the real letter (written on top by the app, from the font) is the only writing on the card."""
        if self.llm is None:
            return None
        ask = f"Draw: {obj} {emoji}. One clear object, centred, bright colours, white background."
        for _ in range(2):
            try:
                raw = self.llm.chat(SVG_SYSTEM, ask, max_tokens=2500, temperature=0.4, timeout=60)
            except TypeError:
                raw = self.llm.chat(SVG_SYSTEM, ask, max_tokens=2500, temperature=0.4)
            except Exception:
                return None
            svg = clean_svg(raw)
            if svg:
                name = hashlib.md5(k.encode()).hexdigest()[:12] + ".svg"
                (self.dir / "images" / name).write_text(svg, encoding="utf-8")
                entry = {"file": f"images/{name}", "object": obj, "model": getattr(self.llm, "name", "") + " (SVG)",
                         "check": "SVG shapes only: no text possible", "status": "ai"}
                self._put(k, "picture", entry)
                return dict(entry, path=str(self.dir / entry["file"]))
            ask += " Your last answer was not a valid shapes-only SVG; reply with the <svg> element only."
        return None

    def prepare(self, unit: Unit) -> None:
        """Make the trick and picture of every card of a unit (run in a background thread)."""
        for line in unit.lesson:
            try:
                if self.llm is not None and "trick" not in self.get(unit, line):
                    self.trick(unit, line)
                if "picture" not in self.get(unit, line) and picture_object(line):
                    self.picture(unit, line)
            except Exception:
                pass

    def _look(self, data: bytes, mime: str, obj: str) -> str:
        """Gemma checks the picture. If it cannot look, the picture is marked 'unchecked' for the teacher."""
        if self.llm is None or not hasattr(self.llm, "see"):
            return "UNCHECKED: no model to look at it"
        try:
            ans = self.llm.see(data, mime, PICTURE_CHECK.format(obj=obj)).upper().replace(" ", "")
        except Exception as e:
            return f"UNCHECKED: {describe_error(e)}"
        text = "TEXT=YES" if "TEXT=YES" in ans else "TEXT=NO" if "TEXT=NO" in ans else "TEXT=?"
        seen = "OBJECT=NO" if "OBJECT=NO" in ans else "OBJECT=YES" if "OBJECT=YES" in ans else "OBJECT=?"
        if text == "TEXT=?":
            return f"UNCHECKED: unclear answer '{ans[:40]}'"
        return f"{text} {seen}"
