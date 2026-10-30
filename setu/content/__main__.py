"""Content CLI.

    python -m setu.content convert           # one-time: source snapshots -> content/ YAML (+ CONVERSION.json)
    python -m setu.content validate          # check content/; exit 1 on errors, list issues
    python -m setu.content import            # validate, then import into SETU_DATABASE_URL as setu_content
"""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m setu.content")
    ap.add_argument("command", choices=("convert", "validate", "import"))
    ap.add_argument("--content", default=str(ROOT / "content"))
    args = ap.parse_args(argv)

    from . import convert, validate

    if args.command == "convert":
        files = convert.convert_all(Path(args.content), root=ROOT)
        convert.write_manifest(Path(args.content), files, ROOT)
        print(f"wrote {len(files)} files to {args.content}")
        return 0

    tree = validate.load_tree(Path(args.content))
    report = validate.validate_tree(tree)
    for e in report.errors:
        print(f"ERROR {e.code}: {e.detail}")
    n_issues = sum(len(v) for v in report.issues.values())
    print(f"{len(tree.rules)} rules, {sum(len(r['items']) for r in tree.rules)} items, {len(tree.lexemes)} words, "
          f"{len(tree.scenes)} scenes · {len(report.errors)} errors · {n_issues} issues on "
          f"{len(report.issues)} records (issues import as drafts and block approval)")
    if report.errors:
        return 1
    if args.command == "validate":
        return 0

    from sqlalchemy import create_engine

    from . import importer

    result = importer.import_tree(create_engine(os.environ["SETU_DATABASE_URL"]), tree, report=report)
    print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
