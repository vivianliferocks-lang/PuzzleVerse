#!/usr/bin/env python3
"""
PuzzleVerse open-image importer V2.

Fixes Wikimedia 403 direct-download issues by using a stronger User-Agent,
Referer, thumbnail URL fallback, and Commons Special:Redirect fallback.

Run from project root:
  python tools/fetch_open_images.py --limit 10 --start 0
  python tools/apply_downloaded_manifest.py
"""
import argparse
import json
import re
import time
from pathlib import Path
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parents[1]
COMMONS_API = "https://commons.wikimedia.org/w/api.php"

# Wikimedia can reject generic/script traffic. Keep this descriptive.
HEADERS = {
    "User-Agent": "PuzzleVerseEducationalImporter/0.3 (educational image attribution workflow; contact: vivian.life.rocks@gmail.com)",
    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://commons.wikimedia.org/",
}
API_HEADERS = {
    "User-Agent": HEADERS["User-Agent"],
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}
ALLOWED_EXT = (".jpg", ".jpeg", ".png", ".webp")


def strip_html(s):
    return re.sub("<[^<]+?>", "", s or "").strip()


def safe_filename_from_title(file_title: str) -> str:
    name = file_title.replace("File:", "", 1).strip()
    return name


def load_manifest():
    downloaded = ROOT / "data_manifest.downloaded.json"
    base = downloaded if downloaded.exists() else ROOT / "data_manifest.json"
    if not base.exists():
        raise FileNotFoundError("data_manifest.json not found. Run this from the PuzzleVerse repo root.")
    return json.loads(base.read_text(encoding="utf-8"))


def commons_search(title):
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": f"{title} filetype:bitmap",
        "gsrnamespace": 6,
        "gsrlimit": 12,
        "prop": "imageinfo",
        # thumburl gives a resized version, usually smaller and better for GitHub Pages.
        "iiprop": "url|mime|dimensions|extmetadata",
        "iiurlwidth": 1600,
        "format": "json",
        "formatversion": 2,
    }
    r = requests.get(COMMONS_API, params=params, headers=API_HEADERS, timeout=30)
    r.raise_for_status()
    pages = r.json().get("query", {}).get("pages", [])

    best = None
    best_score = -1
    for p in pages:
        info = (p.get("imageinfo") or [{}])[0]
        url = info.get("url", "")
        thumburl = info.get("thumburl", "")
        file_title = p.get("title", "")
        file_name = safe_filename_from_title(file_title)

        candidate_url = thumburl or url
        if not candidate_url.lower().split("?")[0].endswith(ALLOWED_EXT):
            continue

        width = int(info.get("width") or 0)
        height = int(info.get("height") or 0)
        if width < 500 or height < 350:
            continue

        meta = info.get("extmetadata", {})
        license_short = strip_html(meta.get("LicenseShortName", {}).get("value", ""))
        usage_terms = strip_html(meta.get("UsageTerms", {}).get("value", ""))
        artist = strip_html(meta.get("Artist", {}).get("value", ""))
        credit = strip_html(meta.get("Credit", {}).get("value", ""))

        score = width * height
        aspect = width / height if height else 0
        if 1.1 <= aspect <= 2.2:
            score *= 1.25
        # Avoid SVG/diagrams where possible for photo puzzle levels.
        if "svg" in candidate_url.lower():
            score *= 0.2

        if score > best_score:
            best_score = score
            best = {
                "url": url,
                "thumburl": thumburl,
                "fileTitle": file_title,
                "fileName": file_name,
                "redirectUrl": "https://commons.wikimedia.org/wiki/Special:Redirect/file/" + quote(file_name),
                "page": "https://commons.wikimedia.org/wiki/" + quote(file_title.replace(" ", "_")),
                "license": license_short or usage_terms,
                "artist": artist,
                "credit": credit,
                "source": "Wikimedia Commons",
                "width": width,
                "height": height,
            }
    return best


def extension_from_url(url: str):
    suffix = Path(url.split("?")[0]).suffix.lower()
    if suffix == ".jpeg":
        return ".jpg"
    if suffix in ALLOWED_EXT:
        return suffix
    return ".jpg"


def download_image(hit):
    # Try thumbnail first, then original URL, then Commons redirect.
    urls = []
    if hit.get("thumburl"):
        urls.append(hit["thumburl"])
    if hit.get("url"):
        urls.append(hit["url"])
    if hit.get("redirectUrl"):
        urls.append(hit["redirectUrl"])

    last_error = None
    for url in urls:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=90, allow_redirects=True)
            if resp.status_code == 403 and "upload.wikimedia.org" in url:
                last_error = RuntimeError(f"403 from {url}; trying fallback")
                continue
            resp.raise_for_status()
            ctype = resp.headers.get("content-type", "").lower()
            if "image" not in ctype and not url.lower().split("?")[0].endswith(ALLOWED_EXT):
                last_error = RuntimeError(f"not an image response: {ctype} from {url}")
                continue
            return resp.content, extension_from_url(resp.url or url), resp.url or url
        except Exception as ex:
            last_error = ex
            continue
    raise last_error or RuntimeError("No download URL worked")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=25)
    ap.add_argument("--start", type=int, default=0)
    args = ap.parse_args()

    manifest = load_manifest()
    end = min(len(manifest), args.start + args.limit)

    for idx in range(args.start, end):
        e = manifest[idx]
        if e.get("licenseStatus", "").startswith("downloaded") and Path(ROOT / e.get("image", "")).exists():
            print("Already downloaded:", e["title"])
            continue

        if e.get("sourceProvider") not in ("Wikimedia Commons", "NASA / Wikimedia Commons"):
            print("Skipped non-Wikimedia provider:", e["title"])
            continue

        try:
            hit = commons_search(e["title"])
            if not hit:
                print("No usable image found:", e["title"])
                continue

            folder = ROOT / e["localImage"].rsplit("/", 1)[0]
            folder.mkdir(parents=True, exist_ok=True)

            data, ext, final_url = download_image(hit)
            target = folder / ("image" + ext)
            target.write_bytes(data)

            rel = str(target.relative_to(ROOT)).replace("\\", "/")
            e["image"] = rel
            e["localImage"] = rel
            e["licenseStatus"] = "downloaded-needs-human-review"
            e["credit"] = f"{hit.get('artist') or hit.get('credit') or 'Unknown'} / Wikimedia Commons / {hit.get('license') or 'license needs review'}"

            (folder / "attribution.md").write_text(
                f"# Attribution for {e['title']}\n\n"
                f"Source page: {hit['page']}\n\n"
                f"Downloaded URL: {final_url}\n\n"
                f"Original URL: {hit.get('url')}\n\n"
                f"Thumbnail URL: {hit.get('thumburl')}\n\n"
                f"Artist: {hit.get('artist')}\n\n"
                f"Credit: {hit.get('credit')}\n\n"
                f"License: {hit.get('license')}\n\n"
                f"Original dimensions: {hit.get('width')} x {hit.get('height')}\n\n"
                "Review status: needs human review before commercial use.\n",
                encoding="utf-8",
            )
            print("Downloaded:", e["levelNumber"], e["title"], "->", rel)
            time.sleep(1.0)
        except Exception as ex:
            print("Error:", e.get("title"), ex)

    (ROOT / "data_manifest.downloaded.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print("Done. Now run: python tools/apply_downloaded_manifest.py")


if __name__ == "__main__":
    main()
