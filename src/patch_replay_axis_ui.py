#!/usr/bin/env python3
from pathlib import Path

P=Path('docs/replay/index.html')
s=P.read_text()

s=s.replace("let races=[],date='ALL';","let races=[],axisResults=new Map(),date='ALL';")
s=s.replace("const arr=v=>Array.isArray(v)?v:[];","const arr=v=>Array.isArray(v)?v:[];const rk=r=>`${r.date}|${r.track}|${Number(r.race_no||0)}`;")
s=s.replace("<p>発走前にどう見ていたかをそのまま残します。的中・不的中より、本命・相手・穴の考え方が主役です。</p>","<p>発走前にどう見ていたかをそのまま残します。結果は払戻より、どの人気の馬を軸にして何着だったかを中心に確認します。</p>")
s=s.replace("<div class=\"notice\">2026年3月〜12月を月ごとに表示します。常に直近2か月分は閲覧可能で、それより前の月は過去アーカイブとして非公開表示になります。</div>","<div class=\"notice\">結果評価は軸馬基準です。◎＝軸馬1着、△＝軸馬2〜3着、×＝軸馬4着以下。人気は結果確認専用で、事前予想には使用しません。</div>")

# Add axis-result styling without changing unrelated page design.
needle='.premium{position:relative;'
if '.axis-result{' not in s:
    css='.result.place{background:#fff7df}.result.place .result-top b{color:#9a6a00}.axis-result{margin-top:8px;font-size:17px;font-weight:900}.axis-pop{font-size:11px;font-weight:900;background:#fff;border:1px solid var(--line);padding:5px 8px;border-radius:999px;white-space:nowrap}'
    s=s.replace(needle,css+needle)

start=s.index('function card(r){')
end=s.index('function render(){',start)
new_card=r'''function axisResultBlock(r){const a=axisResults.get(rk(r));if(!a||!a.matched)return arr(r.result_top3).length?`<details class="result-details"><summary>結果を確認する</summary><div class="result"><div class="result-top"><b>結果判定待ち</b></div><div class="result-ranks">${arr(r.result_top3).map((x,i)=>`${i+1}着 ${esc(x)}`).join('<br>')}</div></div></details>`:'';const cls=a.evaluation==='HIT'?'hit':a.evaluation==='PLACE'?'place':'miss';const pop=a.popularity?`${a.popularity}番人気`:'人気不明';return `<details class="result-details"><summary>結果を確認する</summary><div class="result ${cls}"><div class="result-top"><b>${esc(a.symbol)} ${esc(a.label)}</b><span class="axis-pop">軸 ${esc(pop)}</span></div><div class="axis-result">${esc(a.horse_name||a.axis_horse_name)} → ${a.finish?esc(a.finish)+'着':'着順不明'}</div><div class="result-ranks">${arr(r.result_top3).map((x,i)=>`${i+1}着 ${esc(x)}`).join('<br>')}</div></div></details>`}
function card(r){return `<article class="race"><div class="head"><div><b>${esc(r.track)} ${r.race_no}R ${esc(r.race_name||'')}</b><small>${r.date.replaceAll('-','/')} · ${esc(r.surface||'')} ${r.distance_m?esc(r.distance_m)+'m':''}</small></div><span class="badge">${esc(r.type_label||'事前予想')}</span></div><section class="pre"><small>発走前の見立て</small><div class="axis-label">本命・中心</div><div class="axis">${esc(r.axis||'記録あり')}</div><div class="line"><b>相手</b> ${arr(r.partners).map(esc).join(' / ')||'記録なし'}</div><div class="line"><b>穴</b> ${arr(r.holes).map(esc).join(' / ')||'記録なし'}</div>${r.pre_note?`<div class="note">${esc(r.pre_note)}</div>`:''}${r.formation?`<div class="ticket">${esc(r.formation)}${r.ticket_count?`<br>${r.ticket_count}点`:''}</div>`:''}</section>${axisResultBlock(r)}</article>`}'''
s=s[:start]+new_card+s[end:]

old="fetch('../data/replay-demo-2026-08-29-30.json',{cache:'no-store'}).then(r=>r.json()).then(d=>{races=d.races||[];monthTabs();render()});"
new="Promise.all([fetch('../data/replay-demo-2026-08-29-30.json',{cache:'no-store'}).then(r=>r.json()),fetch('../data/replay-axis-results.json',{cache:'no-store'}).then(r=>r.ok?r.json():({rows:[]})).catch(()=>({rows:[]}))]).then(([d,a])=>{races=d.races||[];axisResults=new Map((a.rows||[]).map(x=>[`${x.date}|${x.track}|${Number(x.race_no||0)}`,x]));monthTabs();render()});"
if old in s:s=s.replace(old,new)
elif 'replay-axis-results.json' not in s:raise RuntimeError('replay fetch pattern not found')

P.write_text(s)
print({'patched':str(P),'axis_ui':True})
