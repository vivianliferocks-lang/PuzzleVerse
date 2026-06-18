#!/usr/bin/env python3
"""
PuzzleVerse unused image cleaner.
Default mode is dry-run. It scans src/levels.js for image references and deletes
unreferenced image.* files only when --apply is passed.
"""
import argparse
import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEVELS = ROOT / "src" / "levels.js"
ASSETS = ROOT / "assets" / "puzzle-library"
REPORT = ROOT / "tools" / "prune_unused_images_report.csv"
IMG_RE = re.compile(r"assets/puzzle-library/[^\"']+/image\.(?:jpg|jpeg|png|webp)", re.I)


def norm(path_text: str) -> str:
    return path_text.replace("\\", "/").lstrip("./")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Actually delete unreferenced image files. Without this, only a report is written.")
    ap.add_argument("--delete-backups", action="store_true", help="Also delete old src/levels.js.bak* files to save space.")
    args = ap.parse_args()

    if not LEVELS.exists():
        raise SystemExit(f"Missing {LEVELS}")
    if not ASSETS.exists():
        raise SystemExit(f"Missing {ASSETS}")

    text = LEVELS.read_text(encoding="utf-8", errors="ignore")
    refs = {norm(m.group(0)) for m in IMG_RE.finditer(text)}

    images = []
    for ext in ("*.jpg", "*.jpeg", "*.png", "*.webp"):
        images.extend(ASSETS.rglob(ext))

    rows = []
    delete_count = 0
    for img in sorted(images):
        rel = norm(str(img.relative_to(ROOT)))
        keep = rel in refs
        action = "keep" if keep else "delete" if args.apply else "dry-run-delete"
        rows.append({"path": rel, "referenced": keep, "action": action})
        if not keep and args.apply:
            img.unlink()
            delete_count += 1

    backup_rows = []
    if args.delete_backups:
        for bak in (ROOT / "src").glob("levels.js.bak*"):
            rel = norm(str(bak.relative_to(ROOT)))
            backup_rows.append({"path": rel, "referenced": False, "action": "delete-backup" if args.apply else "dry-run-delete-backup"})
            if args.apply:
                bak.unlink()
                delete_count += 1

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    with REPORT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["path", "referenced", "action"])
        writer.writeheader()
        writer.writerows(rows + backup_rows)

    print(f"Referenced images in levels.js: {len(refs)}")
    print(f"Image files found: {len(images)}")
    print(f"Unreferenced image files: {sum(1 for r in rows if not r['referenced'])}")
    print(f"Deleted files: {delete_count}")
    print(f"Report: {REPORT}")
    if not args.apply:
        print("Dry run only. Run with --apply after reviewing the report.")


if __name__ == "__main__":
    main()
