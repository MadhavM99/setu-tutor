"""Hindi-only lint for the catalog and the learner and teacher templates (E-03, X-NOENG, TS-L10N, TS-UI-CALM).

What a person can see must contain no Latin script and no emoji: catalog values, the text of templates and the
visible attributes (alt, title, placeholder, aria-label, aria-description, submit/button values). Templates must
not load anything from another host, and must not print Latin string literals from expressions.

    python -m scripts.lint_hindi          # exit 1 and list every violation
"""
import dataclasses
import re
import sys
import unicodedata
from html.parser import HTMLParser
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
LATIN = re.compile(r"[A-Za-z]")
GROUPS = {"app", "nav", "page", "a11y", "onb", "form", "btn", "home", "consent", "tch", "err", "fb", "hint",
          "ladder", "res", "raju", "lang", "learn", "word", "chunk", "place", "scene", "lesson", "persona", "stage"}
VISIBLE_ATTRS = {"alt", "title", "placeholder", "aria-label", "aria-description"}
EXTERNAL = re.compile(r"^\s*(https?:)?//", re.IGNORECASE)
JINJA_COMMENT = re.compile(r"\{#.*?#\}", re.DOTALL)
JINJA_EXPR = re.compile(r"\{\{(.*?)\}\}", re.DOTALL)
JINJA_STMT = re.compile(r"\{%.*?%\}", re.DOTALL)
PLACEHOLDER = re.compile(r"\{[a-z_]+\}")  # format parameters such as {handle}; their values are checked at render
STRING = re.compile(r"""(?P<prefix>\bt\(\s*)?(?P<q>["'])(?P<s>(?:\\.|(?!(?P=q)).)*)(?P=q)""")


@dataclasses.dataclass(frozen=True)
class Violation:
    where: str
    problem: str
    text: str = ""


def _emoji(s: str) -> bool:
    return any(unicodedata.category(ch) == "So" or ch in "️‍" for ch in s)


def _flatten(tree, prefix=""):
    for k, v in tree.items():
        if isinstance(v, dict):
            yield from _flatten(v, f"{prefix}{k}.")
        else:
            yield f"{prefix}{k}", v


def lint_catalog(path: Path, *, allow_file: Path | None) -> list[Violation]:
    allowed = set()
    if allow_file and Path(allow_file).exists():
        allowed = {x.strip() for x in Path(allow_file).read_text(encoding="utf-8").splitlines()
                   if x.strip() and not x.startswith("#")}
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    raw.pop("_meta", None)
    out = []
    for group in raw:
        if group not in GROUPS:
            out.append(Violation(group, "unknown_group"))
    for key, value in _flatten({g: v for g, v in raw.items() if g in GROUPS}):
        text = "" if value is None else str(value)
        if not text.strip():
            out.append(Violation(key, "empty"))
        elif LATIN.search(PLACEHOLDER.sub("", text)) and key not in allowed:
            out.append(Violation(key, "latin", text))
        elif _emoji(text):
            out.append(Violation(key, "emoji", text))
    return out


class _Visible(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.found: list[tuple[str, str]] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style"):
            self._skip += 1
        for k, v in a.items():
            if v is None:
                continue
            if k in VISIBLE_ATTRS:
                self.found.append(("attribute " + k, v))
            if k in ("src", "href", "action") and EXTERNAL.match(v):
                self.found.append(("external", v))
        if tag == "input" and (a.get("type") or "").lower() in ("submit", "button", "reset") and a.get("value"):
            self.found.append(("attribute value", a["value"]))

    handle_startendtag = handle_starttag

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip and data.strip():
            self.found.append(("text", data))


def lint_template_source(source: str, where: str) -> list[Violation]:
    out = []
    source = JINJA_COMMENT.sub("", source)
    for expr in JINJA_EXPR.findall(source):
        for m in STRING.finditer(expr):
            if not m.group("prefix") and LATIN.search(m.group("s")):
                out.append(Violation(where, "latin_literal", m.group("s")))
    markup = JINJA_STMT.sub("", JINJA_EXPR.sub("", source))
    parser = _Visible()
    parser.feed(markup)
    for kind, value in parser.found:
        if kind == "external":
            out.append(Violation(where, "external", value))
        elif LATIN.search(value):
            out.append(Violation(where, f"latin in {kind}", value.strip()))
        elif _emoji(value):
            out.append(Violation(where, f"emoji in {kind}", value.strip()))
    return out


def lint_templates(templates_dir: Path) -> list[Violation]:
    templates_dir = Path(templates_dir)
    files = [*templates_dir.glob("*.html"), *(templates_dir / "learner").rglob("*.html"),
             *(templates_dir / "teacher").rglob("*.html")]
    out = []
    for p in sorted(files):
        out += lint_template_source(p.read_text(encoding="utf-8"), p.relative_to(templates_dir).as_posix())
    return out


def main() -> int:
    violations = lint_catalog(ROOT / "locale/hi.yaml", allow_file=ROOT / "locale/allow-latin.txt")
    violations += lint_templates(ROOT / "setu/web/templates")
    for v in violations:
        print(f"{v.where}: {v.problem}: {v.text}")
    print(f"{len(violations)} violations")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
