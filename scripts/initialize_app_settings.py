#!/usr/bin/env python
"""Initialize app_settings table with default values.

This script is intended to be run from the repository root using the
project virtualenv python, for example:

        ./venv/Scripts/python.exe ./scripts/initialize_app_settings.py

It must add the project root to sys.path before importing `app` so
`from app import ...` works when invoked as a standalone script.
"""

import sys
import os
import traceback

# Ensure project root is on sys.path so `import app` works when invoking
# this script as `python scripts/initialize_app_settings.py` from the repo root
proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if proj_root not in sys.path:
    sys.path.insert(0, proj_root)

try:
    from app import create_app, db
    from app.models.app_setting import AppSetting
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


def init_settings():
    """Initialize app_settings table with default configuration values."""
    app = create_app("production")

    with app.app_context():
        print("[Settings Init] Starting initialization...")

        # Define default settings (4 candidatos TIER 1)
        defaults = [
            {
                "key": "app_timezone",
                "value": os.environ.get("APP_TIMEZONE", "America/Mexico_City"),
                "description": "Application timezone (IANA format)",
                "data_type": "timezone",
                "default_value": "America/Mexico_City",
                "is_editable": True,
            },
            {
                "key": "public_pause_available_from_seconds",
                "value": os.environ.get("PUBLIC_PAUSE_AVAILABLE_FROM_SECONDS", "0"),
                "description": "Seconds after activity start when pause view becomes available",
                "data_type": "integer",
                "default_value": "0",
                "is_editable": True,
            },
            {
                "key": "public_pause_available_until_after_end_minutes",
                "value": os.environ.get(
                    "PUBLIC_PAUSE_AVAILABLE_UNTIL_AFTER_END_MINUTES", "5"
                ),
                "description": "Minutes after activity end to keep pause view available",
                "data_type": "integer",
                "default_value": "5",
                "is_editable": True,
            },
            {
                "key": "public_confirm_window_days",
                "value": os.environ.get("PUBLIC_CONFIRM_WINDOW_DAYS", "30"),
                "description": "Days window for confirming attendance in public views",
                "data_type": "integer",
                "default_value": "30",
                "is_editable": True,
            },
        ]

        created_count = 0
        for default in defaults:
            existing = AppSetting.query.filter_by(key=default["key"]).first()
            if existing:
                print(f"  ✓ Setting '{default['key']}' already exists (skipped)")
            else:
                setting = AppSetting(**default)
                db.session.add(setting)
                created_count += 1
                print(f"  ✓ Created setting '{default['key']}' = {default['value']}")

        if created_count > 0:
            db.session.commit()
            print(f"\n[Settings Init] ✓ Successfully created {created_count} settings")
        else:
            print("\n[Settings Init] ✓ All settings already exist (no changes)")


if __name__ == "__main__":
    init_settings()
