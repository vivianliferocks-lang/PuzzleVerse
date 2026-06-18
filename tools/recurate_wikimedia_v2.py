#!/usr/bin/env python3
"""
PuzzleVerse Wikimedia Recurator V2

Best-effort web replacement finder for selected levels.
Requires internet and requests.

Usage examples:
python tools/recurate_wikimedia_v2.py --ids pv-108-mahatma-gandhi,pv-116-rani-lakshmibai --apply --delay 6
python tools/recurate_wikimedia_v2.py --category science_discoveries --start 0 --limit 20 --apply --delay 8

It avoids some common bad keywords:
- famous_people: statue, plaque, memorial, building, etc.
- science_discoveries: prefers diagram/anatomy/structure/model/NASA style terms.
"""

import argparse
import json
import re
import shutil
import time
from pathlib import Path
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parents[1]
LEVELS = ROOT / "src" / "levels.js"
API = "https://commons.wikimedia.org/w/api.php"
UA = "PuzzleVerseEducationalPrototype/1.0 (local curation script; respectful rate limit)"

FAMOUS_BAD = ["statue","bust","memorial","plaque","grave","birthplace","house","museum","building","stamp","coin","banknote","signature","logo","tree","garden","street","airport","temple","samadhi"]
FAMOUS_GOOD = ["portrait","photo","photograph","painting","engraving","depiction","official"]
SCI_GOOD = ["diagram","anatomy","structure","schematic","labeled","labelled","cutaway","cross-section","model","illustration","nasa","telescope","spacecraft","rover"]
COMMON_BAD = ["logo","svg","icon","map symbol"]

def load_levels():
    text = LEVELS.read_text(encoding="utf-8")
    m = re.search(r"window\.PUZZLEVERSE_LEVELS\s*=\s*(\[[\s\S]*?\]);", text)
    if not m:
        raise SystemExit("Could not find levels array.")
    return text, m.start(1), m.end(1), json.loads(m.group(1))

def norm(s): return re.sub(r"[^a-z0-9]+"," ",str(s or "").lower()).strip()

def score_candidate(level, title, mime, width, height):
    cat = level.get("category","")
    q = norm(title)
    score = 0
    if mime and "image/" in mime: score += 20
    if width and height:
        mp = (width*height)/1_000_000
        score += min(50, mp*18)
    title_tokens = [t for t in norm(level.get("title","")).split() if len(t)>2]
    score += sum(18 for t in title_tokens if t in q)
    if cat == "famous_people":
        score += sum(35 for k in FAMOUS_GOOD if k in q)
        score -= sum(60 for k in FAMOUS_BAD if k in q)
        if width and height and width/height > 1.7:
            score -= 25
    elif cat == "science_discoveries":
        score += sum(30 for k in SCI_GOOD if k in q)
        score -= sum(50 for k in ["conference","building","portrait","person","plaque"] if k in q)
    score -= sum(55 for k in COMMON_BAD if k in q)
    return score

def commons_search(query, limit=12):
    params = {"action":"query","format":"json","generator":"search","gsrsearch":query,"gsrnamespace":6,"gsrlimit":limit,"prop":"imageinfo","iiprop":"url|mime|size|extmetadata","iiurlwidth":1400}
    r = requests.get(API, params=params, headers={"User-Agent":UA}, timeout=30)
    if r.status_code == 429:
        raise RuntimeError("429 rate limit")
    r.raise_for_status()
    pages = r.json().get("query",{}).get("pages",{})
    out = []
    for p in pages.values():
        ii = (p.get("imageinfo") or [{}])[0]
        out.append({
            "title": p.get("title",""),
            "url": ii.get("url") or ii.get("thumburl"),
            "mime": ii.get("mime",""),
            "width": ii.get("width") or 0,
            "height": ii.get("height") or 0,
        })
    return out

def queries_for(level):
    title = level.get("title","")
    cat = level.get("category","")
    if cat == "famous_people":
        return [f'{title} portrait', f'{title} photograph', f'{title} painting portrait']
    if cat == "science_discoveries":
        return [f'{title} diagram', f'{title} educational diagram', f'{title} anatomy structure illustration', title]
    return [title]

def download(url, dest):
    r = requests.get(url, headers={"User-Agent":UA}, timeout=60)
    if r.status_code == 429:
        raise RuntimeError("429 rate limit")
    r.raise_for_status()
    dest.write_bytes(r.content)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", default="")
    ap.add_argument("--category", default="")
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--delay", type=float, default=6)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    text, s, e, levels = load_levels()
    selected = levels
    if args.ids:
        ids = set(x.strip() for x in args.ids.split(",") if x.strip())
        selected = [l for l in levels if l.get("id") in ids]
    if args.category:
        selected = [l for l in selected if l.get("category") == args.category]
    selected = selected[args.start:args.start+args.limit]

    changed = 0
    for i, level in enumerate(selected, 1):
        print(f"[{i}/{len(selected)}] {level.get('id')} - {level.get('title')}")
        candidates = []
        for q in queries_for(level):
            try:
                time.sleep(args.delay)
                candidates.extend(commons_search(q))
            except Exception as ex:
                print(" search error:", ex)
        ranked = []
        seen = set()
        for c in candidates:
            if not c.get("url") or c["url"] in seen:
                continue
            seen.add(c["url"])
            sc = score_candidate(level, c["title"], c.get("mime"), int(c.get("width") or 0), int(c.get("height") or 0))
            ranked.append((sc, c))
        ranked.sort(key=lambda x: x[0], reverse=True)
        for sc, c in ranked[:5]:
            print(" candidate", round(sc,1), c["title"])
        if not ranked:
            continue
        best_score, best = ranked[0]
        if best_score < 45:
            print("  -> low score, needs manual review")
            continue
        if args.apply:
            current = level.get("localImage") or level.get("image")
            if not current:
                print("  -> no current path")
                continue
            dest = (ROOT / current).parent / "image.jpg"
            try:
                download(best["url"], dest)
                rel = dest.relative_to(ROOT).as_posix()
                level["image"] = rel
                level["localImage"] = rel
                level["sourceProvider"] = "Wikimedia Commons"
                level["sourceTitle"] = best["title"]
                level["licenseStatus"] = "recurated-needs-human-review"
                changed += 1
                print("  -> updated", rel)
            except Exception as ex:
                print("  download error:", ex)

    if args.apply and changed:
        backup = LEVELS.with_suffix(".js.bak_recurate_v2")
        shutil.copy2(LEVELS, backup)
        LEVELS.write_text(text[:s] + json.dumps(levels, ensure_ascii=False, indent=2) + text[e:], encoding="utf-8")
        print("Changed:", changed)
        print("Backup:", backup)
    else:
        print("No levels changed. Use --apply after checking candidates.")

if __name__ == "__main__":
    main()
