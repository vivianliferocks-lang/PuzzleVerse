#!/usr/bin/env python3
"""
PuzzleVerse Trivia Improver V5 - All Categories

Purpose:
  Replace generic PuzzleVerse trivia with more subject-specific trivia for all 500 records.
  Uses Wikidata/Wikipedia when available, falls back to safer category-specific educational questions.

Examples:
  python tools/improve_all_trivia_v5.py --all --delay 6
  python tools/improve_all_trivia_v5.py --category famous_people --start 0 --limit 25 --delay 8
  python tools/improve_all_trivia_v5.py --ids pv-108-mahatma-gandhi,pv-116-rani-lakshmibai --delay 8

Notes:
  - If you see 429 rate limit messages, the script waits and retries automatically.
  - It writes a backup of src/levels.js before updating.
  - It writes tools/trivia_v5_report.csv with status for each updated record.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import re
import shutil
import time
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import requests
except ImportError:
    raise SystemExit("Missing dependency: requests. Run: python -m pip install requests")

ROOT = Path(__file__).resolve().parents[1]
LEVELS_PATH = ROOT / "src" / "levels.js"
CACHE_DIR = ROOT / "tools" / ".trivia_cache_v5"
REPORT_PATH = ROOT / "tools" / "trivia_v5_report.csv"
USER_AGENT = "PuzzleVerseEducationalGame/0.5 (trivia curation; contact: project-owner)"

COUNTRIES = [
    "India", "China", "Japan", "Egypt", "Greece", "Italy", "France", "United Kingdom", "United States",
    "Brazil", "Mexico", "Peru", "Australia", "South Africa", "Germany", "Russia", "Canada", "Spain",
    "Turkey", "Cambodia", "Nepal", "Sri Lanka", "Indonesia", "Kenya", "Tanzania", "Norway", "Sweden"
]
PEOPLE_ROLES = [
    "political leader", "freedom fighter", "scientist", "mathematician", "writer", "poet", "nurse", "physicist",
    "astronomer", "engineer", "inventor", "philosopher", "social reformer", "civil rights leader", "artist",
    "explorer", "teacher", "environmentalist", "doctor", "ruler", "economist", "computer scientist", "astronaut"
]
SITE_TYPES = [
    "ancient monument", "religious site", "fortress", "archaeological site", "natural landmark", "modern city",
    "museum", "palace", "temple complex", "amphitheatre", "pyramid", "observatory", "historic city", "heritage site"
]
ANIMAL_GROUPS = ["mammal", "bird", "reptile", "fish", "insect", "arachnid", "crustacean", "mollusc", "cnidarian", "amphibian", "dinosaur", "extinct reptile"]
SCIENCE_FIELDS = ["biology", "physics", "chemistry", "astronomy", "engineering", "medicine", "geology", "computer science", "mathematics", "meteorology"]
CLOUD_DISTRACTORS = ["Cumulus", "Stratus", "Cirrus", "Cumulonimbus", "Altostratus", "Nimbostratus", "Cirrocumulus"]
CONSTELLATION_DISTRACTORS = ["Orion", "Scorpius", "Ursa Major", "Cassiopeia", "Cygnus", "Leo", "Taurus", "Andromeda"]
CIV_DISTRACTORS = ["Indus Valley", "Maya", "Aztec", "Ancient Egypt", "Mesopotamia", "Inca", "Roman Empire", "Ancient Greece", "Olmec"]


def safe_filename(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", s)[:180]


def request_json(url: str, params: Dict[str, Any] | None = None, delay: float = 1.0, max_retries: int = 6) -> Dict[str, Any]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    raw = url + "?" + urllib.parse.urlencode(params or {}, doseq=True)
    key = CACHE_DIR / (safe_filename(raw) + ".json")
    if key.exists():
        try:
            return json.loads(key.read_text(encoding="utf-8"))
        except Exception:
            pass

    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    wait = max(delay, 0.5)
    last_error = None
    for attempt in range(max_retries):
        if attempt > 0 or delay:
            time.sleep(wait)
        try:
            r = requests.get(url, params=params, headers=headers, timeout=35)
            if r.status_code == 429:
                cool_down = max(60, int(wait * 5))
                print(f"  429 rate limit. Waiting {cool_down}s before retry...", flush=True)
                time.sleep(cool_down)
                wait *= 1.8
                continue
            r.raise_for_status()
            data = r.json()
            key.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            return data
        except Exception as e:
            last_error = e
            wait *= 1.7
    raise RuntimeError(f"Request failed: {url} {params} -> {last_error}")


def load_levels_js() -> Tuple[List[Dict[str, Any]], str, str]:
    text = LEVELS_PATH.read_text(encoding="utf-8")
    patterns = [
        r"(window\.PUZZLEVERSE_LEVELS\s*=\s*)(\[.*?\])(\s*;)",
        r"(const\s+PUZZLEVERSE_LEVELS\s*=\s*)(\[.*?\])(\s*;)",
        r"(var\s+PUZZLEVERSE_LEVELS\s*=\s*)(\[.*?\])(\s*;)"
    ]
    for pat in patterns:
        m = re.search(pat, text, flags=re.S)
        if m:
            return json.loads(m.group(2)), text, pat
    raise RuntimeError("Could not find PUZZLEVERSE_LEVELS array in src/levels.js")


def write_levels_js(levels: List[Dict[str, Any]], text: str, pattern: str) -> None:
    backup = LEVELS_PATH.with_suffix(LEVELS_PATH.suffix + ".bak_trivia_v5")
    shutil.copy2(LEVELS_PATH, backup)
    new_arr = json.dumps(levels, ensure_ascii=False, indent=2)
    new_text = re.sub(pattern, lambda m: m.group(1) + new_arr + m.group(3), text, count=1, flags=re.S)
    LEVELS_PATH.write_text(new_text, encoding="utf-8")
    print(f"Updated {LEVELS_PATH}")
    print(f"Backup saved as {backup}")


def search_entity(title: str, delay: float) -> Optional[str]:
    try:
        data = request_json("https://www.wikidata.org/w/api.php", {
            "action": "wbsearchentities", "format": "json", "language": "en", "search": title, "limit": 1
        }, delay=delay)
        res = data.get("search") or []
        return res[0].get("id") if res else None
    except Exception as e:
        print(f"  Wikidata search failed for {title}: {e}")
        return None


def entity_data(qid: str, delay: float) -> Dict[str, Any]:
    try:
        data = request_json(f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json", {}, delay=delay)
        return data.get("entities", {}).get(qid, {})
    except Exception as e:
        print(f"  Entity data failed for {qid}: {e}")
        return {}


def label_for_qid(qid: str, delay: float) -> str:
    ent = entity_data(qid, delay)
    return ent.get("labels", {}).get("en", {}).get("value", qid)


def claim_values(ent: Dict[str, Any], prop: str, delay: float, maxn: int = 3) -> List[str]:
    out: List[str] = []
    claims = ent.get("claims", {}).get(prop, [])[:maxn]
    for c in claims:
        val = c.get("mainsnak", {}).get("datavalue", {}).get("value")
        try:
            if isinstance(val, dict) and "id" in val:
                out.append(label_for_qid(val["id"], delay))
            elif isinstance(val, dict) and "time" in val:
                out.append(val["time"].lstrip("+").split("T")[0])
            elif isinstance(val, str):
                out.append(val)
        except Exception:
            continue
    # Dedupe while preserving order
    seen = set(); deduped = []
    for x in out:
        lx = x.lower()
        if x and lx not in seen:
            seen.add(lx); deduped.append(x)
    return deduped


def wikipedia_summary(title: str, delay: float) -> str:
    try:
        data = request_json("https://en.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(title), {}, delay=delay)
        return (data.get("extract") or "").strip()
    except Exception as e:
        print(f"  Wikipedia summary failed for {title}: {e}")
        return ""


def clean_sentence(text: str, title: str, category: str) -> str:
    if not text:
        fallback = {
            "famous_people": f"{title} is remembered for a real historical contribution.",
            "world_places": f"{title} is an important place connected with geography, culture, or history.",
            "science_discoveries": f"{title} is connected to science, discovery, or technology.",
            "clouds": f"{title} is connected with weather observation and cloud science.",
            "constellations": f"{title} is a named constellation or sky pattern used in astronomy.",
            "deep_sea": f"{title} is connected with life in the deep ocean.",
            "corals": f"{title} is connected with coral reefs and marine ecosystems.",
            "small_critters": f"{title} is a small animal or invertebrate that supports biodiversity.",
            "animals": f"{title} is an animal connected to ecology and biodiversity.",
            "dinosaurs_extinct_animals": f"{title} is connected with prehistoric or extinct life.",
            "extinct_civilizations": f"{title} is connected with ancient or lost civilizations."
        }
        return fallback.get(category, f"{title} is an educational subject in PuzzleVerse.")
    # Use first decent sentence.
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    for p in parts:
        p = p.strip()
        if 35 <= len(p) <= 220 and not p.lower().startswith("this article"):
            return p
    return parts[0][:220].rstrip(" ,;") if parts else f"{title} is an educational subject in PuzzleVerse."


def unique_options(correct: str, distractors: List[str], n: int = 4) -> List[str]:
    opts = [correct.strip()]
    for d in distractors:
        d = str(d).strip()
        if not d: continue
        if d.lower() != correct.lower() and all(d.lower() != x.lower() for x in opts):
            opts.append(d)
        if len(opts) >= n:
            break
    generic = ["Not related", "A fictional answer", "A random modern brand", "A cooking method", "A video-game-only item"]
    for g in generic:
        if len(opts) >= n: break
        if all(g.lower() != x.lower() for x in opts): opts.append(g)
    return opts[:n]


def make_q(q: str, correct: str, distractors: List[str]) -> Dict[str, Any]:
    return {"q": q, "a": unique_options(correct, distractors, 4), "correct": 0}


def make_true_q(title: str, summary: str, cat: str) -> Dict[str, Any]:
    sent = clean_sentence(summary, title, cat)
    return {
        "q": f"Which statement is true about {title}?",
        "a": [sent, f"{title} is only a fictional mobile-game item.", f"{title} is mainly a cooking utensil.", f"{title} is a random road sign."],
        "correct": 0
    }


def theme_question(rec: Dict[str, Any]) -> Dict[str, Any]:
    title = rec.get("title", "This topic")
    theme = rec.get("theme") or rec.get("category", "Educational Topic").replace("_", " ").title()
    return make_q(f"Which PuzzleVerse collection does {title} belong to?", theme, ["Sports Stadium", "Cooking Method", "Random Brand", "Phone Model", "Musical Instrument"])


def improve_person(rec: Dict[str, Any], ent: Dict[str, Any], summary: str, delay: float) -> List[Dict[str, Any]]:
    title = rec.get("title", "This person")
    occupations = claim_values(ent, "P106", delay, 4)
    fields = claim_values(ent, "P101", delay, 3)
    countries = claim_values(ent, "P27", delay, 3)
    birthplaces = claim_values(ent, "P19", delay, 2)
    notable = claim_values(ent, "P800", delay, 2)
    qs: List[Dict[str, Any]] = []
    if occupations:
        qs.append(make_q(f"{title} is best known as which kind of historical figure?", occupations[0], PEOPLE_ROLES))
    elif fields:
        qs.append(make_q(f"Which field is strongly connected with {title}?", fields[0], SCIENCE_FIELDS + PEOPLE_ROLES))
    else:
        qs.append(make_true_q(title, summary, "famous_people"))
    if countries:
        qs.append(make_q(f"{title} is most strongly associated with which country or citizenship?", countries[0], COUNTRIES))
    elif birthplaces:
        qs.append(make_q(f"Which place is connected to the life of {title}?", birthplaces[0], COUNTRIES + ["Atlantis", "Mars Colony", "The Moon"]))
    else:
        qs.append(make_q(f"Why is {title} included in this educational puzzle set?", "Because they are an important real historical figure", ["Because they are a cloud type", "Because they are a dinosaur species", "Because they are a fictional snack", "Because they are a road sign"]))
    if notable:
        qs.append(make_q(f"Which notable work or achievement is connected with {title}?", notable[0], ["Random Road", "A cooking recipe", "A fictional sword", "A phone charger"]))
    else:
        qs.append(make_true_q(title, summary, "famous_people"))
    return qs[:3]


def improve_place(rec: Dict[str, Any], ent: Dict[str, Any], summary: str, delay: float) -> List[Dict[str, Any]]:
    title = rec.get("title", "This place")
    countries = claim_values(ent, "P17", delay, 2)
    located = claim_values(ent, "P131", delay, 2)
    inst = claim_values(ent, "P31", delay, 3)
    qs: List[Dict[str, Any]] = []
    if countries:
        qs.append(make_q(f"In which country is {title} located?", countries[0], COUNTRIES))
    else:
        qs.append(make_true_q(title, summary, "world_places"))
    if inst:
        qs.append(make_q(f"What type of place is {title}?", inst[0], SITE_TYPES))
    else:
        qs.append(make_q(f"What makes {title} useful as an educational puzzle image?", "It represents a real place with cultural, historic, or geographic value", ["It is only a random brand logo", "It is only a cooking recipe", "It is only a fictional phone model", "It is only a shoe size"]))
    if located:
        qs.append(make_q(f"Which region or city is connected to {title}?", located[0], COUNTRIES + ["The Moon", "Underwater City", "Random Brand City"]))
    else:
        qs.append(make_true_q(title, summary, "world_places"))
    return qs[:3]


def improve_life(rec: Dict[str, Any], ent: Dict[str, Any], summary: str, delay: float) -> List[Dict[str, Any]]:
    title = rec.get("title", "This organism")
    cat = rec.get("category", "animals")
    taxon = claim_values(ent, "P225", delay, 1)
    rank = claim_values(ent, "P105", delay, 1)
    parent = claim_values(ent, "P171", delay, 2)
    qs: List[Dict[str, Any]] = []
    if taxon:
        qs.append(make_q(f"What scientific or taxon name is connected to {title}?", taxon[0], ["Homo sapiens", "Panthera leo", "Felis catus", "Aves", "Insecta"]))
    else:
        qs.append(make_true_q(title, summary, cat))
    if parent:
        qs.append(make_q(f"Which biological group is {title} connected to?", parent[0], ANIMAL_GROUPS))
    elif rank:
        qs.append(make_q(f"Which taxonomy clue is connected with {title}?", rank[0], ANIMAL_GROUPS))
    else:
        qs.append(make_q(f"Why is {title} part of the nature puzzle collection?", "It helps players learn about biodiversity and living or extinct life", ["It is a famous treaty", "It is a computer file", "It is a musical note", "It is a car model"]))
    qs.append(make_true_q(title, summary, cat))
    return qs[:3]


def improve_science(rec: Dict[str, Any], ent: Dict[str, Any], summary: str, delay: float) -> List[Dict[str, Any]]:
    title = rec.get("title", "This science topic")
    inst = claim_values(ent, "P31", delay, 2)
    fields = claim_values(ent, "P361", delay, 2) + claim_values(ent, "P279", delay, 2)
    qs: List[Dict[str, Any]] = []
    qs.append(make_true_q(title, summary, "science_discoveries"))
    if inst:
        qs.append(make_q(f"What kind of scientific topic is {title}?", inst[0], SCIENCE_FIELDS + ["machine", "process", "structure", "instrument", "natural phenomenon"]))
    elif fields:
        qs.append(make_q(f"Which larger science idea is connected with {title}?", fields[0], SCIENCE_FIELDS + ["medicine", "space exploration", "mechanics"]))
    else:
        qs.append(make_q(f"Why is {title} useful in an educational science puzzle?", "It connects image recognition with real science learning", ["It is only a snack", "It is only a phone brand", "It is only a random road", "It is only a shoe size"]))
    qs.append(theme_question(rec))
    return qs[:3]


def improve_cloud(rec: Dict[str, Any], summary: str) -> List[Dict[str, Any]]:
    title = rec.get("title", "This cloud type")
    return [
        make_q(f"What should you observe first in a cloud puzzle about {title}?", "Shape, height, texture, and weather clues", ["Only the price of the cloud", "Only a political flag", "Only a cooking ingredient", "Only a cartoon logo"]),
        make_true_q(title, summary, "clouds"),
        make_q(f"Why are cloud types educational in PuzzleVerse?", "They connect visual pattern recognition with weather science", ["They teach only car repair", "They are fictional monsters only", "They are random letters", "They are phone passwords"])
    ]


def improve_constellation(rec: Dict[str, Any], summary: str) -> List[Dict[str, Any]]:
    title = rec.get("title", "This constellation")
    return [
        make_q(f"What is {title} in astronomy?", "A named star pattern or sky region used in astronomy", ["A coral reef", "A dinosaur bone", "A medieval tax coin", "A cooking style"]),
        make_true_q(title, summary, "constellations"),
        make_q(f"Why are constellations useful in an educational puzzle game?", "They teach sky recognition, mythology, and astronomy", ["They teach only shoe sizes", "They are cooking recipes", "They are bank passwords", "They are car engines"])
    ]


def improve_civilization(rec: Dict[str, Any], ent: Dict[str, Any], summary: str, delay: float) -> List[Dict[str, Any]]:
    title = rec.get("title", "This civilization")
    countries = claim_values(ent, "P17", delay, 2) + claim_values(ent, "P495", delay, 2)
    inst = claim_values(ent, "P31", delay, 2)
    qs: List[Dict[str, Any]] = []
    qs.append(make_true_q(title, summary, "extinct_civilizations"))
    if countries:
        qs.append(make_q(f"Which modern country or region is strongly connected with {title}?", countries[0], COUNTRIES))
    elif inst:
        qs.append(make_q(f"What kind of historical subject is {title}?", inst[0], CIV_DISTRACTORS + ["ancient civilization", "archaeological culture"]))
    else:
        qs.append(make_q(f"Why is {title} important for history learning?", "It helps players connect images with ancient cultures and human history", ["It is a cloud type", "It is a phone charger", "It is a recipe", "It is a random brand"]))
    qs.append(theme_question(rec))
    return qs[:3]


def improve_record(rec: Dict[str, Any], delay: float, offline_only: bool = False) -> Tuple[bool, str]:
    title = rec.get("title", "")
    cat = rec.get("category", "")
    qid = None; ent: Dict[str, Any] = {}; summary = ""
    if not offline_only:
        qid = search_entity(title, delay)
        if qid:
            ent = entity_data(qid, delay)
        summary = wikipedia_summary(title, delay)

    if cat == "famous_people":
        rec["trivia"] = improve_person(rec, ent, summary, delay)
    elif cat == "world_places":
        rec["trivia"] = improve_place(rec, ent, summary, delay)
    elif cat in {"animals", "small_critters", "deep_sea", "corals", "dinosaurs_extinct_animals"}:
        rec["trivia"] = improve_life(rec, ent, summary, delay)
    elif cat == "science_discoveries":
        rec["trivia"] = improve_science(rec, ent, summary, delay)
    elif cat == "clouds":
        rec["trivia"] = improve_cloud(rec, summary)
    elif cat == "constellations":
        rec["trivia"] = improve_constellation(rec, summary)
    elif cat == "extinct_civilizations":
        rec["trivia"] = improve_civilization(rec, ent, summary, delay)
    else:
        rec["trivia"] = [make_true_q(title, summary, cat), theme_question(rec), make_q(f"What should you study while solving {title}?", "The image details and educational context", ["Only random coins", "Only a car engine", "Only a cooking recipe", "Only a password"])]
    rec["triviaStatus"] = "improved-v5-subject-specific"
    rec["triviaSource"] = "wikidata-wikipedia-with-template-fallback" if not offline_only else "template-fallback"
    return True, qid or "template"


def select_records(levels: List[Dict[str, Any]], args) -> List[Dict[str, Any]]:
    if args.ids:
        want = {x.strip() for x in args.ids.split(",") if x.strip()}
        return [r for r in levels if r.get("id") in want]
    records = levels
    if args.category:
        records = [r for r in records if r.get("category") == args.category]
    if not args.all and not args.category and not args.ids:
        print("No selector provided. Use --all, --category, or --ids.")
        return []
    start = max(0, args.start or 0)
    end = None if args.limit is None else start + args.limit
    return records[start:end]


def write_report(rows: List[Dict[str, Any]]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with REPORT_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "levelNumber", "title", "category", "status", "source", "note"])
        writer.writeheader(); writer.writerows(rows)
    print(f"Report: {REPORT_PATH}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="Process all records")
    ap.add_argument("--ids", help="Comma-separated level IDs")
    ap.add_argument("--category", help="Process a single category")
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--delay", type=float, default=6.0)
    ap.add_argument("--offline-template", action="store_true", help="Do not call Wikipedia/Wikidata; use template fallback only")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    levels, text, pattern = load_levels_js()
    records = select_records(levels, args)
    print(f"Selected records: {len(records)}")
    if not records:
        return
    rows = []
    updated = 0
    for i, rec in enumerate(records, 1):
        title = rec.get("title", "")
        print(f"[{i}/{len(records)}] Improving trivia: {rec.get('id')} - {title}", flush=True)
        try:
            ok, source = improve_record(rec, args.delay, offline_only=args.offline_template)
            if ok: updated += 1
            rows.append({"id": rec.get("id"), "levelNumber": rec.get("levelNumber"), "title": title, "category": rec.get("category"), "status": "updated" if ok else "skipped", "source": source, "note": ""})
        except KeyboardInterrupt:
            rows.append({"id": rec.get("id"), "levelNumber": rec.get("levelNumber"), "title": title, "category": rec.get("category"), "status": "interrupted", "source": "", "note": "KeyboardInterrupt"})
            print("Interrupted by user. Saving what was already updated...")
            break
        except Exception as e:
            print(f"  ERROR: {e}")
            # Still write safe fallback so the record is improved compared to fully generic trivia.
            try:
                improve_record(rec, args.delay, offline_only=True)
                updated += 1
                rows.append({"id": rec.get("id"), "levelNumber": rec.get("levelNumber"), "title": title, "category": rec.get("category"), "status": "fallback-updated", "source": "template", "note": str(e)[:200]})
            except Exception as ee:
                rows.append({"id": rec.get("id"), "levelNumber": rec.get("levelNumber"), "title": title, "category": rec.get("category"), "status": "failed", "source": "", "note": str(ee)[:200]})
    if not args.dry_run:
        write_levels_js(levels, text, pattern)
        write_report(rows)
    print(f"Done. Updated trivia records: {updated}")


if __name__ == "__main__":
    main()
