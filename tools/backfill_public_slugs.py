"""
Backfill tool to populate `public_slug` for Event and Activity models.

Run this from the project root with the proper virtualenv active. It will:
- create slugs for records missing `public_slug` using slug_utils.generate_unique_slug
- optionally commit changes to the database

Usage:
  python tools/backfill_public_slugs.py --commit

Be sure to have a backup/migration before running in production.
"""

import argparse
import sys
import os
import traceback

# Ensure project root is on sys.path so `import app` works when invoking
# this script as `python tools/backfill_public_slugs.py` from the repo root
proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if proj_root not in sys.path:
    sys.path.insert(0, proj_root)

try:
    from app import create_app, db
    from app.models.event import Event
    from app.models.activity import Activity
    from app.utils.slug_utils import generate_unique_slug
except Exception as exc:
    # Diagnostic output to help debugging environment/path issues
    print("Error importing app package:", file=sys.stderr)
    print(str(exc), file=sys.stderr)
    print("\nDiagnostic info:", file=sys.stderr)
    try:
        print("cwd=", os.getcwd(), file=sys.stderr)
        print("proj_root=", proj_root, file=sys.stderr)
        print("sys.path sample:", file=sys.stderr)
        for p in sys.path[:10]:
            print("  " + repr(p), file=sys.stderr)
        print("\nproj_root contents (top 20):", file=sys.stderr)
        for i, name in enumerate(sorted(os.listdir(proj_root))[:20]):
            print(f"  {i + 1}. {name}", file=sys.stderr)
    except Exception:
        print("Error gathering diagnostic info", file=sys.stderr)
        traceback.print_exc()
    # Re-raise so user gets the original traceback
    raise


def run(commit=False):
    app = create_app()
    with app.app_context():
        session = db.session

        for Model in (Event, Activity):
            print(f"Processing {Model.__tablename__}...")
            missing = (
                session.query(Model).filter(getattr(Model, "public_slug") is None).all()
            )
            print(f"  Found {len(missing)} records without public_slug")
            for obj in missing:
                source = getattr(obj, "name", None) or getattr(obj, "title", None) or ""
                if not source:
                    print(f"   Skipping id={obj.id} (no name)")
                    continue
                slug = generate_unique_slug(session, Model, source)
                print(f"   id={obj.id} -> {slug}")
                obj.public_slug = slug
            if commit:
                session.commit()
                print(f"  Committed changes for {Model.__tablename__}")
            else:
                print(
                    f"  Dry run for {Model.__tablename__} (no commit). Use --commit to persist"
                )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit", action="store_true", help="Persist changes")
    args = parser.parse_args()
    try:
        run(commit=args.commit)
    except Exception:
        print("Error while running backfill", file=sys.stderr)
        raise
