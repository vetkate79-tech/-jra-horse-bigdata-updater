#!/usr/bin/env python3
import json,re,html,shutil
from pathlib import Path
from collections import defaultdict

ROOT=Path('.')
DOCS=ROOT/'docs'
SOURCES=[DOCS/'data/glossary.json',DOCS/'data/site-terms.json',DOCS/'data/site-terms-extra.json',DOCS/'data/jra-official-terms.json']
OUT=DOCS/'words'
INDEX=DOCS/'data/word-index.json'
DOMESTIC_CATEGORY_ORDER=[
    'レース、騎乗技術など','レースの種類、条件など','馬の癖','競馬で使用する様々な道具',
    '勝馬投票券関係、投票関係','調教関係','生産、育成関係、飼糧など','血統、馬の種類など',
    '競馬場などの施設、設備','競馬関係の組織、団体、会議など','競馬史上のもの（現存のものは除く）',
    '競馬に関わる人々','競馬関係の法律、施行規程、公正確保など','厩舎ことば',
    '馬体の各部位、特徴、個体の分類など','馬の病気、ケガ、能力をそこなうものなど',
    '資格・成績・ランキング・表彰など','馬の脚質、あしいろ、歩様、距離特性など',
    'JRA主催のイベント、ファンサービスなど','その他',
]
OVERSEAS_CATEGORY_ORDER=[
    '競馬場施設','牧場、厩舎','競走馬','出馬表','馬、獣医','競走','調教','馬券関係','騎手装具他','馬装具',
]
CATEGORY_ORDER=DOMESTIC_CATEGORY_ORDER+OVERSEAS_CATEGORY_ORDER
OFFICIAL_CATEGORIES=set(CATEGORY_ORDER)
LOCAL_CATEGORY_MAP={
    '馬券':'勝馬投票券関係、投票関係','市場':'勝馬投票券関係、投票関係',
    'クラス':'レースの種類、条件など','レース条件':'レースの種類、条件など',
    '重賞':'レースの種類、条件など','新馬':'レースの種類、条件など','出馬表':'レースの種類、条件など',
    'ペース':'レース、騎乗技術など','レース展開':'レース、騎乗技術など',
    '展開':'レース、騎乗技術など','レース':'レース、騎乗技術など',
    '予想':'レース、騎乗技術など','詳細分析':'レース、騎乗技術など',
    '能力':'レース、騎乗技術など','レース前':'レース、騎乗技術など',
    '脚質':'馬の脚質、あしいろ、歩様、距離特性など','成績':'資格・成績・ランキング・表彰など',
    'コース':'競馬場などの施設、設備','血統':'血統、馬の種類など',
    '血統・調教':'調教関係','サイト機能':'その他','AI・機能':'その他',
    'AI答え合わせ':'その他','馬データ':'その他','競馬用語':'その他',
}

def norm(s): return re.sub(r'[\s・･._\-ー()（）]','',str(s or '').lower())
def slug(term): return 't-' + str(term).encode('utf-8').hex()

def load_terms():
    by={}
    for src in SOURCES:
        if not src.exists(): continue
        doc=json.loads(src.read_text(encoding='utf-8'))
        for x in doc.get('terms',[]):
            if not x.get('term'): continue
            summary=(x.get('summary') or x.get('short_definition') or '').strip()
            if not summary or 'AIに聞' in summary: continue
            k=norm(x['term']);old=by.get(k,{})
            aliases=list(dict.fromkeys([*(old.get('aliases') or []),*(x.get('aliases') or [])]))
            by[k]={**old,**x,'summary':summary,'aliases':aliases}
    return sorted(by.values(),key=lambda x:str(x.get('term','')))

def categories(t):
    raw=t.get('categories')
    if not raw:
        raw=[x.strip() for x in str(t.get('category') or 'その他').split(' / ') if x.strip()]
    elif isinstance(raw,str):
        raw=[x.strip() for x in raw.split(' / ') if x.strip()]
    mapped=[]
    for value in raw:
        official=value if value in OFFICIAL_CATEGORIES else LOCAL_CATEGORY_MAP.get(value,'その他')
        if official not in mapped: mapped.append(official)
    return mapped or ['その他']

def category_label(t): return ' / '.join(categories(t))

def base_css():
    return '''<style>:root{--bg:#f7f8fb;--paper:#fff;--ink:#17202a;--muted:#6d7784;--line:#e2e7ee;--blue:#2563a8;--soft:#eef5ff}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Hiragino Sans","Yu Gothic",sans-serif}.wrap{max-width:900px;margin:auto;padding:18px 15px 80px}.top{display:flex;justify-content:space-between;align-items:center;padding:10px 0}.top a{text-decoration:none;color:var(--ink);font-weight:900}.hero{padding:20px 0}.hero h1{font-size:30px;margin:0 0 8px;color:var(--ink)}.hero p{color:var(--muted);font-size:13px;line-height:1.7}.search{width:100%;padding:14px;border:1px solid var(--line);border-radius:14px;background:var(--paper);font-size:16px}.cats{display:flex;gap:7px;overflow:auto;padding:12px 0}.chip{border:1px solid #cbd9eb;background:#fff;color:var(--ink);border-radius:999px;padding:8px 11px;white-space:nowrap;font-weight:800;font-size:12px}.group{margin-top:20px}.group h2{font-size:17px;margin:0 0 9px;color:var(--ink)}.grid{display:grid;gap:8px}.term{display:block;text-decoration:none;color:var(--ink);background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:13px}.term b{color:var(--ink)}.term small{display:block;color:var(--muted);margin-top:4px}.empty{color:var(--muted);font-size:13px;margin:0;padding:12px 0}.reading{color:var(--muted);font-size:11px}.summary{font-size:14px;line-height:1.85}.aliases{background:var(--soft);padding:10px 12px;border-radius:12px;color:#345b83;font-size:12px}.back{display:inline-block;color:var(--blue);font-weight:800;text-decoration:none;margin-top:18px}@media(min-width:700px){.grid{grid-template-columns:repeat(2,1fr)}}</style>'''

def write_index(terms):
    groups=defaultdict(list)
    for t in terms:
        for c in categories(t): groups[c].append(t)
    unknown=set(groups)-OFFICIAL_CATEGORIES
    if unknown: raise RuntimeError(f'non-JRA categories: {sorted(unknown)}')
    ordered=CATEGORY_ORDER
    cards=[]
    for c in ordered:
        items=''.join(f'<a class="term" data-term="{html.escape(norm(t["term"]))}" data-cat="{html.escape(c)}" href="./{slug(t["term"])}/"><b>{html.escape(t["term"])}</b><small>{html.escape(t.get("reading") or "")}　{html.escape(t.get("summary") or "")}</small></a>' for t in groups[c])
        if not items: items='<p class="empty">現在登録されている用語はありません</p>'
        cards.append(f'<section class="group" data-group="{html.escape(c)}"><h2>{html.escape(c)} <small>{len(groups[c])}語</small></h2><div class="grid">{items}</div></section>')
    chips=''.join(f'<button class="chip" data-filter="{html.escape(c)}">{html.escape(c)} {len(groups[c])}</button>' for c in ordered)
    page=f'''<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>競馬ワード索引｜JRA AI</title>{base_css()}</head><body><main class="wrap"><header class="top"><a href="../">JRA AI</a><a href="../consult/">AIに相談</a></header><section class="hero"><h1>競馬ワード索引</h1><p>JRA公式「競馬用語辞典」と「海外競馬英和辞典」のカテゴリーに準拠して探せます。</p></section><input id="q" class="search" type="search" placeholder="ワード・読み方・関連語を検索"><div class="cats"><button class="chip" data-filter="ALL">すべて {len(terms)}</button>{chips}</div><div id="groups">{''.join(cards)}</div></main><script>const q=document.querySelector('#q');let cat='ALL';function n(s){{return String(s||'').normalize('NFKC').toLowerCase().replace(/[\\s・･._\\-ー()（）]/g,'')}}function run(){{const z=n(q.value);document.querySelectorAll('.term').forEach(a=>{{const okCat=cat==='ALL'||a.dataset.cat===cat;const okQ=!z||n(a.textContent).includes(z);a.style.display=okCat&&okQ?'block':'none'}});document.querySelectorAll('.group').forEach(g=>{{const has=[...g.querySelectorAll('.term')].some(a=>a.style.display!=='none');const empty=g.querySelector('.empty');const showEmpty=!!empty&&!z&&(cat==='ALL'||g.dataset.group===cat);g.style.display=has||showEmpty?'block':'none'}})}}q.oninput=run;document.querySelectorAll('[data-filter]').forEach(b=>b.onclick=()=>{{cat=b.dataset.filter;run()}})</script></body></html>'''
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'index.html').write_text(page,encoding='utf-8')

def write_term_pages(terms):
    expected={slug(t['term']) for t in terms}
    if OUT.exists():
        for d in OUT.iterdir():
            if d.is_dir() and d.name not in expected:
                shutil.rmtree(d)
    for t in terms:
        d=OUT/slug(t['term']); d.mkdir(parents=True,exist_ok=True)
        aliases=t.get('aliases') or [];source=''
        if t.get('source_url'): source=f'<p><a class="back" href="{html.escape(t["source_url"])}" target="_blank" rel="noopener">出典：{html.escape(t.get("source_name") or "参照元")}</a></p>'
        page=f'''<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(t['term'])}とは｜JRA AI 競馬ワード</title>{base_css()}</head><body><main class="wrap"><header class="top"><a href="../../">JRA AI</a><a href="../">ワード索引</a></header><section class="hero"><div class="reading">{html.escape(t.get('reading') or '')}</div><h1>{html.escape(t['term'])}</h1><p>{html.escape(category_label(t))}</p></section><section class="term"><p class="summary" data-word-links-scope>{html.escape(t['summary'])}</p>{f'<div class="aliases">関連語：{html.escape("・".join(aliases))}</div>' if aliases else ''}{source}</section><a class="back" href="../">← ワード索引へ戻る</a></main><script src="/-jra-horse-bigdata-updater/word-links.js"></script></body></html>'''
        (d/'index.html').write_text(page,encoding='utf-8')

def main():
    terms=load_terms();write_index(terms);write_term_pages(terms)
    INDEX.parent.mkdir(parents=True,exist_ok=True)
    INDEX.write_text(json.dumps({'count':len(terms),'category_standard':'JRA','category_order':CATEGORY_ORDER,'terms':[{'term':t['term'],'reading':t.get('reading'),'category':categories(t)[0],'categories':categories(t),'aliases':t.get('aliases') or [],'url':f'words/{slug(t["term"])}/'} for t in terms]},ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    generated={d.name for d in OUT.iterdir() if d.is_dir() and (d/'index.html').exists()}
    expected={slug(t['term']) for t in terms}
    if generated!=expected:
        raise RuntimeError(f'dictionary page mismatch: expected={len(expected)} generated={len(generated)}')
    used={c for t in terms for c in categories(t)}
    print(json.dumps({'terms':len(terms),'category_standard':'JRA','categories':len(CATEGORY_ORDER),'used_categories':len(used),'generated_pages':len(generated),'stale_pages':0},ensure_ascii=False))
if __name__=='__main__':main()
