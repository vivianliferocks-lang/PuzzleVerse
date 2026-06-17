"""
Find likely wrong or low-confidence PuzzleVerse images after curation.
Run from repo root:
  python tools/find_suspicious_images.py
"""
from __future__ import annotations
import csv
import json
import re
from pathlib import Path

REPO_ROOT = Path.cwd()
LEVELS_JS = REPO_ROOT / "src" / "levels.js"
OUT = REPO_ROOT / "tools" / "suspicious_images.csv"
PEOPLE_NEGATIVE = re.compile(r"temple|mandir|mosque|church|school|hospital|airport|road|street|park|memorial|museum|house|grave|tomb|statue|bust|plaque|building|station|fort|palace|hall|center|centre|ferry|boat|ship|bridge|library|institute", re.I)
PLACEHOLDER = re.compile(r"placeholder\.svg", re.I)

def extract_js_array(text, var_name):
    idx = text.find(var_name)
    start = text.find("[", idx)
    depth=0; ins=False; esc=False
    for i,ch in enumerate(text[start:], start):
        if ins:
            if esc: esc=False
            elif ch=='\\': esc=True
            elif ch=='"': ins=False
        else:
            if ch=='"': ins=True
            elif ch=='[': depth+=1
            elif ch==']':
                depth-=1
                if depth==0:
                    return json.loads(text[start:i+1])
    raise RuntimeError('array not found')

def main():
    levels = extract_js_array(LEVELS_JS.read_text(encoding='utf-8'), 'PUZZLEVERSE_LEVELS')
    rows=[]
    for l in levels:
        reasons=[]
        img = l.get('image','')
        if PLACEHOLDER.search(img): reasons.append('placeholder')
        if not (REPO_ROOT / img).exists(): reasons.append('image-file-missing')
        if (l.get('category') or '') == 'famous_people':
            hay=' '.join(str(l.get(k,'')) for k in ['image','localImage','credit','curationWarning','curationSource'])
            # also read curation metadata if present
            cur = (REPO_ROOT / img).parent / 'curation.json' if img else None
            if cur and cur.exists():
                try:
                    meta=json.loads(cur.read_text(encoding='utf-8'))
                    hay += ' ' + ' '.join(str(meta.get(k,'')) for k in ['title','description','warning','url'])
                except Exception:
                    pass
            if PEOPLE_NEGATIVE.search(hay): reasons.append('person-image-may-be-place/statue/building')
        if float(l.get('curationScore') or 100) < 50: reasons.append('low-curation-score')
        if reasons:
            rows.append({'level':l.get('levelNumber'), 'id':l.get('id'), 'title':l.get('title'), 'category':l.get('category'), 'image':img, 'reasons':';'.join(reasons)})
    OUT.parent.mkdir(exist_ok=True)
    with OUT.open('w', newline='', encoding='utf-8') as f:
        w=csv.DictWriter(f, fieldnames=['level','id','title','category','image','reasons'])
        w.writeheader(); w.writerows(rows)
    print(f'Found {len(rows)} suspicious records.')
    print(f'Report: {OUT}')

if __name__ == '__main__': main()
