#!/usr/bin/env python3
import re,csv,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];LEVELS=ROOT/'src'/'levels.js';REPORT=ROOT/'tools'/'prune_unused_images_report.csv'
ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');args=ap.parse_args()
text=LEVELS.read_text(encoding='utf-8') if LEVELS.exists() else '';refs=set(re.findall(r"assets/puzzle-library/[^\"']+?/image\.(?:jpg|jpeg|png|webp)",text,re.I));imgs=[p for p in (ROOT/'assets'/'puzzle-library').rglob('*') if p.suffix.lower() in ['.jpg','.jpeg','.png','.webp']]
rows=[];deleted=0
for p in imgs:
 rel=p.relative_to(ROOT).as_posix();keep=rel in refs;action='keep' if keep else ('delete' if args.apply else 'dry-run-delete');rows.append({'file':rel,'referenced':keep,'action':action})
 if args.apply and not keep:p.unlink();deleted+=1
with REPORT.open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=['file','referenced','action']);w.writeheader();w.writerows(rows)
print('Images scanned:',len(imgs));print('Referenced:',sum(1 for r in rows if r['referenced']));print('Unreferenced:',sum(1 for r in rows if not r['referenced']));print('Deleted:',deleted);print('Report:',REPORT)
