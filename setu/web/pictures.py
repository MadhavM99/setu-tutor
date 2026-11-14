"""Word pictures: small inline SVG drawings that sit beside a Telugu word to help a beginner remember it.

Everything is drawn here, so nothing is downloaded and nothing is loaded from another host (E-15). A picture is a
memory hook, never an answer key: the practice pages show it on the intro card and on the feedback card, and in the
match game's picture mode, not on a recognition question about the same word.

Numbers are drawn as dots so the learner sees the quantity. Concrete words get an object. Abstract words (the
Sanskrit-origin ones) get a symbol, and a word with no good picture gets none: `picture` returns None and the page
simply leaves the picture out. The label read by a screen reader comes from the Hindi catalog (`pic.*` keys).
"""
from markupsafe import Markup, escape

# Telugu word -> (catalog key for the screen-reader label, drawing name)
PICTURES = {
    "ఒకటి": ("pic.count", "dots1"), "రెండు": ("pic.count", "dots2"), "మూడు": ("pic.count", "dots3"),
    "నాలుగు": ("pic.count", "dots4"), "ఐదు": ("pic.count", "dots5"), "ఆరు": ("pic.count", "dots6"),
    "ఏడు": ("pic.count", "dots7"), "ఎనిమిది": ("pic.count", "dots8"), "తొమ్మిది": ("pic.count", "dots9"),
    "పది": ("pic.count", "dots10"),
    "నమస్కారం": ("pic.hands", "hands"), "ధన్యవాదాలు": ("pic.heart", "heart"), "అవును": ("pic.tick", "tick"),
    "ఏమిటి": ("pic.question", "question"), "ఎక్కడ": ("pic.pin", "pin"), "ఎప్పుడు": ("pic.clock", "clock"),
    "ఎవరు": ("pic.person", "person"), "ఎంత": ("pic.coins", "coins"), "పుస్తకం": ("pic.book", "book"),
    "సమయం": ("pic.hourglass", "hourglass"), "దేశం": ("pic.globe", "globe"), "పాఠం": ("pic.board", "board"),
    "అర్థం": ("pic.bulb", "bulb"), "భాగం": ("pic.pie", "pie"), "ఉపన్యాసం": ("pic.mic", "mic"),
    "చరిత్ర": ("pic.scroll", "scroll"), "ఆలస్యం": ("pic.late", "late"),
}

_DOTS = {
    1: [(60, 60)], 2: [(42, 60), (78, 60)], 3: [(60, 36), (38, 78), (82, 78)],
    4: [(40, 40), (80, 40), (40, 80), (80, 80)], 5: [(38, 38), (82, 38), (60, 60), (38, 82), (82, 82)],
    6: [(40, 32), (80, 32), (40, 60), (80, 60), (40, 88), (80, 88)],
    7: [(40, 28), (80, 28), (40, 54), (80, 54), (60, 80), (40, 98), (80, 98)],
    8: [(36, 30), (60, 30), (84, 30), (36, 60), (84, 60), (36, 90), (60, 90), (84, 90)],
    9: [(36, 32), (60, 32), (84, 32), (36, 60), (60, 60), (84, 60), (36, 88), (60, 88), (84, 88)],
    10: [(36, 26), (60, 26), (84, 26), (36, 50), (84, 50), (36, 74), (84, 74), (36, 98), (60, 98), (84, 98)],
}

_SHAPES = {
    "hands": '<path class="soft" d="M60 98C40 90 30 72 34 46c6-4 12 0 14 8l6 20c2-10 4-30 6-40 3-6 8-6 8 0 2 10 4 30 6 40l6-20c2-8 8-12 14-8 4 26-6 44-26 52z"/>',
    "heart": '<path class="soft" d="M60 98C26 74 20 50 32 36c10-10 22-6 28 6 6-12 18-16 28-6 12 14 6 38-28 62z"/>',
    "tick": '<circle class="soft" cx="60" cy="60" r="40"/><path class="line" d="M40 62l15 15 27-32"/>',
    "question": '<path class="soft" d="M22 28h76a8 8 0 0 1 8 8v40a8 8 0 0 1-8 8H58l-20 18V84H22a8 8 0 0 1-8-8V36a8 8 0 0 1 8-8z"/><path class="line" d="M48 48c0-14 24-14 24 0 0 8-12 10-12 18"/><circle class="dot" cx="60" cy="74" r="3.5"/>',
    "pin": '<path class="soft" d="M60 108C36 78 30 66 30 48a30 30 0 0 1 60 0c0 18-6 30-30 60z"/><circle class="dot" cx="60" cy="48" r="11"/>',
    "clock": '<circle class="soft" cx="60" cy="60" r="42"/><path class="line" d="M60 34v28l18 12"/><circle class="dot" cx="60" cy="60" r="3.5"/>',
    "person": '<circle class="soft" cx="60" cy="38" r="20"/><path class="soft" d="M22 106c0-24 16-38 38-38s38 14 38 38z"/>',
    "coins": '<ellipse class="soft" cx="50" cy="86" rx="30" ry="10"/><ellipse class="soft" cx="50" cy="68" rx="30" ry="10"/><ellipse class="soft" cx="50" cy="50" rx="30" ry="10"/><ellipse class="soft" cx="76" cy="38" rx="24" ry="8"/>',
    "book": '<path class="soft" d="M60 34C46 24 28 24 14 30v68c14-6 32-6 46 4 14-10 32-10 46-4V30c-14-6-32-6-46 4z"/><path class="line" d="M60 34v68"/>',
    "hourglass": '<path class="soft" d="M34 18h52M34 102h52M40 18c0 30 20 30 20 42S40 72 40 102M80 18c0 30-20 30-20 42s20 12 20 42"/>',
    "globe": '<circle class="soft" cx="60" cy="60" r="42"/><ellipse class="line" cx="60" cy="60" rx="18" ry="42"/><path class="line" d="M18 60h84M26 38h68M26 82h68"/>',
    "board": '<rect class="soft" x="14" y="22" width="92" height="62" rx="6"/><path class="line" d="M28 42h48M28 56h64M28 70h36M40 84l-10 20M80 84l10 20"/>',
    "bulb": '<path class="soft" d="M60 14a28 28 0 0 0-16 51c4 4 6 8 6 14h20c0-6 2-10 6-14A28 28 0 0 0 60 14z"/><path class="line" d="M50 92h20M54 102h12"/>',
    "pie": '<circle class="soft" cx="60" cy="60" r="42"/><path class="dotfill" d="M60 60V18a42 42 0 0 1 40 54z"/>',
    "mic": '<rect class="soft" x="44" y="14" width="32" height="58" rx="16"/><path class="line" d="M32 62c0 18 12 30 28 30s28-12 28-30M60 92v16M44 108h32"/>',
    "scroll": '<path class="soft" d="M34 18h58a10 10 0 0 1 0 20H34a10 10 0 0 0 0-20zM34 38v52a12 12 0 0 1-12 12h60a12 12 0 0 0 12-12V38"/><path class="line" d="M46 56h30M46 70h30M46 84h20"/>',
    "late": '<circle class="soft" cx="52" cy="62" r="38"/><path class="line" d="M52 38v26l14 10"/><path class="line" d="M98 30l10 12-14 4"/>',
}


def _drawing(name: str) -> str:
    if name.startswith("dots"):
        n = int(name[4:])
        return "".join(f'<circle class="dotfill" cx="{x}" cy="{y}" r="{10 if n < 7 else 8}"/>' for x, y in _DOTS[n])
    return _SHAPES[name]


def has_picture(telugu: str) -> bool:
    return telugu in PICTURES


def picture(telugu: str, label_for) -> Markup | None:
    """Inline SVG for a Telugu word, or None. `label_for` is the catalog lookup for the screen-reader label."""
    entry = PICTURES.get(telugu)
    if entry is None:
        return None
    key, name = entry
    return Markup('<svg class="pic" viewBox="0 0 120 120" role="img" aria-label="') + escape(label_for(key)) + \
        Markup('">') + Markup(_drawing(name)) + Markup("</svg>")
