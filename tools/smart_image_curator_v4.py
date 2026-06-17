#!/usr/bin/env python3
"""
PuzzleVerse Smart Image Curator V4
- Designed to avoid wrong famous-people images such as statues, plaques, temples, museums, graves, etc.
- Prefers portraits, photos, paintings, engravings, and historical depictions.
- Uses Wikimedia/Wikipedia/Wikidata APIs with caching, delay, and retry/backoff.
- Updates src/levels.js to point both image and localImage to the selected downloaded project image.

Run examples:
  python tools/smart_image_curator_v4.py --ids pv-116-rani-lakshmibai,pv-108-mahatma-gandhi,pv-110-abraham-lincoln --delay 8 --force
  python tools/smart_image_curator_v4.py --category famous_people --start 0 --limit 10 --delay 8 --force --placeholder-bad
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

ROOT = Path(__file__).resolve().parents[1]
LEVELS_PATH = ROOT / "src" / "levels.js"
CACHE_DIR = ROOT / "tools" / ".curation_cache_v4"
REPORT_PATH = ROOT / "tools" / "smart_curation_v4_report.csv"

USER_AGENT = "PuzzleVerseEducationalGame/0.4 (curation; contact: project-owner)"
TIMEOUT = 30

PLACEHOLDER = "assets/puzzle-placeholder.svg"

PERSON_GOOD = [
    "portrait", "painting", "depiction", "photo", "photograph", "engraving", "drawing", "miniature",
    "daguerreotype", "passport", "head", "face", "profile", "studio", "young", "old", "signed", "carte de visite",
    "oil on canvas", "watercolor", "watercolour", "sketch", "illustration"
]

PERSON_BAD = [
    "statue", "sculpture", "bust", "memorial", "monument", "plaque", "grave", "tomb", "mausoleum",
    "samadhi", "chhatri", "temple", "mosque", "church", "museum", "house", "home", "birthplace", "school",
    "college", "university", "airport", "station", "road", "street", "park", "garden", "tree", "ashram",
    "stamp", "coin", "currency", "banknote", "poster", "logo", "svg", "flag", "signature", "book", "letter",
    "manuscript", "medal", "award", "conference", "auditorium", "building", "residence", "mahal", "fort",
    "hospital", "foundation", "gate", "library", "hall", "commemoration", "mural", "graffiti", "sign", "program",
    "wiki loves monuments", "map", "diagram"
]

GENERIC_BAD = ["logo", "svg", "icon", "map", "diagram", "chart", "flag", "seal"]

COUNTRY_DISTRACTORS = [
    "India", "China", "Japan", "Egypt", "Greece", "Italy", "France", "United Kingdom", "United States",
    "Brazil", "Mexico", "Peru", "Australia", "South Africa", "Germany", "Russia", "Canada", "Spain"
]
OCCUPATION_DISTRACTORS = [
    "scientist", "mathematician", "writer", "political leader", "freedom fighter", "nurse", "astronaut",
    "artist", "inventor", "philosopher", "teacher", "social reformer", "engineer", "explorer"
]

# Optional hand-picked file-title overrides. Add more rows in tools/manual_image_overrides.json if needed.
# Format: { "pv-xxx-id": "File:Example.jpg" }
DEFAULT_MANUAL_OVERRIDES: Dict[str, str] = {
    # Leave empty by default so the script remains license/API driven. You can add exact Commons File: titles in tools/manual_image_overrides.json.
}


def safe_print(*args):
    print(*args, flush=True)


def cache_key(url: str, params: Dict[str, Any] | None = None) -> str:
    raw = url + "?" + urllib.parse.urlencode(params or {}, doseq=True)
    return re.sub(r"[^A-Za-z0-9_.-]", "_", raw)[:180] + ".json"


def request_json(url: str, params: Dict[str, Any] | None = None, delay: float = 1.0, max_retries: int = 5) -> Dict[str, Any]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = CACHE_DIR / cache_key(url, params)
    if key.exists():
        try:
            return json.loads(key.read_text(encoding="utf-8"))
        except Exception:
            pass

    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    wait = delay
    last_err = None
    for attempt in range(max_retries):
        if attempt > 0 or delay:
            time.sleep(wait)
        try:
            r = requests.get(url, params=params, headers=headers, timeout=TIMEOUT)
            if r.status_code == 429:
                safe_print(f"429 rate limit. Waiting {max(45, int(wait * 4))}s...")
                time.sleep(max(45, wait * 4))
                wait *= 2
                continue
            r.raise_for_status()
            data = r.json()
            key.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            return data
        except Exception as e:
            last_err = e
            wait *= 2
    raise RuntimeError(f"Request failed: {url} {params} -> {last_err}")


def download_url(url: str, dest: Path, delay: float = 1.0, max_retries: int = 5) -> bool:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        "Referer": "https://commons.wikimedia.org/",
    }
    wait = delay
    for attempt in range(max_retries):
        if attempt > 0 or delay:
            time.sleep(wait)
        try:
            r = requests.get(url, headers=headers, timeout=TIMEOUT, stream=True)
            if r.status_code == 429:
                safe_print(f"429 while downloading. Waiting {max(45, int(wait * 4))}s...")
                time.sleep(max(45, wait * 4))
                wait *= 2
                continue
            if r.status_code == 403:
                # Fallback through Special:FilePath, handled by caller through url sometimes.
                wait *= 2
                continue
            r.raise_for_status()
            ctype = r.headers.get("content-type", "")
            if "image" not in ctype:
                return False
            dest.parent.mkdir(parents=True, exist_ok=True)
            with dest.open("wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 64):
                    if chunk:
                        f.write(chunk)
            return dest.stat().st_size > 1024
        except Exception:
            wait *= 2
    return False


def load_levels_js() -> Tuple[List[Dict[str, Any]], str, str]:
    text = LEVELS_PATH.read_text(encoding="utf-8")
    patterns = [
        r"(window\.PUZZLEVERSE_LEVELS\s*=\s*)(\[.*?\])(\s*;)",
        r"(const\s+PUZZLEVERSE_LEVELS\s*=\s*)(\[.*?\])(\s*;)",
        r"(let\s+PUZZLEVERSE_LEVELS\s*=\s*)(\[.*?\])(\s*;)",
    ]
    for pat in patterns:
        m = re.search(pat, text, flags=re.S)
        if m:
            arr = json.loads(m.group(2))
            return arr, text, pat
    raise RuntimeError("Could not find PUZZLEVERSE_LEVELS array in src/levels.js")


def write_levels_js(levels: List[Dict[str, Any]], original_text: str, pattern: str, backup_suffix: str = ".bak_v4"):
    backup = LEVELS_PATH.with_suffix(LEVELS_PATH.suffix + backup_suffix)
    shutil.copy2(LEVELS_PATH, backup)
    new_arr = json.dumps(levels, ensure_ascii=False, indent=2)
    def repl(m):
        return m.group(1) + new_arr + m.group(3)
    new_text = re.sub(pattern, repl, original_text, count=1, flags=re.S)
    LEVELS_PATH.write_text(new_text, encoding="utf-8")
    safe_print(f"Updated {LEVELS_PATH}")
    safe_print(f"Backup saved as {backup}")


def slug_words(s: str) -> List[str]:
    return [w for w in re.split(r"[^a-z0-9]+", s.lower()) if w and len(w) > 1]


def normalize_file_title(title: str) -> str:
    title = title.replace("File:", "", 1)
    return title.strip()


def commons_imageinfo(file_title: str, delay: float) -> Optional[Dict[str, Any]]:
    title = file_title if file_title.startswith("File:") else "File:" + file_title
    data = request_json("https://commons.wikimedia.org/w/api.php", {
        "action": "query", "format": "json", "titles": title,
        "prop": "imageinfo", "iiprop": "url|mime|size|extmetadata|canonicaltitle"
    }, delay=delay)
    pages = data.get("query", {}).get("pages", {})
    for page in pages.values():
        infos = page.get("imageinfo") or []
        if infos:
            info = infos[0]
            info["title"] = page.get("title", title)
            return info
    return None


def metadata_text(info: Dict[str, Any]) -> str:
    parts = [info.get("title", ""), info.get("url", "")]
    ext = info.get("extmetadata") or {}
    for key in ["ObjectName", "ImageDescription", "Credit", "Artist", "Categories", "LicenseShortName"]:
        val = ext.get(key, {}).get("value") if isinstance(ext.get(key), dict) else None
        if val:
            parts.append(re.sub(r"<.*?>", " ", str(val)))
    return " ".join(parts).lower()


def candidate_warning(record: Dict[str, Any], info: Dict[str, Any]) -> str:
    txt = metadata_text(info)
    title = normalize_file_title(info.get("title", ""))
    ext = title.lower().split(".")[-1]
    if ext in {"svg", "gif"}:
        return "generic-suspicious:svg-or-gif"
    if record.get("category") == "famous_people":
        bad = [w for w in PERSON_BAD if w in txt]
        good = [w for w in PERSON_GOOD if w in txt]
        if bad and not good:
            return "person-suspicious:" + ",".join(bad[:4])
        if any(w in txt for w in ["statue", "sculpture", "bust", "plaque", "memorial", "temple", "tomb", "museum", "birthplace", "samadhi"]):
            # Even if source is P18, we prefer artwork/photo over statue/plaque.
            if not any(w in txt for w in ["portrait", "painting", "photograph", "photo", "engraving", "depiction", "drawing"]):
                return "person-suspicious:non-portrait-object"
    else:
        bad = [w for w in GENERIC_BAD if w in txt]
        if bad:
            return "generic-suspicious:" + ",".join(bad[:4])
    return "none"


def score_candidate(record: Dict[str, Any], info: Dict[str, Any], source: str) -> int:
    title = record.get("title", "")
    words = slug_words(title)
    txt = metadata_text(info)
    file_title = normalize_file_title(info.get("title", "")).lower()
    score = 0
    source_bonus = {"manual": 500, "wikidata-P18": 180, "wikipedia-pageimage": 120, "wikipedia-image-list": 90, "commons-search": 70}.get(source, 0)
    score += source_bonus
    for w in words:
        if w in txt:
            score += 18
        if w in file_title:
            score += 20
    if record.get("category") == "famous_people":
        for w in PERSON_GOOD:
            if w in txt:
                score += 65
        for w in PERSON_BAD:
            if w in txt:
                score -= 120
        if "portrait" not in txt and "painting" not in txt and "photograph" not in txt and "photo" not in txt and "depiction" not in txt and "engraving" not in txt:
            score -= 80
    else:
        for w in GENERIC_BAD:
            if w in txt:
                score -= 80
    width = int(info.get("width") or 0)
    height = int(info.get("height") or 0)
    if width >= 600 and height >= 400:
        score += 25
    if width < 200 or height < 200:
        score -= 100
    return score


def search_wikidata_entity(title: str, delay: float) -> Optional[str]:
    data = request_json("https://www.wikidata.org/w/api.php", {
        "action": "wbsearchentities", "format": "json", "language": "en", "search": title, "limit": 1
    }, delay=delay)
    results = data.get("search") or []
    return results[0].get("id") if results else None


def wikidata_p18_file(qid: str, delay: float) -> List[str]:
    data = request_json("https://www.wikidata.org/wiki/Special:EntityData/%s.json" % qid, {}, delay=delay)
    ent = data.get("entities", {}).get(qid, {})
    claims = ent.get("claims", {})
    out = []
    for c in claims.get("P18", []):
        val = c.get("mainsnak", {}).get("datavalue", {}).get("value")
        if val:
            out.append("File:" + val)
    return out


def wikipedia_page_images(title: str, delay: float) -> Tuple[List[str], List[str]]:
    page_images: List[str] = []
    image_list: List[str] = []
    try:
        data = request_json("https://en.wikipedia.org/w/api.php", {
            "action": "query", "format": "json", "redirects": 1, "titles": title,
            "prop": "pageimages|images", "piprop": "original|thumbnail", "pithumbsize": 1600, "imlimit": 30
        }, delay=delay)
        pages = data.get("query", {}).get("pages", {})
        for page in pages.values():
            # pageimage original URL doesn't give Commons title, use thumbnails only as fallback candidate by URL through Commons is harder.
            for im in page.get("images", []) or []:
                t = im.get("title")
                if t and t.startswith("File:"):
                    image_list.append(t)
    except Exception as e:
        safe_print(f"  wikipedia image-list error: {e}")
    return page_images, image_list


def commons_search_titles(record: Dict[str, Any], delay: float, limit: int = 12) -> List[str]:
    title = record.get("title", "")
    if record.get("category") == "famous_people":
        queries = [f'"{title}" portrait', f'"{title}" painting', f'"{title}" photograph', f'"{title}" depiction']
    else:
        queries = [f'"{title}"', title]
    results: List[str] = []
    for q in queries:
        try:
            data = request_json("https://commons.wikimedia.org/w/api.php", {
                "action": "query", "format": "json", "list": "search", "srnamespace": 6,
                "srlimit": limit, "srsearch": q
            }, delay=delay)
            for item in data.get("query", {}).get("search", []) or []:
                t = item.get("title")
                if t and t not in results:
                    results.append(t)
        except Exception as e:
            safe_print(f"  commons search error: {e}")
    return results


def choose_candidate(record: Dict[str, Any], delay: float, manual_overrides: Dict[str, str]) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    candidates: List[Dict[str, Any]] = []
    rid = record.get("id")
    title = record.get("title", "")

    def add(file_title: str, source: str):
        try:
            info = commons_imageinfo(file_title, delay=delay)
            if not info:
                return
            warning = candidate_warning(record, info)
            score = score_candidate(record, info, source)
            candidates.append({"source": source, "file": info.get("title", file_title), "info": info, "warning": warning, "score": score})
        except Exception as e:
            candidates.append({"source": source, "file": file_title, "info": {}, "warning": f"error:{e}", "score": -9999})

    if rid in manual_overrides:
        add(manual_overrides[rid], "manual")

    try:
        qid = search_wikidata_entity(title, delay=delay)
        if qid:
            for f in wikidata_p18_file(qid, delay=delay):
                add(f, "wikidata-P18")
    except Exception as e:
        safe_print(f"  wikidata lookup error: {e}")

    _, image_titles = wikipedia_page_images(title, delay=delay)
    for f in image_titles[:25]:
        add(f, "wikipedia-image-list")

    for f in commons_search_titles(record, delay=delay, limit=12):
        add(f, "commons-search")

    # Deduplicate by file title; keep best score.
    dedup: Dict[str, Dict[str, Any]] = {}
    for c in candidates:
        key = c["file"]
        if key not in dedup or c["score"] > dedup[key]["score"]:
            dedup[key] = c
    candidates = sorted(dedup.values(), key=lambda c: c["score"], reverse=True)

    # For famous people, reject suspicious object/place images and very low score.
    for c in candidates:
        if record.get("category") == "famous_people":
            if c["warning"] != "none":
                continue
            if c["score"] < 120:
                continue
        else:
            if c["warning"].startswith("generic-suspicious") and c["score"] < 120:
                continue
        return c, candidates
    return None, candidates


def record_folder(record: Dict[str, Any]) -> Path:
    # Use the existing folder from image/localImage if possible; otherwise category/id.
    for key in ["localImage", "image"]:
        val = record.get(key) or ""
        if "assets/puzzle-library" in val:
            return ROOT / Path(val).parent
    return ROOT / "assets" / "puzzle-library" / str(record.get("category", "misc")) / str(record.get("id"))


def extension_from_info(info: Dict[str, Any]) -> str:
    title = normalize_file_title(info.get("title", ""))
    ext = title.lower().rsplit(".", 1)[-1] if "." in title else "jpg"
    if ext not in {"jpg", "jpeg", "png", "webp"}:
        ext = "jpg"
    if ext == "jpeg":
        ext = "jpg"
    return ext


def project_rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def download_candidate(record: Dict[str, Any], cand: Dict[str, Any], delay: float, force: bool) -> Optional[str]:
    info = cand["info"]
    ext = extension_from_info(info)
    folder = record_folder(record)
    dest = folder / f"image.{ext}"
    if dest.exists() and not force:
        return project_rel(dest)
    url = info.get("url")
    ok = False
    if url:
        ok = download_url(url, dest, delay=delay)
    if not ok:
        file_title = normalize_file_title(info.get("title", cand.get("file", "")))
        fallback = "https://commons.wikimedia.org/wiki/Special:FilePath/" + urllib.parse.quote(file_title)
        ok = download_url(fallback, dest, delay=delay)
    if ok:
        # Remove older image.* files with different extension to avoid confusion.
        for old in folder.glob("image.*"):
            if old != dest:
                try:
                    old.unlink()
                except Exception:
                    pass
        return project_rel(dest)
    return None


def load_manual_overrides() -> Dict[str, str]:
    path = ROOT / "tools" / "manual_image_overrides.json"
    data = dict(DEFAULT_MANUAL_OVERRIDES)
    if path.exists():
        try:
            data.update(json.loads(path.read_text(encoding="utf-8")))
        except Exception as e:
            safe_print(f"Could not read manual overrides: {e}")
    return data


def select_records(levels: List[Dict[str, Any]], args) -> List[Dict[str, Any]]:
    if args.ids:
        want = {x.strip() for x in args.ids.split(",") if x.strip()}
        return [r for r in levels if r.get("id") in want]
    records = levels
    if args.category:
        records = [r for r in records if r.get("category") == args.category]
    start = args.start or 0
    end = None if args.limit is None else start + args.limit
    return records[start:end]


def placeholder_for(record: Dict[str, Any]) -> str:
    # Prefer the record's per-folder placeholder if it exists, else global placeholder.
    folder = record_folder(record)
    p = folder / "placeholder.svg"
    if p.exists():
        return project_rel(p)
    return PLACEHOLDER


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", help="Comma-separated level IDs")
    ap.add_argument("--category", help="Category filter, e.g. famous_people")
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--delay", type=float, default=5.0)
    ap.add_argument("--force", action="store_true", help="Re-download and overwrite selected images")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--placeholder-bad", action="store_true", help="For famous_people with no acceptable image, replace image with placeholder to avoid wrong statue/place images")
    args = ap.parse_args()

    levels, text, pattern = load_levels_js()
    records = select_records(levels, args)
    manual = load_manual_overrides()

    safe_print(f"Selected records: {len(records)}")
    report_rows = []
    updated = 0
    manual_review = 0
    failed = 0

    by_id = {r.get("id"): r for r in levels}
    for idx, rec in enumerate(records, 1):
        rid = rec.get("id")
        safe_print(f"[{idx}/{len(records)}] Curating {rid}: {rec.get('title')}")
        chosen, cands = choose_candidate(rec, delay=args.delay, manual_overrides=manual)
        for c in cands[:5]:
            safe_print(f"  candidate {c['source']} score={c['score']} warning={c['warning']} file={c['file']}")
        if not chosen:
            manual_review += 1
            safe_print("  => needs manual review")
            if args.placeholder_bad and rec.get("category") == "famous_people":
                rec["image"] = placeholder_for(rec)
                rec["localImage"] = placeholder_for(rec)
                rec["licenseStatus"] = "needs-manual-image-review"
                rec["credit"] = "Image removed because no confident portrait/artwork was found"
                updated += 1
            report_rows.append({"id": rid, "title": rec.get("title"), "status": "needs-manual-review", "chosen_file": "", "score": "", "warning": "", "candidates": " | ".join([f"{c['file']} ({c['score']}, {c['warning']})" for c in cands[:8]])})
            continue
        if args.dry_run:
            safe_print(f"  => would update to {chosen['file']}")
            report_rows.append({"id": rid, "title": rec.get("title"), "status": "dry-run", "chosen_file": chosen["file"], "score": chosen["score"], "warning": chosen["warning"], "candidates": ""})
            continue
        rel = download_candidate(rec, chosen, delay=args.delay, force=args.force)
        if not rel:
            failed += 1
            safe_print("  => failed download")
            report_rows.append({"id": rid, "title": rec.get("title"), "status": "download-failed", "chosen_file": chosen["file"], "score": chosen["score"], "warning": chosen["warning"], "candidates": ""})
            continue
        rec["image"] = rel
        rec["localImage"] = rel
        rec["sourceProvider"] = "Wikimedia Commons"
        rec["sourceFile"] = chosen["file"]
        rec["licenseStatus"] = "downloaded-needs-human-review"
        rec["credit"] = extract_credit(chosen["info"])
        updated += 1
        safe_print(f"  => updated {rel}")
        report_rows.append({"id": rid, "title": rec.get("title"), "status": "updated", "chosen_file": chosen["file"], "score": chosen["score"], "warning": chosen["warning"], "candidates": ""})

    if not args.dry_run:
        write_levels_js(levels, text, pattern)
    write_report(report_rows)
    safe_print("\nDone.")
    safe_print(f"Updated: {updated}")
    safe_print(f"Needs manual review: {manual_review}")
    safe_print(f"Failed/errors: {failed}")
    safe_print(f"Report: {REPORT_PATH}")
    safe_print("Test with: python -m http.server 8000")


def extract_credit(info: Dict[str, Any]) -> str:
    ext = info.get("extmetadata") or {}
    artist = ""
    lic = ""
    credit = ""
    if isinstance(ext.get("Artist"), dict):
        artist = re.sub(r"<.*?>", " ", ext["Artist"].get("value", "")).strip()
    if isinstance(ext.get("LicenseShortName"), dict):
        lic = ext["LicenseShortName"].get("value", "")
    if isinstance(ext.get("Credit"), dict):
        credit = re.sub(r"<.*?>", " ", ext["Credit"].get("value", "")).strip()
    parts = [p for p in [artist, credit, lic] if p]
    return " | ".join(parts)[:300] if parts else "Wikimedia Commons contributor; verify attribution before publishing"


def write_report(rows: List[Dict[str, Any]]):
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with REPORT_PATH.open("w", newline="", encoding="utf-8") as f:
        fields = ["id", "title", "status", "chosen_file", "score", "warning", "candidates"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)


if __name__ == "__main__":
    main()
