#!/usr/bin/env python3
"""
PuzzleVerse V6 educational visual curator.
Use this for science/anatomy/diagram-heavy subjects where a simple photo is not enough.
It searches Wikimedia Commons with stronger educational query terms and prefers titles
containing diagram/anatomy/structure/cross-section terms.
"""
import argparse
import json
import re
import time
import urllib.parse
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
LEVELS = ROOT / "src" / "levels.js"
ASSETS = ROOT / "assets" / "puzzle-library"
UA = "PuzzleVerseEducationalCuration/1.0 (educational prototype; respectful low-volume requests)"

PRIORITY_QUERIES = {
    "pv-159-dna-double-helix": ["DNA double helix structure diagram", "DNA double helix model labelled", "DNA structure diagram"],
    "pv-160-cell-structure": ["animal cell structure diagram labelled", "cell anatomy diagram", "cell structure labelled"],
    "pv-161-human-skeleton": ["human skeleton anatomy diagram labelled", "human skeleton diagram", "skeletal system diagram"],
    "pv-162-heart-anatomy": ["human heart anatomy chambers diagram", "heart anatomy cross section labelled", "heart chambers diagram"],
    "pv-163-neuron": ["neuron structure diagram labelled", "nerve cell anatomy diagram", "neuron diagram"],
    "pv-164-photosynthesis": ["photosynthesis diagram", "photosynthesis process diagram labelled", "photosynthesis educational diagram"],
    "pv-165-water-cycle": ["water cycle diagram", "hydrologic cycle diagram", "water cycle labelled"],
    "pv-168-plate-tectonics": ["plate tectonics diagram", "tectonic plates diagram", "plate boundary diagram"],
}

PREFER = ["diagram", "anatomy", "structure", "label", "labelled", "labeled", "cross section", "cross-section", "schematic", "educational", "model", "chambers", "system"]
REJECT = ["logo", "icon", "stamp", "coin", "building", "museum", "memorial", "plaque", "statue", "grave", "tomb", "map only"]


def load_levels_text():
    return LEVELS.read_text(encoding="utf-8", errors="ignore")


def parse_levels(text):
    # Works with the current generated JS object-array format.
    records = []
    for block in re.finditer(r"\{\s*\"id\"\s*:\s*\"([^\"]+)\".*?\n\s*\}", text, re.S):
        b = block.group(0)
        id_ = block.group(1)
        title = re.search(r"\"title\"\s*:\s*\"([^\"]+)\"", b)
        category = re.search(r"\"category\"\s*:\s*\"([^\"]+)\"", b)
        records.append({"id": id_, "title": title.group(1) if title else id_, "category": category.group(1) if category else "", "block": b})
    return records


def request_json(url, params, delay):
    for attempt in range(4):
        r = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=30)
        if r.status_code == 429:
            wait = max(delay, 10) * (attempt + 1)
            print(f"429 rate limit. Waiting {wait}s...")
            time.sleep(wait)
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError("Too many 429 responses")


def commons_search(query, delay):
    data = request_json("https://commons.wikimedia.org/w/api.php", {
        "action": "query", "format": "json", "generator": "search", "gsrsearch": query,
        "gsrnamespace": 6, "gsrlimit": 12,
        "prop": "imageinfo", "iiprop": "url|mime|size|extmetadata", "iiurlwidth": 1600
    }, delay)
    pages = data.get("query", {}).get("pages", {})
    out = []
    for p in pages.values():
        title = p.get("title", "")
        ii = (p.get("imageinfo") or [{}])[0]
        url = ii.get("thumburl") or ii.get("url")
        mime = ii.get("mime", "")
        if not url or not mime.startswith("image/") or mime.endswith("svg+xml"):
            continue
        out.append({"title": title, "url": url, "mime": mime})
    return out


def score_candidate(title):
    low = urllib.parse.unquote(title).lower().replace("_", " ")
    if any(x in low for x in REJECT):
        return -999
    score = 0
    for term in PREFER:
        if term in low:
            score += 40
    # Avoid generic unrelated photos when looking for educational diagrams.
    if "diagram" not in low and "anatom" not in low and "structure" not in low and "label" not in low and "schematic" not in low:
        score -= 40
    return score


def best_candidate(title, id_, delay):
    queries = PRIORITY_QUERIES.get(id_, [f"{title} diagram", f"{title} anatomy", f"{title} structure labelled"])
    candidates = []
    for q in queries:
        print(f"  search: {q}")
        try:
            candidates.extend(commons_search(q, delay))
        except Exception as e:
            print(f"  search failed: {e}")
        time.sleep(delay)
    scored = sorted(((score_candidate(c["title"]), c) for c in candidates), key=lambda x: x[0], reverse=True)
    for score, cand in scored[:5]:
        print(f"  candidate score={score} title={cand['title']}")
    return scored[0][1] if scored and scored[0][0] > 0 else None


def id_to_folder(id_):
    hits = list(ASSETS.rglob(id_))
    if hits:
        return hits[0]
    # fallback: find folder that ends with id
    for p in ASSETS.rglob("*"):
        if p.is_dir() and p.name == id_:
            return p
    return None


def download(url, dest):
    r = requests.get(url, headers={"User-Agent": UA}, timeout=60)
    r.raise_for_status()
    dest.write_bytes(r.content)


def replace_level_image(text, id_, rel):
    # Replace image/localImage inside the matching object only.
    def repl(match):
        block = match.group(0)
        block = re.sub(r'"image"\s*:\s*"[^"]*"', f'"image": "{rel}"', block, count=1)
        if re.search(r'"localImage"\s*:', block):
            block = re.sub(r'"localImage"\s*:\s*"[^"]*"', f'"localImage": "{rel}"', block, count=1)
        else:
            block = block.replace(f'"image": "{rel}"', f'"image": "{rel}",\n    "localImage": "{rel}"', 1)
        return block
    pattern = re.compile(r"\{\s*\"id\"\s*:\s*\"" + re.escape(id_) + r"\".*?\n\s*\}", re.S)
    return pattern.sub(repl, text, count=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", help="Comma-separated level ids to curate")
    ap.add_argument("--delay", type=float, default=6.0)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    text = load_levels_text()
    levels = parse_levels(text)
    ids = set(args.ids.split(",")) if args.ids else set(PRIORITY_QUERIES)
    selected = [r for r in levels if r["id"] in ids]
    print(f"Selected records: {len(selected)}")
    updated = 0
    for rec in selected:
        print(f"Curating {rec['id']} - {rec['title']}")
        cand = best_candidate(rec["title"], rec["id"], args.delay)
        if not cand:
            print("  no strong educational candidate found")
            continue
        folder = id_to_folder(rec["id"])
        if not folder:
            print("  folder not found")
            continue
        ext = ".png" if "png" in cand["mime"] else ".jpg"
        dest = folder / f"image{ext}"
        download(cand["url"], dest)
        rel = str(dest.relative_to(ROOT)).replace("\\", "/")
        text = replace_level_image(text, rec["id"], rel)
        (folder / "attribution.md").write_text(f"# Attribution\n\nSelected educational visual: {cand['title']}\n\nSource URL: {cand['url']}\n\nReview before commercial release.\n", encoding="utf-8")
        print(f"  updated -> {rel}")
        updated += 1

    if updated:
        backup = LEVELS.with_suffix(".js.bak_v6_educational_visuals")
        backup.write_text(load_levels_text(), encoding="utf-8")
        LEVELS.write_text(text, encoding="utf-8")
    print(f"Done. Updated: {updated}")


if __name__ == "__main__":
    main()
