#!/usr/bin/env python3
"""
PuzzleVerse Trivia Improver V4
Updates generic trivia into subject-specific trivia using Wikidata/Wikipedia where possible.
It is intentionally conservative: if it cannot find reliable data, it writes better category-specific educational questions rather than pretending facts.

Examples:
  python tools/improve_trivia_v4.py --ids pv-108-mahatma-gandhi,pv-116-rani-lakshmibai --delay 5
  python tools/improve_trivia_v4.py --category famous_people --start 0 --limit 20 --delay 5
  python tools/improve_trivia_v4.py --category world_places --start 0 --limit 50 --delay 3
"""
from __future__ import annotations
import argparse, json, re, shutil, time, urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import requests

ROOT = Path(__file__).resolve().parents[1]
LEVELS_PATH = ROOT / "src" / "levels.js"
CACHE_DIR = ROOT / "tools" / ".trivia_cache_v4"
USER_AGENT = "PuzzleVerseEducationalGame/0.4 (trivia; contact: project-owner)"

COUNTRIES = ["India", "China", "Japan", "Egypt", "Greece", "Italy", "France", "United Kingdom", "United States", "Brazil", "Mexico", "Peru", "Australia", "South Africa", "Germany", "Russia", "Canada", "Spain"]
FIELDS = ["science", "mathematics", "literature", "politics", "nursing", "astronomy", "civil rights", "art", "invention", "philosophy", "medicine", "space exploration", "environmental conservation", "social reform"]
OCCUPATION_DISTRACTORS = [
    "scientist", "writer", "political leader", "freedom fighter", "mathematician",
    "nurse", "physicist", "astronomer", "engineer", "inventor", "philosopher",
    "social reformer", "civil rights leader", "artist", "explorer", "teacher",
    "environmentalist", "doctor", "ruler", "economist"
]
SITE_TYPES = ["ancient monument", "religious site", "fortress", "archaeological site", "natural landmark", "modern city", "museum", "palace", "temple complex", "amphitheatre", "pyramid", "observatory"]
ANIMAL_GROUPS = ["mammal", "bird", "reptile", "fish", "insect", "arachnid", "crustacean", "mollusc", "cnidarian", "amphibian"]

PROPERTY_LABELS = {
    "P17": "country", "P27": "country of citizenship", "P19": "place of birth", "P20": "place of death",
    "P106": "occupation", "P101": "field of work", "P800": "notable work", "P31": "instance of",
    "P131": "located in", "P495": "country of origin", "P1412": "languages spoken", "P569": "date of birth",
    "P570": "date of death", "P225": "taxon name", "P105": "taxon rank", "P171": "parent taxon"
}


def request_json(url: str, params: Dict[str, Any] | None = None, delay: float = 1.0, max_retries: int = 5) -> Dict[str, Any]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    raw = url + "?" + urllib.parse.urlencode(params or {}, doseq=True)
    key = CACHE_DIR / (re.sub(r"[^A-Za-z0-9_.-]", "_", raw)[:180] + ".json")
    if key.exists():
        try: return json.loads(key.read_text(encoding="utf-8"))
        except Exception: pass
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    wait = delay
    last = None
    for attempt in range(max_retries):
        if attempt > 0 or delay:
            time.sleep(wait)
        try:
            r = requests.get(url, params=params, headers=headers, timeout=30)
            if r.status_code == 429:
                print(f"429 rate limit. Waiting {max(45, int(wait*4))}s...", flush=True)
                time.sleep(max(45, wait*4)); wait *= 2; continue
            r.raise_for_status(); data = r.json()
            key.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            return data
        except Exception as e:
            last = e; wait *= 2
    raise RuntimeError(f"Request failed: {url} {params} -> {last}")


def load_levels_js() -> Tuple[List[Dict[str, Any]], str, str]:
    text = LEVELS_PATH.read_text(encoding="utf-8")
    patterns = [r"(window\.PUZZLEVERSE_LEVELS\s*=\s*)(\[.*?\])(\s*;)", r"(const\s+PUZZLEVERSE_LEVELS\s*=\s*)(\[.*?\])(\s*;)"]
    for pat in patterns:
        m = re.search(pat, text, flags=re.S)
        if m: return json.loads(m.group(2)), text, pat
    raise RuntimeError("Could not find PUZZLEVERSE_LEVELS array")


def write_levels_js(levels, text, pattern):
    backup = LEVELS_PATH.with_suffix(LEVELS_PATH.suffix + ".bak_trivia_v4")
    shutil.copy2(LEVELS_PATH, backup)
    new_arr = json.dumps(levels, ensure_ascii=False, indent=2)
    new_text = re.sub(pattern, lambda m: m.group(1) + new_arr + m.group(3), text, count=1, flags=re.S)
    LEVELS_PATH.write_text(new_text, encoding="utf-8")
    print(f"Updated {LEVELS_PATH}")
    print(f"Backup saved as {backup}")


def search_entity(title: str, delay: float) -> Optional[str]:
    data = request_json("https://www.wikidata.org/w/api.php", {"action":"wbsearchentities", "format":"json", "language":"en", "search":title, "limit":1}, delay=delay)
    res = data.get("search") or []
    return res[0].get("id") if res else None


def entity_data(qid: str, delay: float) -> Dict[str, Any]:
    data = request_json(f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json", {}, delay=delay)
    return data.get("entities", {}).get(qid, {})


def label_for_qid(qid: str, delay: float) -> str:
    try:
        ent = entity_data(qid, delay)
        return ent.get("labels", {}).get("en", {}).get("value", qid)
    except Exception:
        return qid


def claim_values(ent: Dict[str, Any], prop: str, delay: float, maxn: int = 3) -> List[str]:
    out = []
    for c in ent.get("claims", {}).get(prop, [])[:maxn]:
        val = c.get("mainsnak", {}).get("datavalue", {}).get("value")
        if isinstance(val, dict) and "id" in val:
            out.append(label_for_qid(val["id"], delay))
        elif isinstance(val, dict) and "time" in val:
            out.append(val["time"].lstrip("+").split("T")[0])
        elif isinstance(val, str):
            out.append(val)
    return [x for x in out if x]


def wikipedia_summary(title: str, delay: float) -> str:
    try:
        data = request_json("https://en.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(title), {}, delay=delay)
        return data.get("extract") or ""
    except Exception:
        return ""


def unique_options(correct: str, distractors: List[str], n: int = 4) -> List[str]:
    opts = [correct]
    for d in distractors:
        if d and d.lower() != correct.lower() and all(d.lower() != x.lower() for x in opts):
            opts.append(d)
        if len(opts) >= n: break
    return opts


def make_q(q: str, correct: str, distractors: List[str]) -> Dict[str, Any]:
    opts = unique_options(correct, distractors)
    while len(opts) < 4:
        opts.append(["Not related", "A fictional answer", "A random modern brand", "A cooking method"][len(opts)-1])
    return {"q": q, "a": opts[:4], "correct": 0}


def true_statement_question(title: str, summary: str, category: str) -> Dict[str, Any]:
    sent = summary.split(". ")[0].strip()
    if len(sent) < 20:
        if category == "famous_people": sent = f"{title} is remembered for real historical achievements."
        elif category == "world_places": sent = f"{title} is an important real-world landmark or historic site."
        elif category in {"animals", "small_critters", "deep_sea", "corals"}: sent = f"{title} is connected to the natural world and biodiversity."
        else: sent = f"{title} is an educational topic connected to this puzzle category."
    return {"q": f"Which statement is true about {title}?", "a": [sent, f"{title} is a fictional video game item only.", f"{title} is mainly a type of cooking utensil.", f"{title} is a random road sign."], "correct": 0}


def improve_record(rec: Dict[str, Any], delay: float) -> bool:
    title = rec.get("title", "")
    cat = rec.get("category", "")
    try:
        qid = search_entity(title, delay)
        ent = entity_data(qid, delay) if qid else {}
    except Exception as e:
        print(f"  entity lookup failed for {title}: {e}")
        ent = {}
    summary = wikipedia_summary(title, delay)
    trivia = []

    if cat == "famous_people":
        occupations = claim_values(ent, "P106", delay, maxn=3)
        fields = claim_values(ent, "P101", delay, maxn=2)
        countries = claim_values(ent, "P27", delay, maxn=2)
        birthplaces = claim_values(ent, "P19", delay, maxn=1)
        if occupations:
            trivia.append(make_q(f"{title} is best known as which kind of historical figure?", occupations[0], OCCUPATION_DISTRACTORS))
        elif fields:
            trivia.append(make_q(f"Which field is strongly connected with {title}?", fields[0], FIELDS))
        else:
            trivia.append(true_statement_question(title, summary, cat))
        if countries:
            trivia.append(make_q(f"{title} is most strongly associated with which country?", countries[0], COUNTRIES))
        elif birthplaces:
            trivia.append(make_q(f"Which place is connected to the life of {title}?", birthplaces[0], COUNTRIES + ["Atlantis", "Mars Colony"]))
        else:
            trivia.append({"q": f"Why is {title} included in PuzzleVerse?", "a": ["Because they are an important real historical figure", "Because they are a cloud type", "Because they are a dinosaur species", "Because they are a fictional snack"], "correct": 0})
        trivia.append(true_statement_question(title, summary, cat))

    elif cat == "world_places":
        country = claim_values(ent, "P17", delay, maxn=1)
        inst = claim_values(ent, "P31", delay, maxn=2)
        located = claim_values(ent, "P131", delay, maxn=1)
        if country: trivia.append(make_q(f"In which country is {title} located?", country[0], COUNTRIES))
        else: trivia.append(true_statement_question(title, summary, cat))
        if inst: trivia.append(make_q(f"What type of place is {title}?", inst[0], SITE_TYPES))
        else: trivia.append({"q": f"What makes {title} useful as an educational puzzle image?", "a": ["It represents a real place with cultural, historic, or geographic value", "It is only a random brand logo", "It is only a cooking recipe", "It is only a fictional phone model"], "correct": 0})
        if located: trivia.append(make_q(f"Which region or city is connected to {title}?", located[0], COUNTRIES + ["The Moon", "Underwater City"]))
        else: trivia.append(true_statement_question(title, summary, cat))

    elif cat in {"animals", "small_critters", "deep_sea", "corals", "dinosaurs_extinct_animals"}:
        taxon = claim_values(ent, "P225", delay, maxn=1)
        rank = claim_values(ent, "P105", delay, maxn=1)
        parent = claim_values(ent, "P171", delay, maxn=1)
        if taxon: trivia.append(make_q(f"What is the scientific/taxon name connected to {title}?", taxon[0], ["Homo sapiens", "Panthera leo", "Felis catus", "Aves", "Insecta"]))
        else: trivia.append(true_statement_question(title, summary, cat))
        if parent: trivia.append(make_q(f"Which biological group is {title} connected to?", parent[0], ANIMAL_GROUPS))
        elif rank: trivia.append(make_q(f"Which taxonomy clue is connected with {title}?", rank[0], ANIMAL_GROUPS))
        else: trivia.append({"q": f"Why is {title} part of the nature puzzle collection?", "a": ["It helps players learn about biodiversity and living/extinct life", "It is a famous political treaty", "It is a type of computer file", "It is a random musical note"], "correct": 0})
        trivia.append(true_statement_question(title, summary, cat))

    elif cat == "clouds":
        trivia = [
            {"q": f"What should players observe first in a cloud puzzle about {title}?", "a": ["Shape, height, texture, and weather clues", "Only the price of the cloud", "Only a political flag", "Only a cooking ingredient"], "correct": 0},
            true_statement_question(title, summary, cat),
            {"q": f"Why are cloud types educational in PuzzleVerse?", "a": ["They connect visual pattern recognition with weather science", "They teach only car repair", "They are fictional monsters only", "They are random letters"], "correct": 0}
        ]
    elif cat == "constellations":
        trivia = [
            {"q": f"What is {title} in astronomy?", "a": ["A named star pattern/sky region used in astronomy", "A type of coral reef", "A dinosaur bone", "A medieval tax coin"], "correct": 0},
            true_statement_question(title, summary, cat),
            {"q": f"Why are constellations useful in an educational puzzle game?", "a": ["They teach sky recognition, mythology, and astronomy", "They teach only shoe sizes", "They are only cooking recipes", "They are only bank passwords"], "correct": 0}
        ]
    else:
        trivia = [
            true_statement_question(title, summary, cat),
            {"q": f"Which category does {title} belong to in this game?", "a": [rec.get("theme", cat).replace("_", " "), "Sports Stadium", "Cooking Method", "Random Brand"], "correct": 0},
            {"q": f"What should you pay attention to while solving the {title} puzzle?", "a": ["The image details and the educational context", "Only the background music", "Only the screen brightness", "Only random coins"], "correct": 0}
        ]
    rec["trivia"] = trivia[:3]
    rec["triviaStatus"] = "improved-v4-needs-human-review"
    return True


def select_records(levels, args):
    if args.ids:
        want = {x.strip() for x in args.ids.split(",") if x.strip()}
        return [r for r in levels if r.get("id") in want]
    records = levels
    if args.category:
        records = [r for r in records if r.get("category") == args.category]
    start = args.start or 0
    end = None if args.limit is None else start + args.limit
    return records[start:end]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids")
    ap.add_argument("--category")
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--delay", type=float, default=4.0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    levels, text, pattern = load_levels_js()
    records = select_records(levels, args)
    print(f"Selected records: {len(records)}")
    updated = 0
    for i, rec in enumerate(records, 1):
        print(f"[{i}/{len(records)}] Improving trivia: {rec.get('id')} - {rec.get('title')}")
        try:
            if improve_record(rec, args.delay): updated += 1
        except Exception as e:
            print(f"  ERROR: {e}")
    if not args.dry_run:
        write_levels_js(levels, text, pattern)
    print(f"Done. Updated trivia records: {updated}")

if __name__ == "__main__": main()
