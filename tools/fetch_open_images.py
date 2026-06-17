#!/usr/bin/env python3
"""
PuzzleVerse open-image importer.

What it does:
1. Reads data_manifest.json.
2. Searches Wikimedia Commons for each item by title.
3. Downloads the first usable image candidate into the item folder as image.jpg.
4. Writes attribution.md and updates data_manifest.downloaded.json.

NASA items are left as manual-review entries unless you extend the NASA API section.
Run from project root:
  python tools/fetch_open_images.py --limit 25

Important: review every downloaded image and attribution before commercial release.
"""
import argparse, json, time, re
from pathlib import Path
from urllib.parse import urlencode
import requests

ROOT = Path(__file__).resolve().parents[1]
COMMONS_API = 'https://commons.wikimedia.org/w/api.php'
HEADERS = {'User-Agent':'PuzzleVerseEducationalImporter/0.1 (contact: replace-with-your-email)'}
ALLOWED_EXT = ('.jpg','.jpeg','.png','.webp')

def strip_html(s):
    return re.sub('<[^<]+?>','',s or '').strip()

def commons_search(title):
    params = {
        'action':'query','generator':'search','gsrsearch':f'{title} filetype:bitmap',
        'gsrnamespace':6,'gsrlimit':8,'prop':'imageinfo',
        'iiprop':'url|mime|dimensions|extmetadata','format':'json','formatversion':2
    }
    r=requests.get(COMMONS_API,params=params,headers=HEADERS,timeout=30)
    r.raise_for_status()
    pages=r.json().get('query',{}).get('pages',[])
    for p in pages:
        info=(p.get('imageinfo') or [{}])[0]
        url=info.get('url','')
        if not url.lower().endswith(ALLOWED_EXT):
            continue
        meta=info.get('extmetadata',{})
        license_short=strip_html(meta.get('LicenseShortName',{}).get('value',''))
        usage_terms=strip_html(meta.get('UsageTerms',{}).get('value',''))
        artist=strip_html(meta.get('Artist',{}).get('value',''))
        credit=strip_html(meta.get('Credit',{}).get('value',''))
        return {'url':url,'page':p.get('title',''),'license':license_short or usage_terms,'artist':artist,'credit':credit,'source':'Wikimedia Commons'}
    return None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--limit',type=int,default=10)
    ap.add_argument('--start',type=int,default=0)
    args=ap.parse_args()
    manifest=json.loads((ROOT/'data_manifest.json').read_text(encoding='utf-8'))
    out=[]
    count=0
    for e in manifest[args.start:]:
        if count>=args.limit: break
        if e.get('sourceProvider')!='Wikimedia Commons':
            out.append(e); continue
        folder=ROOT/e['localImage'].rsplit('/',1)[0]
        folder=Path(folder)
        folder.mkdir(parents=True,exist_ok=True)
        try:
            hit=commons_search(e['title'])
            if not hit:
                print('No hit:', e['title']); out.append(e); continue
            img=requests.get(hit['url'],headers=HEADERS,timeout=60)
            img.raise_for_status()
            ext=Path(hit['url']).suffix.split('?')[0] or '.jpg'
            target=folder/('image'+ext.lower())
            target.write_bytes(img.content)
            e['image']=str(target.relative_to(ROOT)).replace('\\','/')
            e['localImage']=e['image']
            e['licenseStatus']='downloaded-needs-human-review'
            e['credit']=f"{hit.get('artist') or hit.get('credit') or 'Unknown'} / Wikimedia Commons / {hit.get('license') or 'license needs review'}"
            (folder/'attribution.md').write_text(f"# Attribution for {e['title']}\n\nSource page: {hit['page']}\n\nImage URL: {hit['url']}\n\nArtist: {hit.get('artist')}\n\nCredit: {hit.get('credit')}\n\nLicense: {hit.get('license')}\n\nReview status: needs human review before commercial use.\n",encoding='utf-8')
            print('Downloaded:',e['title'])
            count+=1
            time.sleep(1)
        except Exception as ex:
            print('Error:',e['title'],ex)
        out.append(e)
    # preserve rest
    downloaded={x['id']:x for x in out}
    merged=[downloaded.get(e['id'],e) for e in manifest]
    (ROOT/'data_manifest.downloaded.json').write_text(json.dumps(merged,indent=2,ensure_ascii=False),encoding='utf-8')
    print('Done. Review attributions, then copy downloaded JSON into src/levels.js if desired.')
if __name__=='__main__': main()
