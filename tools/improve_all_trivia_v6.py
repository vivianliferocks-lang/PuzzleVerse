#!/usr/bin/env python3
import re,json,argparse,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; LEVELS=ROOT/'src'/'levels.js'
CATEGORY_HINTS={'famous_people':('Which field or public role is most closely connected with {title}?',['Science / history / public life','Cooking recipe','Random road sign','Sports stadium']),'world_places':('What kind of landmark or site is {title} best known as?',['Historic or cultural site','Computer part','Cooking method','Modern app']),'science_discoveries':('What topic does {title} most directly help us understand?',['Science and how the world works','Fashion design','Movie awards','Restaurant menus']),'clouds':('{title} is mainly studied as part of which subject?',['Weather and atmosphere','Ancient coins','Deep sea fossils','Musical notes']),'constellations':('{title} is best connected with what?',['Astronomy and the night sky','Kitchen tools','Coral reefs only','Road construction']),'deep_sea':('{title} belongs most closely to which environment?',['Deep ocean life','Desert farming','City traffic','Mountain temples']),'corals':('{title} is important because it is connected to what ecosystem?',['Coral reef ecosystems','Cloud formation','Space travel','Ancient coins']),'small_critters':('{title} is best studied as what type of subject?',['Small animal or invertebrate life','Ancient building','Planetary motion','Political speech']),'animals':('{title} is best understood as what?',['Animal life and ecology','Medieval architecture','Cloud type','Mathematical formula only']),'dinosaurs_extinct_animals':('{title} is connected most strongly with what?',['Prehistoric or extinct life','Modern banking','Cloud seeding','Phone software']),'extinct_civilizations':('{title} is best connected with what?',['Ancient civilization and history','Modern social media','Marine biology only','Electric motors'])}
def extract(text):
 m=re.search(r"window\.PUZZLEVERSE_LEVELS\s*=\s*(\[[\s\S]*?\]);",text)
 if not m: raise SystemExit('Could not find PUZZLEVERSE_LEVELS')
 return m.start(1),m.end(1),json.loads(m.group(1))
def make(l):
 title=l.get('title','this subject');cat=l.get('category','');theme=l.get('theme','Educational knowledge');fact=l.get('contextFact') or l.get('educationalFact') or f'{title} has educational value.'
 q,a=CATEGORY_HINTS.get(cat,('What is this puzzle mainly teaching you about?',[theme,'Random guessing','Unrelated entertainment','A shopping cart']))
 return [{'q':q.format(title=title),'a':a,'correct':0},{'q':f'What should you pay attention to while solving {title}?','a':['The visual details that reveal the subject','Only the timer number','Only the browser address bar','Only the button color'],'correct':0},{'q':f'Why is {title} included in PuzzleVerse?','a':[fact[:120],'It is unrelated to learning','It is only a blank image','It is a coin button'],'correct':0}]
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--category',default='');ap.add_argument('--start',type=int,default=0);ap.add_argument('--limit',type=int,default=9999);args=ap.parse_args()
 text=LEVELS.read_text(encoding='utf-8');s,e,levels=extract(text);ids=[i for i,l in enumerate(levels) if not args.category or l.get('category')==args.category][args.start:args.start+args.limit]
 for i in ids:levels[i]['trivia']=make(levels[i])
 backup=LEVELS.with_suffix('.js.bak_trivia_v6');shutil.copy2(LEVELS,backup);LEVELS.write_text(text[:s]+json.dumps(levels,ensure_ascii=False,indent=2)+text[e:],encoding='utf-8')
 print('Updated trivia records:',len(ids));print('Backup:',backup)
if __name__=='__main__':main()
