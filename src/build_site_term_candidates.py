#!/usr/bin/env python3
import json,re
from pathlib import Path

ROOT=Path('.')
DOCS=ROOT/'docs'
REGISTERED=[DOCS/'data/glossary.json',DOCS/'data/site-terms.json']
OUT=DOCS/'data/site-term-candidates.json'
STATUS=ROOT/'status/site_term_coverage.json'

# High-signal terminology that may appear in public UI/copy. This is deliberately
# conservative: ordinary Japanese words and horse names are not auto-promoted.
PATTERNS=[
 r'[一-龯ぁ-んァ-ヶA-Za-z0-9・]+(?:確率|率|評価|分析|リスク|シナリオ|ペース|馬券|買い目|候補|適性|耐久性|競合|侵入|妙味|期待値|オッズ|展開|脚質|血統|調教|斤量|馬場|クラス|重賞|フォーメーション)',
 r'(?:単勝|複勝|馬連|馬単|ワイド|三連複|三連単|3連複|3連単|G[123]|G[ⅠⅡⅢ]|GI{1,3}|AI答え合わせ|詳細分析|AIに聞く|馬データ|出馬表|枠番|馬番|パドック|返し馬|向正面|直線|[1-4]コーナー)'
]
IGNORE_PARTS=('node_modules','data/horses','race_cards','replay-demo')

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
        if not p.is_file() or p.suffix.lower() not in ('.html','.js','.css','.json','.md'):continue
        rel=str(p).replace('\\','/')
        if any(part in rel for part in IGNORE_PARTS):continue
        if p in REGISTERED or p==OUT:continue
        if p.stat().st_size>1_000_000:continue
        yield p

def main():
    known=registered(); hits={}
    scanned=0
    for p in files():
        scanned+=1
        try:text=p.read_text(encoding='utf-8',errors='ignore')
        except Exception:continue
        for pat in PATTERNS:
            for m in re.finditer(pat,text):
                term=m.group(0).strip('「」『』【】<>/,:：。！？!?#&;=')
                # Long captures are usually prose, not terminology.
                if not term or len(term)>24:continue
                k=norm(term)
                if not k or k in known:continue
                row=hits.setdefault(k,{'term':term,'category':'サイト内候補','summary':'サイト内で使われている用語です。詳しい意味は「AIに聞く」から確認できます。','source_name':'JRA AI サイト内自動検出','occurrences':0,'pages':[]})
                row['occurrences']+=1
                rel=str(p.relative_to(DOCS)).replace('\\','/')
                if rel not in row['pages'] and len(row['pages'])<12:row['pages'].append(rel)
    rows=sorted(hits.values(),key=lambda x:(-x['occurrences'],x['term']))
    OUT.parent.mkdir(parents=True,exist_ok=True);STATUS.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps({'updated_at':'AUTO','terms':rows},ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    STATUS.write_text(json.dumps({'files_scanned':scanned,'registered_keys':len(known),'uncovered_candidates':len(rows),'top_candidates':rows[:50]},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'files_scanned':scanned,'registered_keys':len(known),'uncovered_candidates':len(rows)},ensure_ascii=False))

if __name__=='__main__':main()
