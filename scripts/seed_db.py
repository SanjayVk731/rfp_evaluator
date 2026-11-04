"""Create the SQLite database and seed the sample evaluation criteria.

Usage:
    python scripts/seed_db.py            # create tables, seed criteria if empty
    python scripts/seed_db.py --reset    # replace criteria with the defaults
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import db  # noqa: E402

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="reset criteria to defaults")
    parser.add_argument("--db", default=None, help="path to the SQLite file")
    args = parser.parse_args()

    db.init_db(args.db, seed=True, reset_criteria=args.reset)
    criteria = db.get_all_criteria(args.db)
    ok, total = db.check_weights([c for c in criteria if c["is_active"]])
    print(f"Database: {args.db or db.DEFAULT_DB_PATH}")
    for c in criteria:
        print(f"  [{c['criterion_id']}] {c['name']:<24} weight={c['weight']:>5}%  max={c['max_score']}  active={bool(c['is_active'])}")
    print(f"Active weight total: {total}% ({'OK' if ok else 'INVALID - must be 100'})")
