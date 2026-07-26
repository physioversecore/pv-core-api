"""
Run all seed scripts in dependency order:
   1. Users (no dependencies)
   2. Therapists (depends on users)
   3. Products (no dependencies)
   4. Sessions (depends on users + therapists)
   5. Reports (depends on users + sessions)
   6. Settings (currencies, payment methods)
"""

import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent

SCRIPTS = [
    "seed-users.py",
    "seed-patient-profiles.py",
    "seed-therapists.py",
    "seed-products.py",
    "seed-sessions.py",
    "seed-reports.py",
    "seed-reviews.py",
    "seed-therapist-dashboard.py",
    "seed-schedule.py",
    "seed-settings.py",
    "seed-refunds.py",
]


def main():
    for script in SCRIPTS:
        path = SCRIPTS_DIR / script
        print(f"\n{'='*60}")
        print(f"Running {script}...")
        print(f"{'='*60}")
        result = subprocess.run([sys.executable, str(path)], capture_output=False)
        if result.returncode != 0:
            print(f"FAILED {script} (exit code {result.returncode})")
            sys.exit(result.returncode)
        print(f"OK  {script}")

    print(f"\n{'='*60}")
    print("All seed scripts completed successfully.")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
