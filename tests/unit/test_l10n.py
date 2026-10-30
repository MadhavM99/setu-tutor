"""Hindi-only learner and teacher UI (X-NOENG, E-03, M-54; TS-L10N-01..05, TS-UI-CALM).

The lint checks what a person can see: catalog values, the visible text of templates and the visible attributes
(alt, title, placeholder, aria-label, button values). Tag and attribute names are markup, not text.
"""
import ast
import re
from pathlib import Path

import pytest

from scripts import lint_hindi
from setu.web import i18n

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / "setu/web/templates"
CATALOG = ROOT / "locale/hi.yaml"


@pytest.fixture(scope="module")
def catalog():
    return i18n.Catalog.load(CATALOG, pending_file=ROOT / "locale/pending.txt")


# ---------------------------------------------------------------- TS-L10N-01: the catalog


def test_catalog_has_no_latin_no_emoji_and_known_groups_only():
    assert lint_hindi.lint_catalog(CATALOG, allow_file=ROOT / "locale/allow-latin.txt") == []


def test_the_latin_allow_list_starts_empty():
    lines = [x for x in (ROOT / "locale/allow-latin.txt").read_text(encoding="utf-8").splitlines()
             if x.strip() and not x.startswith("#")]
    assert lines == []  # adding an exception needs an ADR (localisation-hindi-ui.md §1)


@pytest.mark.parametrize("value,problem", [
    ("Submit", "latin"),
    ("अंदर आएँ (Sign in)", "latin"),
    ("शाबाश 🎉", "emoji"),
    ("", "empty"),
])
def test_catalog_lint_catches_bad_values(tmp_path, value, problem):
    path = tmp_path / "hi.yaml"
    path.write_text(f'btn:\n  ok: "{value}"\n', encoding="utf-8")
    assert [v.problem for v in lint_hindi.lint_catalog(path, allow_file=None)] == [problem]


def test_catalog_lint_rejects_unknown_groups(tmp_path):
    path = tmp_path / "hi.yaml"
    path.write_text('marketing:\n  hello: "नमस्ते"\n', encoding="utf-8")
    assert [v.problem for v in lint_hindi.lint_catalog(path, allow_file=None)] == ["unknown_group"]


# ---------------------------------------------------------------- TS-L10N-02/03: templates


def test_all_learner_and_teacher_templates_pass_the_lint():
    assert lint_hindi.lint_templates(TEMPLATES) == []


@pytest.mark.parametrize("snippet,should_fail", [
    ("<p>Hello</p>", True),
    ('<input placeholder="Name">', True),
    ('<img src="/static/x.png" alt="logo">', True),
    ('<button aria-label="close">×</button>', True),
    ('<input type="submit" value="Submit">', True),
    ("<p>शाबाश 🎉</p>", True),
    ('<p>{{ "Hello" }}</p>', True),                 # a Latin literal printed straight from an expression
    ('<a href="https://fonts.googleapis.com/css">x</a>', True),  # external resource
    ('<div class="card" id="main">{{ t("nav.home") }}</div>', False),
    ("{# an English comment for developers #}<p>{{ t('home.greeting') }}</p>", False),
    ('<input type="submit" value="{{ t(\'btn.signin\') }}">', False),
    ("{% if user %}<p>{{ user.handle }}</p>{% endif %}", False),
    ('<span lang="te">{{ te("నమస్కారం") }}</span>', False),
    ("<style>.x { color: red }</style><script>var a = 1;</script>", False),
])
def test_template_lint_on_snippets(tmp_path, snippet, should_fail):
    (tmp_path / "learner").mkdir()
    (tmp_path / "learner" / "x.html").write_text(snippet, encoding="utf-8")
    assert bool(lint_hindi.lint_templates(tmp_path)) is should_fail


def test_teacher_templates_are_checked_too(tmp_path):
    (tmp_path / "teacher").mkdir()
    (tmp_path / "teacher" / "x.html").write_text("<h1>Teacher</h1>", encoding="utf-8")
    assert lint_hindi.lint_templates(tmp_path)


# ---------------------------------------------------------------- TS-L10N-04: every key used exists


def _template_keys():
    keys = set()
    for p in TEMPLATES.rglob("*.html"):
        keys |= set(re.findall(r"""\bt\(\s*["']([a-z0-9_.]+)["']""", p.read_text(encoding="utf-8")))
    return keys


def _api_error_codes():
    codes = set()
    for p in (ROOT / "setu").rglob("*.py"):
        for node in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            if (isinstance(node, ast.Call) and getattr(node.func, "id", None) == "ApiError" and node.args
                    and isinstance(node.args[0], ast.Constant)):
                codes.add(node.args[0].value)
    return codes


def test_every_template_key_exists(catalog):
    # Keys built from a prefix (e.g. "consent.scope." ~ scope) are checked by their own tests.
    missing = [k for k in _template_keys() if not k.endswith(".") and not catalog.has(k)]
    assert missing == []


def test_every_api_error_has_a_hindi_message(catalog):
    codes = _api_error_codes()
    assert {"auth_failed", "locked", "invite_invalid", "not_signed_in", "forbidden", "validation"} <= codes
    assert [c for c in codes if not catalog.has(f"err.{c}")] == []


def test_every_consent_scope_has_a_label(catalog):
    from setu.web import consent_forms

    for form in consent_forms.FORMS.values():
        for scope in form["scopes"]:
            assert catalog.has(f"consent.scope.{scope}")


# ---------------------------------------------------------------- TS-L10N-05: fail closed at runtime


def test_missing_key_fails_loudly(catalog):
    with pytest.raises(i18n.MissingText):
        catalog.get("nav.does_not_exist")


def test_pending_text_is_never_rendered(catalog):
    # The consent form text must be the ethics-approved version; until it is in the catalog it cannot be shown.
    assert catalog.is_pending("consent.pilot_v1")
    with pytest.raises(i18n.PendingText):
        catalog.get("consent.pilot_v1")


def test_parameters_are_filled_and_must_not_inject_latin(catalog):
    assert "1234-5678" in catalog.get("home.signed_in_as", handle="1234-5678")
    with pytest.raises(i18n.LatinInText):
        catalog.get("home.signed_in_as", handle="admin")


def test_counts_use_devanagari_digits_by_default(catalog):
    assert catalog.number(15) == "१५"


def test_css_and_templates_load_nothing_from_outside(tmp_path):
    for p in [*TEMPLATES.rglob("*.html"), *(ROOT / "setu/web/static/css").rglob("*.css")]:
        assert not re.search(r"(https?:)?//[a-z0-9.-]+\.[a-z]{2,}", p.read_text(encoding="utf-8")), p
