#!/usr/bin/env python3
import re
from bs4 import BeautifulSoup
import collect_active_elite_horses as elite

hid='pw01dud102024105568/6D'
html=elite.request_profile(hid)
soup=BeautifulSoup(html,'html.parser')
print('TITLE=', soup.title.get_text(' ',strip=True) if soup.title else '')
for m in soup.find_all('meta'):
    if m.get('property') in ('og:title','twitter:title') or m.get('name') in ('description','keywords'):
        print('META',m.get('property') or m.get('name'),'=',m.get('content'))
print('\n=== LABEL NODES ===')
for pat in ('収得賞金','競走馬情報','抹消年月日','馬主名','生年月日'):
    print('\nLABEL',pat)
    count=0
    for node in soup.find_all(string=re.compile(pat)):
        p=node.parent
        print('TAG=',p.name,'CLASS=',p.get('class'),'TEXT=',re.sub(r'\s+',' ',p.get_text(' ',strip=True))[:500])
        if p.parent:
            print('PARENT=',p.parent.name,p.parent.get('class'),re.sub(r'\s+',' ',p.parent.get_text(' ',strip=True))[:800])
        count+=1
        if count>=8:break
print('\n=== GRADE IMAGES ===')
count=0
for img in soup.find_all('img'):
    alt=str(img.get('alt') or '')
    src=str(img.get('src') or '')
    if re.search(r'G[ⅠⅡⅢ123]|grade|jgrade|listed',alt+' '+src,re.I):
        print('IMG alt=',alt,'src=',src,'parent=',re.sub(r'\s+',' ',img.parent.get_text(' ',strip=True))[:500] if img.parent else '')
        count+=1
        if count>=30:break
print('GRADE_IMG_COUNT_SHOWN',count)
print('\n=== POSSIBLE HORSE HEADERS ===')
for tag in soup.find_all(['h1','h2','h3','strong','span','p']):
    txt=re.sub(r'\s+',' ',tag.get_text(' ',strip=True))
    if '(JPN)' in txt or '（JPN）' in txt or '競走馬情報' in txt:
        print(tag.name,tag.get('class'),txt[:700])
