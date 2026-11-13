"""Seeded train/val split of the accepted training pairs (TASKS.md task 10, step 3).

Input: data/ft/pairs.jsonl (from `ft_data`). Output: data/ft/train.jsonl, data/ft/val.jsonl and reports/ft_split.json.

- **Frozen cases stay out.** Every sentence of every pair (correct and wrong) is compared with every sentence of the
  29 frozen planting cases (correct and wrong). This is stricter than `ft_data.near_duplicate`, which compares like
  sides only. Any exact match or near-duplicate (normalised character edit distance <= `ft_data.NEAR`) is dropped
  and counted. `tests/unit/test_ft_split.py` fails if the written files contain one.
- **Near-duplicates stay together.** Within a rule, pairs whose correct or wrong sentences are near-duplicates of
  each other form one group (union-find), and so do pairs with the same correct sentence across rules. A group goes
  wholly into train or wholly into val, so val does not just repeat train with one word changed.
- **Stratified by rule, seeded.** For each rule, its groups are shuffled with `random.Random(f"{seed}:{rule}")`, and
  round(VAL_FRACTION x groups) of them go to val (at least 1 when the rule has 2 or more groups). The same seed and the
  same pairs always give the same split.

    .venv/bin/python -m setu.research.ft_split            # seed 13
    .venv/bin/python -m setu.research.ft_split --seed 7
"""
import argparse
import hashlib
import json
import random
from collections import Counter, defaultdict

from setu.domain.normalise import canonical

from . import ft_data as fd

SEED = 13
VAL_FRACTION = 0.1
SPLIT_REPORT = fd.ROOT / "reports/ft_split.json"


def _close(a: str, b: str, near: float) -> bool:
    """norm_distance(a, b) <= near, skipping the edit distance when the length gap alone already exceeds it."""
    a, b = canonical(a), canonical(b)
    if abs(len(a) - len(b)) > near * max(1, len(a), len(b)):
        return False
    return fd.norm_distance(a, b) <= near


def frozen_sentences() -> list[str]:
    return [canonical(s) for _, _, c, w in fd.frozen_pairs() for s in (c, w)]


def frozen_overlap(pair: dict, frozen=None, near: float = fd.NEAR) -> str | None:
    """'exact' or 'near' if either sentence of the pair matches any frozen sentence (either side), else None."""
    frozen = frozen if frozen is not None else frozen_sentences()
    worst = None
    for s in (canonical(pair["correct"]), canonical(pair["wrong"])):
        for f in frozen:
            if s == f:
                return "exact"
            if _close(s, f, near):
                worst = "near"
    return worst


def _near(a: dict, b: dict, near: float) -> bool:
    return any(_close(a[k], b[k], near) for k in ("correct", "wrong"))


def groups(pairs: list[dict], near: float = fd.NEAR) -> list[int]:
    """Group id per pair: near-duplicates within a rule, and identical correct sentences across rules, share one."""
    parent = list(range(len(pairs)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        parent[find(i)] = find(j)

    by_rule, by_correct = defaultdict(list), {}
    for i, p in enumerate(pairs):
        by_rule[p["rule_id"]].append(i)
        c = canonical(p["correct"])
        if c in by_correct:
            union(i, by_correct[c])
        by_correct.setdefault(c, i)
    for idx in by_rule.values():
        for a in range(len(idx)):
            for b in range(a + 1, len(idx)):
                if _near(pairs[idx[a]], pairs[idx[b]], near):
                    union(idx[a], idx[b])
    return [find(i) for i in range(len(pairs))]


def split(pairs: list[dict], seed: int = SEED, val_fraction: float = VAL_FRACTION) -> dict:
    frozen = frozen_sentences()
    kept, dropped = [], []
    for p in pairs:
        o = frozen_overlap(p, frozen)
        (dropped if o else kept).append({**p, "frozen_overlap": o} if o else p)
    gid = groups(kept)
    rule_groups = defaultdict(set)  # a group id is the index of its root pair; the group belongs to that pair's rule
    for g in gid:
        rule_groups[kept[g]["rule_id"]].add(g)
    val_groups = set()
    for rule in sorted(rule_groups):
        gs = sorted(rule_groups[rule], key=lambda g: (canonical(kept[g]["correct"]), canonical(kept[g]["wrong"])))
        random.Random(f"{seed}:{rule}").shuffle(gs)
        n_val = round(val_fraction * len(gs))
        if len(gs) >= 2:
            n_val = max(1, n_val)
        val_groups.update(gs[:n_val])
    train = [p for i, p in enumerate(kept) if gid[i] not in val_groups]
    val = [p for i, p in enumerate(kept) if gid[i] in val_groups]
    return {"train": train, "val": val, "dropped": dropped, "n_groups": len(set(gid))}


def leaks(train: list[dict], val: list[dict], near: float = fd.NEAR) -> list[tuple]:
    """(val, train) pairs of the same rule that are near-duplicates; empty for a split made by `split`."""
    tr = defaultdict(list)
    for p in train:
        tr[p["rule_id"]].append(p)
    return [(v["correct"], t["correct"]) for v in val for t in tr[v["rule_id"]] if _near(v, t, near)]


def _sha(rows) -> str:
    return hashlib.sha256("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n"
                                  for r in rows).encode("utf-8")).hexdigest()[:16]


def report(res: dict, seed: int, val_fraction: float) -> dict:
    rules = sorted({p["rule_id"] for p in res["train"] + res["val"]})
    tr, va = Counter(p["rule_id"] for p in res["train"]), Counter(p["rule_id"] for p in res["val"])
    return {"seed": seed, "val_fraction": val_fraction, "near_threshold": fd.NEAR,
            "train": len(res["train"]), "val": len(res["val"]), "groups": res["n_groups"],
            "dropped_frozen_overlap": dict(Counter(p["frozen_overlap"] for p in res["dropped"])),
            "by_rule": {r: {"train": tr[r], "val": va[r]} for r in rules},
            "by_source": {"train": dict(Counter(p["source"] for p in res["train"])),
                          "val": dict(Counter(p["source"] for p in res["val"]))},
            "val_train_near_duplicates": len(leaks(res["train"], res["val"])),
            "sha256_16": {"train": _sha(res["train"]), "val": _sha(res["val"])},
            "note": "near-duplicate grouping is within a rule (plus identical correct sentences across rules)"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--val-fraction", type=float, default=VAL_FRACTION)
    args = ap.parse_args(argv)
    src = fd.DATA / "pairs.jsonl"
    pairs = [json.loads(x) for x in src.read_text(encoding="utf-8").splitlines() if x.strip()]
    res = split(pairs, args.seed, args.val_fraction)
    for name in ("train", "val"):
        (fd.DATA / f"{name}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in res[name]),
                                               encoding="utf-8")
    rep = report(res, args.seed, args.val_fraction)
    SPLIT_REPORT.write_text(json.dumps(rep, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"train {rep['train']} · val {rep['val']} · groups {rep['groups']} · dropped {rep['dropped_frozen_overlap']}"
          f" · val/train near-dups {rep['val_train_near_duplicates']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
