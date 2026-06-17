#!/usr/bin/env python3
"""
Create a local HTML gallery from tools/suspicious_images.csv or tools/smart_curation_v3_report.csv
so you can quickly review bad puzzle images in the browser.
Run:
  python tools/make_review_gallery.py
Open:
  tools/review_gallery.html
"""
import csv
from pathlib import Path

ROOT = Path.cwd()
csv_path = ROOT / "tools" / "suspicious_images.csv"
if not csv_path.exists():
    csv_path = ROOT / "tools" / "smart_curation_v3_report.csv"

out_path = ROOT / "tools" / "review_gallery.html"

rows = []
if csv_path.exists():
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

def image_for(row):
    img = row.get("image") or ""
    if img:
        return "../" + img.replace("\\", "/") if not img.startswith("..") else img
    return ""

cards = []
for r in rows:
    title = r.get("title","")
    ident = r.get("id","")
    level = r.get("level","")
    img = image_for(r)
    reason = r.get("reasons") or r.get("warning") or r.get("status","")
    cards.append(f"""
    <article>
      <img src="{img}" onerror="this.style.opacity=.2">
      <h3>{level} {title}</h3>
      <p>{ident}</p>
      <p>{reason}</p>
      <code>{r.get('image','')}</code>
    </article>
    """)

html = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>PuzzleVerse Image Review Gallery</title>
<style>
body {{ margin: 0; background: #101326; color: white; font-family: Arial, sans-serif; }}
header {{ padding: 22px; position: sticky; top: 0; background: #101326; border-bottom: 1px solid #333; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 16px; padding: 16px; }}
article {{ background: #202640; border: 1px solid #3b4266; border-radius: 14px; overflow: hidden; }}
img {{ width: 100%; height: 170px; object-fit: cover; background: #000; display: block; }}
h3 {{ margin: 12px 12px 4px; }}
p, code {{ display: block; margin: 8px 12px; color: #bfc7ff; word-break: break-word; }}
code {{ font-size: 11px; color: #9ee; margin-bottom: 14px; }}
</style>
</head>
<body>
<header>
<h1>PuzzleVerse Image Review Gallery</h1>
<p>Source CSV: {csv_path.name} · Records: {len(rows)}</p>
</header>
<div class="grid">
{''.join(cards)}
</div>
</body>
</html>"""
out_path.write_text(html, encoding="utf-8")
print(f"Created {out_path}")
