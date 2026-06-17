#!/usr/bin/env python3
"""
PuzzleVerse Smart Image Curator V3

Purpose:
- Replaces broad/wrong image matches with better Wikimedia/Wikipedia/Wikidata images.
- Handles 429 rate limits with retry + delay.
- Prefers portraits/paintings for famous_people.
- Rejects obvious wrong person images like temples, birthplaces, museums, houses, memorials.
- Updates src/levels.js so BOTH "image" and "localImage" point to the downloaded project image.

Run from repo root:
  python tools/smart_image_curator_v3.py --ids pv-116-rani-lakshmibai --force
  python tools/smart_image_curator_v3.py --category famous_people --delay 4 --force
"""

import argparse
import json
import mimetypes
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

import requests

ROOT = Path.cwd()
LEVELS_PATH = ROOT / "src" / "levels.js"
CACHE_PATH = ROOT / "tools" / "image_api_cache.json"
REPORT_PATH = ROOT / "tools" / "smart_curation_v3_report.csv"

USER_AGENT = "PuzzleVerseEducationalImageCurator/3.0 (educational game image curation; contact: project-owner)"

BAD_PERSON_TERMS = {
    "birth place", "birthplace", "museum", "memorial", "house", "home", "school",
    "college", "university", "institute", "academy", "hospital", "temple", "church",
    "mosque", "tomb", "grave", "cemetery", "airport", "bridge", "road", "street",
    "statue of", "monument", "plaque", "stamp", "coin", "banknote", "signature",
    "room", "building", "office", "park", "garden", "samadhi", "mausoleum",
    "ashram", "mandir", "palace", "fort", "castle", "library"
}

GOOD_PERSON_TERMS = {
    "portrait", "photo", "photograph", "painting", "depiction", "image", "head",
    "profile", "face", "bust", "sketch", "engraving", "drawing", "self-portrait"
}

BAD_GENERIC_TERMS = {"logo", "map", "diagram only", "qr", "icon", "seal"}

def load_cache():
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def save_cache(cache):
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")

CACHE = load_cache()
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json,text/html,*/*"})

def cached_get_json(url, params=None, delay=2.5, retries=6):
    key = url + "?" + json.dumps(params or {}, sort_keys=True, ensure_ascii=False)
    if key in CACHE:
        return CACHE[key]
    wait = delay
    for attempt in range(retries):
        try:
            r = SESSION.get(url, params=params, timeout=30)
            if r.status_code == 429:
                retry_after = r.headers.get("Retry-After")
                sleep_for = int(retry_after) if retry_after and retry_after.isdigit() else wait
                print(f"429 rate limit. Waiting {sleep_for}s...")
                time.sleep(sleep_for)
                wait = min(wait * 2, 90)
                continue
            r.raise_for_status()
            data = r.json()
            CACHE[key] = data
            save_cache(CACHE)
            time.sleep(delay)
            return data
        except Exception as e:
            if attempt == retries - 1:
                raise
            print(f"Request failed, retrying in {int(wait)}s: {e}")
            time.sleep(wait)
            wait = min(wait * 2, 90)
    raise RuntimeError("Request failed after retries")

def download_url(url, target, delay=1.0, retries=5):
    headers = {
        "User-Agent": USER_AGENT,
        "Referer": "https://commons.wikimedia.org/"
    }
    wait = delay
    for attempt in range(retries):
        try:
            with SESSION.get(url, headers=headers, timeout=60, stream=True) as r:
                if r.status_code == 429:
                    retry_after = r.headers.get("Retry-After")
                    sleep_for = int(retry_after) if retry_after and retry_after.isdigit() else wait * 5
                    print(f"429 while downloading. Waiting {int(sleep_for)}s...")
                    time.sleep(sleep_for)
                    wait = min(wait * 2, 60)
                    continue
                r.raise_for_status()
                target.parent.mkdir(parents=True, exist_ok=True)
                with open(target, "wb") as f:
                    for chunk in r.iter_content(1024 * 128):
                        if chunk:
                            f.write(chunk)
                time.sleep(delay)
                return True
        except Exception as e:
            if attempt == retries - 1:
                raise
            print(f"Download failed, retrying in {int(wait)}s: {e}")
            time.sleep(wait)
            wait = min(wait * 2, 60)
    return False

def extract_array_text(js):
    marker = "PUZZLEVERSE_LEVELS"
    idx = js.find(marker)
    if idx < 0:
        raise ValueError("Cannot find PUZZLEVERSE_LEVELS in src/levels.js")
    start = js.find("[", idx)
    if start < 0:
        raise ValueError("Cannot find levels array start")
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(js)):
        ch = js[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    return js[start:i+1], start, i+1
    raise ValueError("Cannot find levels array end")

def load_levels():
    js = LEVELS_PATH.read_text(encoding="utf-8")
    arr_text, start, end = extract_array_text(js)
    # The generated levels file uses JSON-compatible object syntax.
    levels = json.loads(arr_text)
    return js, levels, start, end

def save_levels(js, levels, start, end):
    new_arr = json.dumps(levels, ensure_ascii=False, indent=2)
    backup = LEVELS_PATH.with_suffix(".js.bak_v3")
    backup.write_text(js, encoding="utf-8")
    LEVELS_PATH.write_text(js[:start] + new_arr + js[end:], encoding="utf-8")
    print(f"Updated {LEVELS_PATH}")
    print(f"Backup saved as {backup}")

def slug_words(title):
    return [w.lower() for w in re.findall(r"[a-zA-Z0-9]+", title) if len(w) > 1]

def candidate_warning(record, file_title, desc=""):
    low = (file_title + " " + desc).lower().replace("_", " ")
    warnings = []
    if record.get("category") == "famous_people":
        bad = [t for t in BAD_PERSON_TERMS if t in low]
        if bad:
            warnings.append("person-suspicious:" + ",".join(sorted(bad)[:4]))
        # Modern people should not use stamps/plaques as primary if better options exist.
    generic = [t for t in BAD_GENERIC_TERMS if t in low]
    if generic:
        warnings.append("generic-suspicious:" + ",".join(generic))
    return ";".join(warnings) or "none"

def score_candidate(record, cand):
    title = record["title"]
    words = slug_words(title)
    text = (cand.get("file_title","") + " " + cand.get("desc","") + " " + cand.get("source","")).lower().replace("_", " ")
    score = cand.get("base", 0)
    for w in words:
        if w in text:
            score += 12
    if record.get("category") == "famous_people":
        for good in GOOD_PERSON_TERMS:
            if good in text:
                score += 22
        for bad in BAD_PERSON_TERMS:
            if bad in text:
                score -= 80
        if "statue" in text or "bust" in text:
            score -= 15  # acceptable fallback, but prefer real portrait/painting
        if "stamp" in text or "plaque" in text:
            score -= 90
    else:
        for bad in BAD_GENERIC_TERMS:
            if bad in text:
                score -= 60
    return score

def commons_file_info(file_title, delay):
    if not file_title.startswith("File:"):
        file_title = "File:" + file_title
    data = cached_get_json("https://commons.wikimedia.org/w/api.php", {
        "action": "query",
        "format": "json",
        "titles": file_title,
        "prop": "imageinfo",
        "iiprop": "url|extmetadata|mime|size"
    }, delay=delay)
    pages = data.get("query", {}).get("pages", {})
    for p in pages.values():
        infos = p.get("imageinfo") or []
        if infos:
            info = infos[0]
            meta = info.get("extmetadata", {})
            desc = " ".join(str((meta.get(k) or {}).get("value", "")) for k in ["ObjectName", "ImageDescription", "Credit", "Artist"])
            return {
                "file_title": p.get("title", file_title),
                "url": info.get("url"),
                "mime": info.get("mime", ""),
                "desc": re.sub("<.*?>", " ", desc),
                "credit": re.sub("<.*?>", " ", str((meta.get("Credit") or {}).get("value", ""))).strip(),
                "artist": re.sub("<.*?>", " ", str((meta.get("Artist") or {}).get("value", ""))).strip(),
                "license": str((meta.get("LicenseShortName") or {}).get("value", "")).strip()
            }
    return None

def wikidata_p18_candidates(title, delay):
    out = []
    data = cached_get_json("https://www.wikidata.org/w/api.php", {
        "action": "wbsearchentities",
        "format": "json",
        "language": "en",
        "search": title,
        "limit": 3
    }, delay=delay)
    for item in data.get("search", []):
        qid = item.get("id")
        if not qid:
            continue
        ent = cached_get_json("https://www.wikidata.org/wiki/Special:EntityData/%s.json" % qid, delay=delay)
        entity = ent.get("entities", {}).get(qid, {})
        claims = entity.get("claims", {}).get("P18", [])
        for claim in claims[:2]:
            try:
                file_name = claim["mainsnak"]["datavalue"]["value"]
                info = commons_file_info(file_name, delay)
                if info and info.get("url"):
                    info["source"] = "wikidata-P18"
                    info["base"] = 170
                    out.append(info)
            except Exception:
                continue
    return out

def wikipedia_page_candidates(title, delay):
    out = []
    data = cached_get_json("https://en.wikipedia.org/w/api.php", {
        "action": "query",
        "format": "json",
        "redirects": 1,
        "titles": title,
        "prop": "pageimages|images",
        "piprop": "original|thumbnail|name",
        "pithumbsize": 1600,
        "imlimit": 10
    }, delay=delay)
    pages = data.get("query", {}).get("pages", {})
    for p in pages.values():
        # Page image is useful but sometimes not ideal. It becomes one candidate.
        pi = p.get("pageimage")
        if pi:
            info = commons_file_info(pi, delay)
            if info and info.get("url"):
                info["source"] = "wikipedia-pageimage"
                info["base"] = 145
                out.append(info)
        # Also check image list for title/name overlap.
        for img in (p.get("images") or [])[:10]:
            ft = img.get("title")
            if not ft:
                continue
            info = commons_file_info(ft, delay)
            if info and info.get("url"):
                info["source"] = "wikipedia-image-list"
                info["base"] = 110
                out.append(info)
    return out

def commons_search_candidates(record, delay):
    title = record["title"]
    queries = []
    if record.get("category") == "famous_people":
        queries = [
            f'intitle:"{title}" portrait',
            f'"{title}" portrait',
            f'"{title}" painting',
            f'"{title}" photograph',
            f'"{title}"'
        ]
    else:
        queries = [f'intitle:"{title}"', f'"{title}"', title]
    out = []
    for q in queries:
        data = cached_get_json("https://commons.wikimedia.org/w/api.php", {
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrsearch": q,
            "gsrnamespace": 6,
            "gsrlimit": 8,
            "prop": "imageinfo",
            "iiprop": "url|extmetadata|mime|size"
        }, delay=delay)
        pages = data.get("query", {}).get("pages", {})
        for p in pages.values():
            infos = p.get("imageinfo") or []
            if not infos:
                continue
            info = infos[0]
            meta = info.get("extmetadata", {})
            desc = " ".join(str((meta.get(k) or {}).get("value", "")) for k in ["ObjectName", "ImageDescription", "Credit", "Artist"])
            out.append({
                "file_title": p.get("title", ""),
                "url": info.get("url"),
                "mime": info.get("mime", ""),
                "desc": re.sub("<.*?>", " ", desc),
                "credit": re.sub("<.*?>", " ", str((meta.get("Credit") or {}).get("value", ""))).strip(),
                "artist": re.sub("<.*?>", " ", str((meta.get("Artist") or {}).get("value", ""))).strip(),
                "license": str((meta.get("LicenseShortName") or {}).get("value", "")).strip(),
                "source": "commons-search",
                "base": 90
            })
        if out:
            break
    return out

def unique_candidates(cands):
    seen = set()
    out = []
    for c in cands:
        key = c.get("url") or c.get("file_title")
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out

def target_for_record(record, url_or_mime):
    parent = None
    for key in ["localImage", "image"]:
        val = record.get(key)
        if val:
            parent = Path(val).parent
            break
    if parent is None:
        parent = Path("assets") / "puzzle-library" / record.get("category", "misc") / record["id"]
    ext = ".jpg"
    low = (url_or_mime or "").lower()
    if "png" in low:
        ext = ".png"
    elif "webp" in low:
        ext = ".webp"
    elif "jpeg" in low or "jpg" in low:
        ext = ".jpg"
    return ROOT / parent / ("image" + ext), str(parent / ("image" + ext)).replace("\\", "/")

def curate_one(record, force=False, delay=3.5, strict_people=True):
    current = record.get("image", "")
    if current and "placeholder.svg" not in current and not force:
        return "skipped-existing", None, None

    print(f"Curating {record.get('id')}: {record.get('title')}")
    cands = []
    # Order matters: exact structured sources first.
    try:
        cands += wikidata_p18_candidates(record["title"], delay)
    except Exception as e:
        print(f"  Wikidata warning: {e}")
    try:
        cands += wikipedia_page_candidates(record["title"], delay)
    except Exception as e:
        print(f"  Wikipedia warning: {e}")
    try:
        cands += commons_search_candidates(record, delay)
    except Exception as e:
        print(f"  Commons warning: {e}")

    cands = unique_candidates(cands)
    for c in cands:
        c["warning"] = candidate_warning(record, c.get("file_title",""), c.get("desc",""))
        c["score"] = score_candidate(record, c)

    cands.sort(key=lambda x: x.get("score", 0), reverse=True)
    if not cands:
        return "failed-no-candidate", None, None

    # For people, don't accept a clearly suspicious low-quality result unless forced by user reviewing it later.
    chosen = None
    for c in cands:
        if record.get("category") == "famous_people" and strict_people:
            if c["score"] < 85 or "person-suspicious" in c["warning"]:
                continue
        chosen = c
        break
    if chosen is None:
        chosen = cands[0]
        return "needs-manual-review", chosen, cands[:5]

    target, rel = target_for_record(record, chosen.get("mime") or chosen.get("url"))
    download_url(chosen["url"], target, delay=1.0)
    record["image"] = rel
    record["localImage"] = rel
    record["licenseStatus"] = "smart-curated-v3-review-needed"
    credit_parts = [p for p in [chosen.get("artist"), chosen.get("credit"), chosen.get("license"), chosen.get("source"), chosen.get("file_title")] if p]
    record["credit"] = " | ".join(credit_parts)[:500]
    # Attribution file next to the image.
    attr = target.parent / "attribution.md"
    attr.write_text(
        f"# {record['title']}\n\n"
        f"- Source: {chosen.get('source')}\n"
        f"- File: {chosen.get('file_title')}\n"
        f"- URL: {chosen.get('url')}\n"
        f"- Artist: {chosen.get('artist')}\n"
        f"- Credit: {chosen.get('credit')}\n"
        f"- License: {chosen.get('license')}\n"
        f"- Warning: {chosen.get('warning')}\n",
        encoding="utf-8"
    )
    return "updated", chosen, cands[:5]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--category", help="Curate only one category, e.g. famous_people")
    ap.add_argument("--ids", help="Comma-separated level IDs to curate")
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--force", action="store_true", help="Replace existing images")
    ap.add_argument("--delay", type=float, default=3.5, help="Delay between API requests; increase if you see 429")
    ap.add_argument("--allow-suspicious-people", action="store_true", help="Allow low-confidence person results")
    args = ap.parse_args()

    js, levels, start, end = load_levels()
    wanted_ids = set(x.strip() for x in args.ids.split(",")) if args.ids else None
    selected = []
    for rec in levels:
        if wanted_ids and rec.get("id") not in wanted_ids:
            continue
        if args.category and rec.get("category") != args.category:
            continue
        selected.append(rec)
    if args.start:
        selected = selected[args.start:]
    if args.limit is not None:
        selected = selected[:args.limit]

    print(f"Selected records: {len(selected)}")
    rows = ["id,title,status,source,score,warning,file\n"]
    updated = 0
    manual = 0
    failed = 0

    for idx, rec in enumerate(selected, 1):
        print(f"[{idx}/{len(selected)}] {rec.get('id')} - {rec.get('title')}")
        try:
            status, chosen, top = curate_one(
                rec,
                force=args.force,
                delay=args.delay,
                strict_people=not args.allow_suspicious_people
            )
            if status == "updated":
                updated += 1
            elif status == "needs-manual-review":
                manual += 1
            elif status.startswith("failed"):
                failed += 1
            source = chosen.get("source","") if chosen else ""
            score = chosen.get("score","") if chosen else ""
            warning = chosen.get("warning","") if chosen else ""
            file_title = (chosen.get("file_title","") if chosen else "").replace('"','""')
            rows.append(f'"{rec.get("id")}","{rec.get("title")}","{status}","{source}","{score}","{warning}","{file_title}"\n')
            if top:
                for c in top[:3]:
                    print(f"  candidate {c.get('source')} score={c.get('score')} warning={c.get('warning')} file={c.get('file_title')}")
            print(f"  => {status}")
        except KeyboardInterrupt:
            print("Stopped by user.")
            break
        except Exception as e:
            failed += 1
            print(f"  ERROR: {e}")
            rows.append(f'"{rec.get("id")}","{rec.get("title")}","error","","","{str(e).replace(chr(34), chr(39))}",""\n')

    save_levels(js, levels, start, end)
    REPORT_PATH.write_text("".join(rows), encoding="utf-8")
    print("\nDone.")
    print(f"Updated: {updated}")
    print(f"Needs manual review: {manual}")
    print(f"Failed/errors: {failed}")
    print(f"Report: {REPORT_PATH}")
    print("Test with: python -m http.server 8000")

if __name__ == "__main__":
    main()
