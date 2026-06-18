#!/usr/bin/env python3
"""
PuzzleVerse Quarantine From Audit V2

Moves flagged images into assets/_quarantine_bad_images/YYYYMMDD_HHMMSS/
Default is dry-run. Use --apply to actually move files.

This does NOT edit levels.js. It is safer to review first.
"""

import argparse
import csv
import shutil
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "tools" / "content_audit_report.csv"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--min-severity", type=int, default=80)
    args = ap.parse_args()

    if not REPORT.exists():
        raise SystemExit("Run tools/content_audit_v2.py first.")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    qroot = ROOT / "assets" / "_quarantine_bad_images" / stamp
    rows = list(csv.DictReader(REPORT.open(encoding="utf-8-sig")))
    selected = [r for r in rows if r.get("status") == "flagged" and int(float(r.get("severity") or 0)) >= args.min_severity]
    qrows = []

    if args.apply:
        qroot.mkdir(parents=True, exist_ok=True)

    for r in selected:
        rel = r.get("image", "")
        src = ROOT / rel
        if not src.exists():
            qrows.append({**r, "quarantinePath": "", "action": "missing_skip"})
            continue
        dest = qroot / rel
        qrows.append({**r, "quarantinePath": dest.relative_to(ROOT).as_posix(), "action": "move" if args.apply else "dry-run-move"})
        if args.apply:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dest))

    out = ROOT / "tools" / "quarantine_report.csv"
    if qrows:
        keys = list(qrows[0].keys())
        with out.open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(qrows)

    print("Selected:", len(selected))
    print("Applied:", args.apply)
    print("Min severity:", args.min_severity)
    print("Report:", out)
    if args.apply:
        print("Quarantine folder:", qroot)

if __name__ == "__main__":
    main()
