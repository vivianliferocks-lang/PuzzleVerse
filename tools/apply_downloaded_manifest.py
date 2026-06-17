#!/usr/bin/env python3
"""Copy data_manifest.downloaded.json into src/levels.js for the browser game."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
manifest_path = ROOT / 'data_manifest.downloaded.json'
if not manifest_path.exists():
    raise FileNotFoundError('data_manifest.downloaded.json not found. Run fetch_open_images.py first.')
levels = json.loads(manifest_path.read_text(encoding='utf-8'))
levels_js = ROOT / 'src' / 'levels.js'
levels_js.parent.mkdir(exist_ok=True)
content = """/*
  PuzzleVerse Educational Content Pack.
  Generated from data_manifest.downloaded.json.
  Review image attribution before commercial release.
*/
window.PUZZLEVERSE_LEVELS = """ + json.dumps(levels, indent=2, ensure_ascii=False) + ";\n\n"
content += """window.PUZZLEVERSE_EVENTS = [
  { title: 'Diwali Lights Challenge', theme: 'Diwali', reward: 'Top 3 win 1,000,000 / 500,000 / 250,000 coins', status: 'Planned' },
  { title: 'Chinese New Year Puzzle Race', theme: 'Chinese New Year', reward: 'Festival frame + coin rewards', status: 'Planned' },
  { title: 'Ocean Day Reef Quest', theme: 'Marine Life', reward: 'Coral Guardian badge', status: 'Planned' },
  { title: 'Dinosaur Discovery Cup', theme: 'Prehistoric Life', reward: 'Fossil Master title', status: 'Planned' }
];
"""
levels_js.write_text(content, encoding='utf-8')
print(f'Updated {levels_js}')
