#!/usr/bin/env python3
"""
PuzzleVerse Apply Manual Overrides V2

Reads tools/manual_overrides_template.csv after you fill replacementPath.

For each row where:
decision = replace
replacementPath = path/to/new/image.jpg

It copies the replacement into the level folder as image.jpg/png/webp
and updates src/levels.js localImage/image fields.
"""

import csv
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEVELS = ROOT / "src" / "levels.js"
OVERRIDES = ROOT / "tools" / "manual_overrides_template.csv"

def load_levels_text():
    text = LEVELS.read_text(encoding="utf-8")
    m = re.search(r"window\.PUZZLEVERSE_LEVELS\s*=\s*(\[[\s\S]*?\]);", text)
    if not m:
        raise SystemExit("Could not find PUZZLEVERSE_LEVELS")
    return text, m.start(1), m.end(1), json.loads(m.group(1))

def main():
    if not OVERRIDES.exists():
        raise SystemExit("manual_overrides_template.csv not found.")
    text, s, e, levels = load_levels_text()
    by_id = {l.get("id"): l for l in levels}
    changed = 0

    rows = list(csv.DictReader(OVERRIDES.open(encoding="utf-8-sig")))
    for row in rows:
        if (row.get("decision") or "").strip().lower() != "replace":
            continue
        repl = (row.get("replacementPath") or "").strip()
        if not repl:
            continue
        src = ROOT / repl
        if not src.exists():
            print("Missing replacement:", repl)
            continue
        lvl = by_id.get(row.get("id"))
        if not lvl:
            print("Level id not found:", row.get("id"))
            continue

        current = lvl.get("localImage") or lvl.get("image")
        if not current:
            print("No current path:", lvl.get("title"))
            continue
        dest_dir = (ROOT / current).parent
        ext = src.suffix.lower()
        if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
            print("Unsupported image:", src)
            continue
        dest = dest_dir / ("image" + ext.replace(".jpeg", ".jpg"))
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        new_rel = dest.relative_to(ROOT).as_posix()
        lvl["image"] = new_rel
        lvl["localImage"] = new_rel
        lvl["licenseStatus"] = "manual-replacement-review"
        changed += 1
        print("Updated:", lvl.get("title"), "->", new_rel)

    if changed:
        backup = LEVELS.with_suffix(".js.bak_manual_overrides")
        shutil.copy2(LEVELS, backup)
        LEVELS.write_text(text[:s] + json.dumps(levels, ensure_ascii=False, indent=2) + text[e:], encoding="utf-8")
        print("Changed:", changed)
        print("Backup:", backup)
    else:
        print("No changes. Fill replacementPath in tools/manual_overrides_template.csv first.")

if __name__ == "__main__":
    main()
