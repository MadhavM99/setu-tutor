"""Operator commands. `python -m setu.web.admin invite --role admin` prints a single-use invite code (shown once)."""
import argparse
import os

from sqlalchemy import create_engine

from . import auth


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m setu.web.admin")
    sub = ap.add_subparsers(dest="cmd", required=True)
    inv = sub.add_parser("invite")
    inv.add_argument("--role", required=True, choices=auth.ROLES)
    inv.add_argument("--cohort")
    inv.add_argument("--hours", type=float, default=24)
    args = ap.parse_args(argv)
    engine = create_engine(os.environ["SETU_APP_DATABASE_URL"])
    print(auth.create_invite(engine, role=args.role, cohort=args.cohort, valid_hours=args.hours))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
