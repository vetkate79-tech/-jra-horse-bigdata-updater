#!/usr/bin/env python3
from __future__ import annotations
import json,re,sys,urllib.parse,urllib.request
from bs4 import BeautifulSoup
from pathlib import Path
sys.path.insert(0,'src')
from collect_active_elite_horses import request_profile, UA

HORSE_ID='2023106749'
OUT=Path('status/jra-corner-result-page-diagnostic.json')
BASE='https://www.jra.go.jp'

def main():
    html=request_profile(HORSE_ID)
    soup=BeautifulSoup(html,'html.parser')
    links=[]
    for a in soup.find_all('a',href=True):
        href=a['href']
        if 'accessS.html?CNAME=pw01sde' in href:
            links.append(urllib.parse.urljoin(BASE,href))
    url=links[1] if len(links)>1 else links[0]
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Referer':BASE+'/','Accept-Language':'ja'})
    with urllib.request.urlopen(req,timeout=30) as r: raw=r.read()
    text=None;enc_used=None
    for enc in ('utf-8','cp932','euc_jp'):
        try:
            cand=raw.decode(enc)
            if '通過' in cand or 'コーナー' in cand or '着順' in cand:
                text=cand;enc_used=enc;break
        except: pass
    if text is None:
        text=raw.decode('cp932','replace');enc_used='cp932-replace'
    s=BeautifulSoup(text,'html.parser')
    snippets=[]
    for tag in s.find_all(['table','section','div','tr','th','td']):
        t=' '.join(tag.stripped_strings)
        if any(k in t for k in ('通過','コーナー','着順')):
            snippets.append(t[:1200])
            if len(snippets)>=20: break
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({'horse_id':HORSE_ID,'url':url,'encoding':enc_used,'snippet_count':len(snippets),'snippets':snippets},ensure_ascii=False,indent=2))
    print(json.dumps({'url':url,'encoding':enc_used,'snippet_count':len(snippets),'snippets':snippets[:5]},ensure_ascii=False))
if __name__=='__main__':main()
