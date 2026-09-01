#!/usr/bin/env python3
import json,re
from pathlib import Path

ROOT=Path('.')
DOCS=ROOT/'docs'
REGISTERED=[DOCS/'data/glossary.json',DOCS/'data/site-terms.json']
OUT=DOCS/'data/site-term-candidates.json'
STATUS=ROOT/'status/site_term_coverage.json'
PUBLIC_PREFIXES=('index.html','app/','analysis/','horses/','consult/','about/','replay/')
SIGNALS=('確率','率','評価','分析','リスク','シナリオ','ペース','馬券','買い目','候補','適性','耐久性','競合','侵入','妙味','期待値','オッズ','展開','脚質','血統','調教','斤量','馬場','クラス','重賞','フォーメーション')
EXACT=('単勝','複勝','馬連','馬単','ワイド','三連複','三連単','3連複','3連単','G1','G2','G3','GⅠ','GⅡ','GⅢ','AI答え合わせ','詳細分析','AIに聞く','馬データ','出馬表','枠番','馬番','パドック','返し馬','向正面','直線','1コーナー','2コーナー','3コーナー','4コーナー')
BAD_FRAGMENTS=('この','その','ます','です','した','する','され','でき','ください','について','なら','とき','AIが','ユーザー','http','href','class','function','const','return')

def norm(s):
    return re.sub(r'[\s・･._\-ー()（）]','',str(s).lower())

def registered():
    names=set()
    for p in REGISTERED:
        if not p.exists():continue
        d=json.loads(p.read_text(encoding='utf-8'))
        for x in d.get('terms',[]):
            for v in [x.get('term'),*(x.get('aliases') or [])]:
                if v:names.add(norm(v))
    return names

def files():
    for p in DOCS.rglob('*'):
        if not p.is_file() or p.suffix.lower() not in ('.html','.js'):continue
        rel=str(p.relative_to(DOCS)).replace('\\','/')
        if not any(rel==x or rel.startswith(x) for x in PUBLIC_PREFIXES):continue
        if p.stat().st_size>750_000:continue
        yield p,rel

def candidate_tokens(text):
    # Strip markup separators first, then inspect short Japanese/Latin chunks.
    for token in re.findall(r'[一-龯々ぁ-んァ-ヶA-Za-z0-9ⅠⅡⅢ・（）()]{2,18}',text):
        t=token.strip('・（）()')
        if not t or len(t)>14:continue
        if any(x in t for x in BAD_FRAGMENTS):continue
        if t in EXACT or any(sig in t for sig in SIGNALS):yield t

def main():
    known=registered();hits={};scanned=0
    for p,rel in files():
        scanned+=1
        try:text=p.read_text(encoding='utf-8',errors='ignore')
        except Exception:continue
        for term in candidate_tokens(text):
            k=norm(term)
            if not k or k in known:continue
            # If the whole token is merely a decorated occurrence of a registered
            # term, prefer the registered canonical entry rather than a duplicate.
            if any(len(k)>len(x)>=3 and (k.endswith(x) or k.startswith(x)) for x in known):
                if not any(sig in term for sig in ('候補','リスク','評価','分析','確率','適性','競合','侵入')):continue
            row=hits.setdefault(k,{'term':term,'category':'サイト内候補','summary':'サイト内で使われている用語です。詳しい意味は「AIに聞く」から確認できます。','source_name':'JRA AI サイト内自動検出','occurrences':0,'pages':[]})
            row['occurrences']+=1
            if rel not in row['pages'] and len(row['pages'])<10:row['pages'].append(rel)
    rows=sorted(hits.values(),key=lambda x:(-x['occurrences'],x['term']))
    OUT.parent.mkdir(parents=True,exist_ok=True);STATUS.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps({'updated_at':'AUTO','terms':rows},ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    STATUS.write_text(json.dumps({'files_scanned':scanned,'registered_keys':len(known),'uncovered_candidates':len(rows),'top_candidates':rows[:50]},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'files_scanned':scanned,'registered_keys':len(known),'uncovered_candidates':len(rows)},ensure_ascii=False))

if __name__=='__main__':main()
