"""The Hindi string catalog (localisation-hindi-ui.md §1).

Lookups fail loudly: a missing key raises, a key whose approved wording is still pending raises, and a parameter
that would put Latin script on the page raises. Nothing falls back to English.
"""
import re
from pathlib import Path

import yaml

LATIN = re.compile(r"[A-Za-z]")
DEVANAGARI_DIGITS = str.maketrans("0123456789", "०१२३४५६७८९")


class MissingText(KeyError):
    pass


class PendingText(KeyError):
    """The wording must come from an approved source (e.g. the ethics-approved consent form) and is not in yet."""


class LatinInText(ValueError):
    pass


def _flatten(tree: dict, prefix: str = "") -> dict:
    out = {}
    for key, value in tree.items():
        full = f"{prefix}{key}"
        if isinstance(value, dict):
            out.update(_flatten(value, full + "."))
        else:
            out[full] = value
    return out


class Catalog:
    def __init__(self, values: dict, meta: dict, pending: dict):
        self._values, self._meta, self._pending = values, meta, pending

    @classmethod
    def load(cls, path: Path, *, pending_file: Path | None = None) -> "Catalog":
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        meta = raw.pop("_meta", {}) or {}
        pending = {}
        if pending_file and Path(pending_file).exists():
            for line in Path(pending_file).read_text(encoding="utf-8").splitlines():
                if line.strip() and not line.startswith("#"):
                    key, _, why = line.partition("\t")
                    pending[key.strip()] = why.strip()
        return cls(_flatten(raw), meta, pending)

    def has(self, key: str) -> bool:
        return key in self._values

    def is_pending(self, key: str) -> bool:
        return key in self._pending and key not in self._values

    def keys(self):
        return self._values.keys()

    def get(self, key: str, **params) -> str:
        if self.is_pending(key):
            raise PendingText(f"{key}: {self._pending[key]}")
        if key not in self._values:
            raise MissingText(key)
        for name, value in params.items():
            if LATIN.search(str(value)):
                raise LatinInText(f"parameter {name!r} of {key} contains Latin script")
        return str(self._values[key]).format_map({k: str(v) for k, v in params.items()})

    def number(self, n) -> str:
        s = str(n)
        return s.translate(DEVANAGARI_DIGITS) if self._meta.get("digits") == "devanagari" else s
