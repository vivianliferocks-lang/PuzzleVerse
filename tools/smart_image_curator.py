"""
PuzzleVerse Smart Image Curator
--------------------------------
Replaces weak Commons-search images with stronger canonical images from
Wikipedia/Wikidata first, then Commons as a fallback.

Run from the PuzzleVerse repository root:
  python tools/smart_image_curator.py --ids pv-116-rani-lakshmibai --force
  python tools/smart_image_curator.py --category famous_people --force
  python tools/smart_image_curator.py --start 0 --limit 50 --force

It updates:
  - assets/puzzle-library/<category>/<level-id>/image.<ext>
  - attribution.md and curation.json in that folder
  - src/levels.js image/localImage/licenseStatus/credit fields
  - tools/curation_report.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import mimetypes
import os
import re
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote, unquote, urlparse

import requests

REPO_ROOT = Path.cwd()
LEVELS_JS = REPO_ROOT / "src" / "levels.js"
ASSET_ROOT = REPO_ROOT / "assets" / "puzzle-library"
REPORT_PATH = REPO_ROOT / "tools" / "curation_report.csv"

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "PuzzleVerseEducationalGame/0.2 (image curation; contact: developer)",
    "Accept": "application/json,text/html,*/*;q=0.8",
})

PEOPLE_NEGATIVE_WORDS = {
    "temple", "mandir", "mosque", "church", "cathedral", "shrine", "school", "college",
    "university", "hospital", "airport", "road", "street", "avenue", "park", "garden",
    "memorial", "museum", "house", "birthplace", "grave", "tomb", "mausoleum", "statue",
    "bust", "plaque", "sign", "stamp", "coin", "banknote", "building", "station", "fort",
    "palace", "hall", "auditorium", "award", "conference", "lecture", "center", "centre",
    "ferry", "ship", "boat", "bridge", "gate", "library", "institute", "foundation",
}

COMMON_BAD_WORDS = {
    "logo", "seal", "icon", "map", "diagram", "chart", "graph", "svg", "flag",
    "coat of arms", "qr", "barcode", "poster", "book cover", "album cover"
}

SAFE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


@dataclass
class Candidate:
    url: str
    title: str
    source: str
    credit: str = ""
    license_short: str = ""
    license_url: str = ""
    description: str = ""
    score: float = 0.0
    warning: str = ""


def request_json(url: str, params: Dict[str, Any], retries: int = 3) -> Dict[str, Any]:
    last_err: Optional[Exception] = None
    for attempt in range(retries):
        try:
            r = SESSION.get(url, params=params, timeout=30)
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            last_err = exc
            time.sleep(1.0 + attempt)
    raise RuntimeError(f"Request failed: {url} {params} -> {last_err}")


def extract_js_array(text: str, var_name: str) -> Tuple[List[Dict[str, Any]], int, int]:
    idx = text.find(var_name)
    if idx < 0:
        raise ValueError(f"Could not find {var_name} in src/levels.js")
    start = text.find("[", idx)
    if start < 0:
        raise ValueError(f"Could not find array start for {var_name}")
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    array_text = text[start:end]
                    return json.loads(array_text), start, end
    raise ValueError(f"Could not find array end for {var_name}")


def load_levels() -> Tuple[str, List[Dict[str, Any]], int, int]:
    text = LEVELS_JS.read_text(encoding="utf-8")
    levels, start, end = extract_js_array(text, "PUZZLEVERSE_LEVELS")
    return text, levels, start, end


def save_levels(original_text: str, levels: List[Dict[str, Any]], start: int, end: int) -> None:
    backup = LEVELS_JS.with_suffix(".js.bak")
    if not backup.exists():
        shutil.copy2(LEVELS_JS, backup)
    new_array = json.dumps(levels, ensure_ascii=False, indent=2)
    LEVELS_JS.write_text(original_text[:start] + new_array + original_text[end:], encoding="utf-8")


def clean_tokens(title: str) -> List[str]:
    ignore = {"of", "the", "a", "an", "and", "jr", "ii", "iii", "iv", "v", "king", "queen", "saint", "st"}
    return [t.lower() for t in re.findall(r"[A-Za-z0-9]+", title) if len(t) > 2 and t.lower() not in ignore]


def is_person_category(level: Dict[str, Any]) -> bool:
    return (level.get("category") or "").lower() == "famous_people" or "people" in (level.get("theme") or "").lower()


def commons_file_info(file_title: str) -> Optional[Candidate]:
    if not file_title.startswith("File:"):
        file_title = "File:" + file_title
    data = request_json("https://commons.wikimedia.org/w/api.php", {
        "action": "query",
        "format": "json",
        "titles": file_title,
        "prop": "imageinfo",
        "iiprop": "url|extmetadata|mime|size",
    })
    pages = data.get("query", {}).get("pages", {})
    for page in pages.values():
        infos = page.get("imageinfo") or []
        if not infos:
            continue
        info = infos[0]
        url = info.get("url")
        mime = (info.get("mime") or "").lower()
        if not url or not mime.startswith("image/"):
            continue
        meta = info.get("extmetadata") or {}
        def meta_val(k: str) -> str:
            v = meta.get(k, {}).get("value", "")
            return re.sub(r"<[^>]+>", "", v).strip()
        return Candidate(
            url=url,
            title=page.get("title", file_title),
            source="commons-file-info",
            credit=meta_val("Artist") or meta_val("Credit") or "Wikimedia Commons contributor",
            license_short=meta_val("LicenseShortName") or meta_val("UsageTerms"),
            license_url=meta_val("LicenseUrl"),
            description=meta_val("ImageDescription") or meta_val("ObjectName"),
        )
    return None


def wikipedia_candidates(title: str) -> Tuple[List[Candidate], Optional[str], str]:
    candidates: List[Candidate] = []
    wikidata_id: Optional[str] = None
    canonical_title = title
    data = request_json("https://en.wikipedia.org/w/api.php", {
        "action": "query",
        "format": "json",
        "redirects": 1,
        "titles": title,
        "prop": "pageimages|pageprops",
        "piprop": "original|thumbnail",
        "pithumbsize": 1600,
    })
    pages = data.get("query", {}).get("pages", {})
    for page in pages.values():
        if "missing" in page:
            continue
        canonical_title = page.get("title", title)
        props = page.get("pageprops") or {}
        wikidata_id = props.get("wikibase_item") or wikidata_id
        original = (page.get("original") or {}).get("source")
        thumb = (page.get("thumbnail") or {}).get("source")
        src = original or thumb
        if src:
            candidates.append(Candidate(url=src, title=canonical_title, source="wikipedia-pageimage"))
    if wikidata_id:
        try:
            claims = request_json("https://www.wikidata.org/w/api.php", {
                "action": "wbgetclaims",
                "format": "json",
                "entity": wikidata_id,
                "property": "P18",
            })
            for claim in claims.get("claims", {}).get("P18", [])[:3]:
                filename = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
                if filename:
                    c = commons_file_info(filename)
                    if c:
                        c.source = "wikidata-P18"
                        candidates.insert(0, c)
        except Exception as exc:
            print(f"Warning: Wikidata P18 lookup failed for {title}: {exc}")
    return candidates, wikidata_id, canonical_title


def commons_search_candidates(title: str, limit: int = 12) -> List[Candidate]:
    # Use exact title first, then normal title search. Commons search often returns memorials/statues,
    # so scoring will decide if anything is usable.
    queries = [f'intitle:"{title}"', f'"{title}"', title]
    seen = set()
    out: List[Candidate] = []
    for q in queries:
        data = request_json("https://commons.wikimedia.org/w/api.php", {
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrnamespace": 6,
            "gsrsearch": q,
            "gsrlimit": limit,
            "prop": "imageinfo",
            "iiprop": "url|extmetadata|mime|size",
        })
        pages = data.get("query", {}).get("pages", {})
        for page in pages.values():
            ptitle = page.get("title", "")
            if ptitle in seen:
                continue
            seen.add(ptitle)
            infos = page.get("imageinfo") or []
            if not infos:
                continue
            info = infos[0]
            mime = (info.get("mime") or "").lower()
            url = info.get("url")
            if not url or not mime.startswith("image/"):
                continue
            meta = info.get("extmetadata") or {}
            def meta_val(k: str) -> str:
                v = meta.get(k, {}).get("value", "")
                return re.sub(r"<[^>]+>", "", v).strip()
            out.append(Candidate(
                url=url,
                title=ptitle,
                source="commons-search",
                credit=meta_val("Artist") or meta_val("Credit") or "Wikimedia Commons contributor",
                license_short=meta_val("LicenseShortName") or meta_val("UsageTerms"),
                license_url=meta_val("LicenseUrl"),
                description=meta_val("ImageDescription") or meta_val("ObjectName"),
            ))
        if out:
            break
    return out


def score_candidate(level: Dict[str, Any], cand: Candidate) -> Candidate:
    title = level.get("title", "")
    tokens = clean_tokens(title)
    hay = " ".join([cand.title, cand.description, cand.credit, cand.url]).lower()
    score = 0.0

    if cand.source == "wikidata-P18":
        score += 90
    elif cand.source == "wikipedia-pageimage":
        score += 80
    elif cand.source == "commons-search":
        score += 35

    matched = sum(1 for t in tokens if t in hay)
    score += matched * 12
    if tokens and matched == len(tokens):
        score += 30
    elif tokens and matched == 0:
        score -= 35

    ext = Path(urlparse(cand.url).path).suffix.lower()
    if ext in {".jpg", ".jpeg"}:
        score += 6
    elif ext == ".png":
        score += 3
    elif ext == ".svg":
        score -= 35

    hay_words = set(re.findall(r"[a-z]+", hay))
    common_bad = COMMON_BAD_WORDS.intersection(hay)
    if common_bad:
        score -= 35
        cand.warning += f"common-bad:{','.join(sorted(common_bad))};"

    if is_person_category(level):
        neg = PEOPLE_NEGATIVE_WORDS.intersection(hay_words)
        # A P18/pageimage can sometimes be a bust/painting when no photo exists. Penalize but do not always reject.
        if neg:
            score -= 12 * len(neg)
            cand.warning += f"people-negative:{','.join(sorted(neg))};"
        # Strong preference for portrait/painting/photo keywords for historical people.
        if any(w in hay_words for w in ["portrait", "painting", "photograph", "photo", "image", "engraving"]):
            score += 18

    cand.score = score
    return cand


def choose_candidate(level: Dict[str, Any]) -> Optional[Candidate]:
    title = level.get("title", "").strip()
    candidates, wikidata_id, canonical_title = wikipedia_candidates(title)
    # If title search finds a redirect pageimage/P18, this is usually strongest.
    if not candidates:
        candidates.extend(commons_search_candidates(title))
    else:
        # Add Commons candidates as lower-priority fallback in case P18/page image is SVG/logo/etc.
        try:
            candidates.extend(commons_search_candidates(title, limit=8))
        except Exception:
            pass
    if not candidates:
        return None
    scored = [score_candidate(level, c) for c in candidates]
    scored.sort(key=lambda c: c.score, reverse=True)
    best = scored[0]
    # Very low score means likely bad match. Keep existing and report.
    if best.score < 40:
        best.warning += "low-confidence;"
    return best


def url_extension(url: str, content_type: str = "") -> str:
    parsed_ext = Path(unquote(urlparse(url).path)).suffix.lower()
    if parsed_ext in SAFE_EXTENSIONS:
        return ".jpg" if parsed_ext == ".jpeg" else parsed_ext
    guess = mimetypes.guess_extension(content_type.split(";")[0].strip()) if content_type else None
    if guess and guess.lower() in SAFE_EXTENSIONS:
        return ".jpg" if guess.lower() == ".jpeg" else guess.lower()
    return ".jpg"


def download_image(cand: Candidate, dest_dir: Path, force: bool) -> Optional[Path]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    for existing in dest_dir.glob("image.*"):
        if existing.suffix.lower() in SAFE_EXTENSIONS and not force:
            return existing
    r = SESSION.get(cand.url, timeout=60, stream=True, headers={"Referer": "https://commons.wikimedia.org/"})
    if r.status_code == 403:
        # fallback through Special:Redirect/file where possible
        filename = Path(unquote(urlparse(cand.url).path)).name
        if filename:
            redirect_url = f"https://commons.wikimedia.org/wiki/Special:Redirect/file/{quote(filename)}"
            r = SESSION.get(redirect_url, timeout=60, stream=True, headers={"Referer": "https://commons.wikimedia.org/"})
    r.raise_for_status()
    content_type = r.headers.get("Content-Type", "")
    ext = url_extension(cand.url, content_type)
    if not content_type.lower().startswith("image/") and ext not in SAFE_EXTENSIONS:
        raise RuntimeError(f"Not an image response: {content_type}")
    for existing in dest_dir.glob("image.*"):
        if existing.suffix.lower() in SAFE_EXTENSIONS:
            existing.unlink(missing_ok=True)
    dest = dest_dir / f"image{ext}"
    with open(dest, "wb") as f:
        for chunk in r.iter_content(chunk_size=1024 * 64):
            if chunk:
                f.write(chunk)
    return dest


def attribution_text(level: Dict[str, Any], cand: Candidate) -> str:
    return f"""# Attribution

Puzzle: {level.get('title')}
Level ID: {level.get('id')}

Source: {cand.source}
File/title: {cand.title}
Image URL: {cand.url}
Credit/artist: {cand.credit or 'Wikimedia Commons / Wikipedia contributor'}
License: {cand.license_short or 'Check source page'}
License URL: {cand.license_url or 'Check source page'}

Curation warning: {cand.warning or 'none'}
Curation score: {cand.score:.1f}

Review before commercial publishing. Replace if the image is not an accurate match.
"""


def select_levels(levels: List[Dict[str, Any]], args: argparse.Namespace) -> List[Dict[str, Any]]:
    selected = levels
    if args.ids:
        ids = {x.strip() for x in args.ids.split(",") if x.strip()}
        selected = [l for l in selected if l.get("id") in ids]
    if args.category:
        selected = [l for l in selected if (l.get("category") or "").lower() == args.category.lower()]
    if args.start is not None or args.limit is not None:
        start = args.start or 0
        end = start + (args.limit if args.limit is not None else len(selected))
        selected = selected[start:end]
    return selected


def main() -> int:
    parser = argparse.ArgumentParser(description="Smartly curate PuzzleVerse images using Wikipedia/Wikidata first.")
    parser.add_argument("--ids", help="Comma-separated level ids to repair, e.g. pv-116-rani-lakshmibai,pv-118-chanakya")
    parser.add_argument("--category", help="Category to repair, e.g. famous_people")
    parser.add_argument("--start", type=int, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--force", action="store_true", help="Overwrite existing image.* files")
    parser.add_argument("--dry-run", action="store_true", help="Do not write files")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between API calls/downloads")
    args = parser.parse_args()

    if not LEVELS_JS.exists():
        print("ERROR: Run this from the PuzzleVerse repository root. src/levels.js not found.")
        return 2

    original_text, levels, start_idx, end_idx = load_levels()
    selected = select_levels(levels, args)
    if not selected:
        print("No levels selected.")
        return 0

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    rows: List[Dict[str, Any]] = []
    updated = 0
    failed = 0

    id_to_level = {l.get("id"): l for l in levels}

    for n, level in enumerate(selected, 1):
        level_id = level.get("id")
        title = level.get("title", "")
        category = level.get("category", "uncategorized")
        dest_dir = ASSET_ROOT / category / level_id
        print(f"[{n}/{len(selected)}] Curating {level_id}: {title}")
        try:
            cand = choose_candidate(level)
            if not cand:
                print(f"  No candidate found.")
                failed += 1
                rows.append({"id": level_id, "title": title, "status": "no-candidate", "source": "", "score": "", "warning": "", "url": ""})
                continue
            print(f"  Candidate: {cand.source} score={cand.score:.1f} warning={cand.warning or 'none'}")
            print(f"  {cand.title}")
            if args.dry_run:
                rows.append({"id": level_id, "title": title, "status": "dry-run", "source": cand.source, "score": f"{cand.score:.1f}", "warning": cand.warning, "url": cand.url})
                continue
            img_path = download_image(cand, dest_dir, args.force)
            if not img_path:
                raise RuntimeError("Download did not produce an image path")
            rel_path = img_path.relative_to(REPO_ROOT).as_posix()
            target = id_to_level[level_id]
            target["image"] = rel_path
            target["localImage"] = rel_path
            target["sourceProvider"] = "Wikimedia Commons / Wikipedia"
            target["licenseStatus"] = "downloaded-needs-human-review" if cand.warning else "downloaded-needs-attribution-review"
            target["credit"] = (cand.credit or "Wikimedia Commons / Wikipedia contributor")[:300]
            target["curationSource"] = cand.source
            target["curationScore"] = round(cand.score, 1)
            target["curationWarning"] = cand.warning or ""
            (dest_dir / "attribution.md").write_text(attribution_text(level, cand), encoding="utf-8")
            (dest_dir / "curation.json").write_text(json.dumps(cand.__dict__, ensure_ascii=False, indent=2), encoding="utf-8")
            rows.append({"id": level_id, "title": title, "status": "updated", "source": cand.source, "score": f"{cand.score:.1f}", "warning": cand.warning, "url": cand.url})
            updated += 1
        except Exception as exc:
            print(f"  ERROR: {exc}")
            failed += 1
            rows.append({"id": level_id, "title": title, "status": f"error: {exc}", "source": "", "score": "", "warning": "", "url": ""})
        time.sleep(args.delay)

    if not args.dry_run:
        save_levels(original_text, levels, start_idx, end_idx)

    write_header = not REPORT_PATH.exists()
    with REPORT_PATH.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "title", "status", "source", "score", "warning", "url"])
        if write_header:
            writer.writeheader()
        writer.writerows(rows)

    print("\nDone.")
    print(f"Updated: {updated}")
    print(f"Failed: {failed}")
    print(f"Report: {REPORT_PATH}")
    if not args.dry_run:
        print("Test with: python -m http.server 8000")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
