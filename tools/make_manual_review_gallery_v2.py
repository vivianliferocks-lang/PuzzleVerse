#!/usr/bin/env python3
import json,re,html
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];LEVELS=ROOT/'src'/'levels.js';OUT=ROOT/'tools'/'manual_review_gallery.html'
text=LEVELS.read_text(encoding='utf-8');m=re.search(r"window\.PUZZLEVERSE_LEVELS\s*=\s*(\[[\s\S]*?\]);",text)
if not m:raise SystemExit('Could not parse levels.js')
levels=json.loads(m.group(1));cards=[]
for l in levels:
 img=l.get('localImage') or l.get('image') or '';cards.append(f"<article><img src='../{html.escape(img)}'><h3>{html.escape(str(l.get('levelNumber','')))}. {html.escape(l.get('title',''))}</h3><p>{html.escape(l.get('category',''))}</p></article>")
OUT.write_text("<!doctype html><html><head><meta charset='utf-8'><title>PuzzleVerse Review</title><style>body{font-family:Arial;background:#f6f7fb}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:14px}article{background:white;border-radius:14px;overflow:hidden;box-shadow:0 4px 16px #0001}img{width:100%;height:150px;object-fit:cover}h3,p{padding:0 12px}</style></head><body><h1>PuzzleVerse Manual Image Review</h1><div class='grid'>"+"\n".join(cards)+"</div></body></html>",encoding='utf-8');print('Created:',OUT)
