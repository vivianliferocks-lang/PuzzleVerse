#!/usr/bin/env python3
"""
PuzzleVerse Content Audit V2

Runs locally on your PuzzleVerse folder, so you do not need to upload a 1GB image pack.

Outputs:
- tools/content_audit_report.csv
- tools/review_gallery_flagged.html
- tools/review_gallery_all.html
- tools/manual_overrides_template.csv

What it catches:
- missing images
- broken unreadable images
- tiny / suspicious files
- blank or very low detail images
- famous_people images likely to be plaques/statues/buildings/landscapes
- science images that are probably not educational/diagram-style
- obvious keyword mismatches in metadata/path/source fields
"""

import argparse
import csv
import json
import math
import os
import re
import statistics
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
LEVELS_JS = ROOT / "src" / "levels.js"
OUT_DIR = ROOT / "tools"
ASSET_ROOT = ROOT / "assets" / "puzzle-library"

try:
    from PIL import Image, ImageStat
    PIL_OK = True
except Exception:
    PIL_OK = False

FAMOUS_BAD = [
    "statue", "bust", "memorial", "plaque", "grave", "tomb", "cemetery",
    "birthplace", "house", "home", "museum", "institute", "school",
    "university", "building", "hall", "auditorium", "stamp", "coin",
    "banknote", "signature", "logo", "tree", "garden", "street", "road",
    "airport", "bridge", "temple", "church", "mosque", "shrine", "samadhi",
    "mausoleum", "medal"
]
FAMOUS_GOOD = [
    "portrait", "photo", "photograph", "painting", "engraving", "depiction",
    "head", "face", "person", "profile", "official", "self-portrait"
]
SCIENCE_DIAGRAM_GOOD = [
    "diagram", "anatomy", "structure", "schematic", "labeled", "labelled",
    "cutaway", "cross-section", "model", "illustration", "infographic",
    "chart", "map", "nasa", "telescope", "spacecraft", "rover"
]
SCIENCE_BAD = [
    "logo", "plaque", "building", "conference", "auditorium", "portrait",
    "person", "street", "museum-room", "random"
]
CATEGORIES_REQUIRING_IMAGE = {
    "world_places", "famous_people", "science_discoveries", "clouds", "constellations",
    "deep_sea", "corals", "small_critters", "animals", "dinosaurs_extinct_animals",
    "extinct_civilizations"
}

def read_levels():
    text = LEVELS_JS.read_text(encoding="utf-8")
    m = re.search(r"window\.PUZZLEVERSE_LEVELS\s*=\s*(\[[\s\S]*?\]);", text)
    if not m:
        raise SystemExit("Could not find window.PUZZLEVERSE_LEVELS in src/levels.js")
    return json.loads(m.group(1))

def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", str(s or "").lower()).strip()

def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", str(s or "").lower()).strip("-")

def image_path(level):
    for key in ["localImage", "image", "imageUrl", "thumbnail"]:
        v = level.get(key)
        if v and isinstance(v, str) and not v.startswith("data:"):
            return v
    return ""

def file_metadata_text(level, img_rel):
    parts = [
        level.get("title", ""),
        level.get("category", ""),
        level.get("theme", ""),
        level.get("sourceTitle", ""),
        level.get("sourceProvider", ""),
        level.get("sourceSearchUrl", ""),
        level.get("credit", ""),
        level.get("licenseStatus", ""),
        img_rel,
    ]
    return norm(" ".join(map(str, parts)))

def title_tokens(title):
    stop = set("the a an of and in for with to from by on at de da di la le el al bin ibn jr sr dr sir saint st".split())
    return [t for t in norm(title).split() if len(t) > 2 and t not in stop]

def safe_rel(p):
    try:
        return p.relative_to(ROOT).as_posix()
    except Exception:
        return str(p)

def image_stats(abs_path):
    stats = {
        "exists": abs_path.exists(),
        "readable": False,
        "width": "",
        "height": "",
        "megapixels": "",
        "file_kb": "",
        "aspect": "",
        "brightness_std": "",
        "mean_brightness": "",
        "format": "",
    }
    if abs_path.exists():
        stats["file_kb"] = round(abs_path.stat().st_size / 1024, 1)
    if not PIL_OK or not abs_path.exists():
        return stats
    try:
        with Image.open(abs_path) as im:
            im = im.convert("RGB")
            w, h = im.size
            stats.update({
                "readable": True,
                "width": w,
                "height": h,
                "megapixels": round((w*h)/1_000_000, 3),
                "aspect": round(w / h, 3) if h else "",
                "format": Image.open(abs_path).format if abs_path.exists() else "",
            })
            small = im.resize((64, 64))
            gray = small.convert("L")
            stat = ImageStat.Stat(gray)
            stats["mean_brightness"] = round(stat.mean[0], 2)
            stats["brightness_std"] = round(stat.stddev[0], 2)
    except Exception:
        stats["readable"] = False
    return stats

def audit_level(level):
    img_rel = image_path(level)
    abs_path = ROOT / img_rel if img_rel else Path("__missing__")
    stats = image_stats(abs_path)
    category = level.get("category", "")
    title = level.get("title", "")
    meta = file_metadata_text(level, img_rel)
    reasons = []
    severity = 0

    if not img_rel:
        reasons.append("no_image_path")
        severity += 100
    if not stats["exists"]:
        reasons.append("missing_file")
        severity += 100
    elif not stats["readable"]:
        reasons.append("unreadable_or_broken_image")
        severity += 90

    if stats["exists"] and stats["file_kb"] != "" and float(stats["file_kb"]) < 8:
        reasons.append("very_small_file")
        severity += 35

    if stats["readable"]:
        if stats["width"] and stats["height"]:
            if int(stats["width"]) < 320 or int(stats["height"]) < 220:
                reasons.append("low_resolution")
                severity += 25
        if stats["brightness_std"] != "" and float(stats["brightness_std"]) < 12:
            reasons.append("low_detail_or_blank_like")
            severity += 45

    # Title token sanity from metadata/source/path. This catches obviously unrelated files when sourceTitle is available.
    tokens = title_tokens(title)
    if tokens:
        matched = sum(1 for t in tokens if t in meta)
        if matched == 0 and category in CATEGORIES_REQUIRING_IMAGE:
            reasons.append("title_tokens_not_found_in_metadata_path")
            severity += 20

    if category == "famous_people":
        bad_hits = [k for k in FAMOUS_BAD if k in meta]
        good_hits = [k for k in FAMOUS_GOOD if k in meta]
        if bad_hits:
            reasons.append("famous_people_bad_keywords:" + "|".join(bad_hits[:5]))
            severity += 45
        if not good_hits:
            reasons.append("famous_people_no_portrait_keywords")
            severity += 18
        if stats["readable"] and stats["aspect"] != "":
            aspect = float(stats["aspect"])
            # Many portraits are taller than wide. Landscape is not always wrong, but it deserves review.
            if aspect > 1.55:
                reasons.append("famous_people_landscape_aspect_review")
                severity += 22

    if category == "science_discoveries":
        good_hits = [k for k in SCIENCE_DIAGRAM_GOOD if k in meta]
        bad_hits = [k for k in SCIENCE_BAD if k in meta]
        science_title = norm(title)
        needs_diagram = any(k in science_title for k in [
            "anatomy", "cell", "skeleton", "dna", "neuron", "heart", "cycle",
            "tectonics", "solar system", "black hole", "milky way", "nebula",
            "supernova", "microscope", "telescope"
        ])
        if needs_diagram and not good_hits:
            reasons.append("science_needs_educational_diagram_keywords")
            severity += 35
        if bad_hits:
            reasons.append("science_bad_keywords:" + "|".join(bad_hits[:5]))
            severity += 35

    # Broken card images from screenshots: no file or metadata placeholder.
    if "placeholder" in meta or "pending download" in meta or "pending-download" in meta:
        reasons.append("placeholder_or_pending_download")
        severity += 50

    if not reasons:
        reasons.append("ok")

    return {
        "levelNumber": level.get("levelNumber", ""),
        "id": level.get("id", ""),
        "title": title,
        "category": category,
        "image": img_rel,
        "abs_path": str(abs_path),
        "severity": severity,
        "status": "flagged" if severity >= 35 else "ok",
        "reasons": "; ".join(reasons),
        **stats
    }

def write_csv(rows, path):
    keys = [
        "levelNumber", "id", "title", "category", "status", "severity", "reasons",
        "image", "exists", "readable", "width", "height", "megapixels", "file_kb",
        "aspect", "brightness_std", "mean_brightness"
    ]
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows([{k: r.get(k, "") for k in keys} for r in rows])

def gallery(rows, path, title):
    cards = []
    for r in rows:
        img = r["image"] or ""
        img_src = "../" + img if img else ""
        badge = "bad" if r["status"] == "flagged" else "ok"
        cards.append(f"""
        <article class="card {badge}">
          <div class="imgwrap"><img src="{img_src}" onerror="this.classList.add('broken')" /></div>
          <div class="body">
            <h3>{r['levelNumber']}. {escape(r['title'])}</h3>
            <p><b>{escape(r['category'])}</b></p>
            <p>Status: <b>{r['status']}</b> · Severity: <b>{r['severity']}</b></p>
            <p class="reason">{escape(r['reasons'])}</p>
            <p class="path">{escape(r['image'])}</p>
          </div>
        </article>
        """)
    html = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>{escape(title)}</title>
<style>
body{{font-family:Arial, sans-serif;background:#f5f7fb;margin:0;padding:18px;color:#111936}}
h1{{margin:0 0 12px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:14px}}
.card{{background:white;border-radius:14px;overflow:hidden;box-shadow:0 6px 18px #0001;border:3px solid transparent}}
.card.bad{{border-color:#ff5f5f}}
.card.ok{{border-color:#dfe6ff}}
.imgwrap{{height:170px;background:#eef2ff;display:flex;align-items:center;justify-content:center}}
img{{width:100%;height:100%;object-fit:cover}}
img.broken{{display:none}}
.body{{padding:12px}}
h3{{font-size:18px;margin:0 0 8px}}
p{{margin:6px 0}}
.reason{{color:#9b1c1c;font-size:13px;line-height:1.35}}
.path{{font-size:12px;color:#63708e;word-break:break-all}}
</style>
</head>
<body>
<h1>{escape(title)}</h1>
<p>Generated locally by PuzzleVerse Content Audit. Red cards need review/replacement.</p>
<div class="grid">
{''.join(cards)}
</div>
</body>
</html>"""
    path.write_text(html, encoding="utf-8")

def escape(s):
    return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")

def manual_template(rows):
    path = OUT_DIR / "manual_overrides_template.csv"
    keys = ["levelNumber", "id", "title", "category", "currentImage", "decision", "replacementPath", "notes"]
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            if r["status"] == "flagged":
                w.writerow({
                    "levelNumber": r["levelNumber"],
                    "id": r["id"],
                    "title": r["title"],
                    "category": r["category"],
                    "currentImage": r["image"],
                    "decision": "replace",
                    "replacementPath": "",
                    "notes": r["reasons"]
                })
    return path

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--threshold", type=int, default=35, help="Flag severity threshold")
    ap.add_argument("--category", default="", help="Only audit one category")
    args = ap.parse_args()

    OUT_DIR.mkdir(exist_ok=True)
    levels = read_levels()
    rows = []
    for lvl in levels:
        if args.category and lvl.get("category") != args.category:
            continue
        row = audit_level(lvl)
        row["status"] = "flagged" if int(row["severity"]) >= args.threshold else "ok"
        rows.append(row)

    report = OUT_DIR / "content_audit_report.csv"
    flagged = [r for r in rows if r["status"] == "flagged"]

    write_csv(rows, report)
    gallery(flagged, OUT_DIR / "review_gallery_flagged.html", f"PuzzleVerse Flagged Image Review ({len(flagged)})")
    gallery(rows, OUT_DIR / "review_gallery_all.html", f"PuzzleVerse Full Image Review ({len(rows)})")
    template = manual_template(rows)

    print("PIL available:", PIL_OK)
    print("Audited:", len(rows))
    print("Flagged:", len(flagged))
    print("Report:", report)
    print("Flagged gallery:", OUT_DIR / "review_gallery_flagged.html")
    print("All gallery:", OUT_DIR / "review_gallery_all.html")
    print("Manual override template:", template)

if __name__ == "__main__":
    main()
