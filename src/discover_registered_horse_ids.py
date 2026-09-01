#!/usr/bin/env python3
"""Discover JRA current registered horse profile IDs from official roster PDFs.

The JRA registered-horse roster is split across eight PDFs (Miho/Ritto,
2yo/3yo+). We inspect PDF link annotations for official accessU profile URIs.
If the PDFs do not expose hyperlinks, the status file records that fact rather
than inventing IDs; another authoritative resolver can then be added.
"""
import csv,json,re,urllib.parse,urllib.request
from pathlib import Path
from pypdf import PdfReader

PDFS={
 'miho2':'https://www.jra.go.jp/datafile/resist/pdf/registration_miho2.pdf',
 'miho3-1':'https://www.jra.go.jp/datafile/resist/pdf/registration_miho3-1.pdf',
 'miho3-2':'https://www.jra.go.jp/datafile/resist/pdf/registration_miho3-2.pdf',
 'miho3-3':'https://www.jra.go.jp/datafile/resist/pdf/registration_miho3-3.pdf',
 'ritto2':'https://www.jra.go.jp/datafile/resist/pdf/registration_ritto2.pdf',
 'ritto3-1':'https://www.jra.go.jp/datafile/resist/pdf/registration_ritto3-1.pdf',
 'ritto3-2':'https://www.jra.go.jp/datafile/resist/pdf/registration_ritto3-2.pdf',
 'ritto3-3':'https://www.jra.go.jp/datafile/resist/pdf/registration_ritto3-3.pdf',
}
CACHE=Path('cache/jra_registered_roster');OUT=Path('data/current_registered_horse_ids.csv');STATUS=Path('status/current_registered_roster.json')
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36'
ID_RE=re.compile(r'(pw01dud(?:00|10)\d{12}/[A-Fa-f0-9]{2})')


def fetch(key,url):
    CACHE.mkdir(parents=True,exist_ok=True);p=CACHE/f'{key}.pdf'
    if p.exists() and p.stat().st_size>100_000:return p
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Referer':'https://www.jra.go.jp/datafile/resist/'})
    with urllib.request.urlopen(req,timeout=90) as r:p.write_bytes(r.read())
    return p


def annotation_uris(pdf):
    reader=PdfReader(str(pdf));uris=[]
    for page_no,page in enumerate(reader.pages):
        for ref in page.get('/Annots') or []:
            try:a=ref.get_object();action=a.get('/A') or {};uri=action.get('/URI')
            except Exception:continue
            if uri:uris.append((page_no,str(uri)))
    return uris,len(reader.pages)


def main():
    STATUS.parent.mkdir(exist_ok=True);rows={};report=[]
    for key,url in PDFS.items():
        try:
            path=fetch(key,url);uris,pages=annotation_uris(path);ids=[]
            for page,uri in uris:
                decoded=urllib.parse.unquote(uri)
                m=ID_RE.search(decoded)
                if not m:continue
                hid=m.group(1);ids.append(hid);rows.setdefault(hid,{'horse_id':hid,'roster_parts':set(),'profile_url':uri})['roster_parts'].add(key)
            report.append({'part':key,'pages':pages,'annotations':len(uris),'profile_ids':len(set(ids)),'status':'OK'})
        except Exception as e:report.append({'part':key,'status':'ERROR','error':repr(e)})
    OUT.parent.mkdir(exist_ok=True)
    with OUT.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['horse_id','roster_parts','profile_url']);w.writeheader()
        for hid,r in sorted(rows.items()):w.writerow({'horse_id':hid,'roster_parts':'|'.join(sorted(r['roster_parts'])),'profile_url':r['profile_url']})
    state={'source':'JRA_REGISTERED_HORSE_ROSTER_PDFS','pdf_parts':report,'registered_profile_ids':len(rows),
           'status':'PASS' if rows else 'NO_PROFILE_LINKS_IN_PDF'}
    STATUS.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(state,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
