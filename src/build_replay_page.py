#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import re
from pathlib import Path

AUGUST=Path("docs/data/august-validation-archive.json")
LIVE=Path("docs/data/live_predictions_sealed.json")
OUT=Path("docs/replay/index.html")

CSS=r""":root{--bg:#f4f6f3;--paper:#fff;--ink:#101814;--muted:#69756e;--line:#dce3de;--green:#08704a;--soft:#e9f4ee;--lock:#edf0ee;--result:#fff4dc;--win:#e5f4eb;--place:#e8f2fb;--miss:#fbefed}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Hiragino Sans","Yu Gothic",sans-serif;padding-bottom:74px}.top{height:54px;position:sticky;top:0;z-index:20;display:flex;align-items:center;justify-content:space-between;padding:0 14px;background:rgba(244,246,243,.96);border-bottom:1px solid var(--line)}.top a{text-decoration:none;color:var(--ink);font-weight:900}.wrap{max-width:920px;margin:auto;padding:18px 14px 30px}.hero small{font-size:10px;color:var(--green);font-weight:900;letter-spacing:.1em}.hero h1{font-size:27px;margin:7px 0 8px}.hero p,.notice{font-size:12px;line-height:1.7;color:var(--muted)}.notice{margin:14px 0;background:#fff;border:1px solid var(--line);border-radius:14px;padding:12px}.months,.dates{display:flex;gap:8px;overflow:auto;margin:16px 0 10px}.months button,.dates button{border:1px solid var(--line);background:#fff;border-radius:999px;padding:9px 14px;font-weight:900;white-space:nowrap}.months button.active,.dates button.active{background:var(--ink);color:#fff}.months button.locked{background:var(--lock);color:#8a938e}.dates button.locked-day{background:var(--lock);color:#8a938e;border-style:dashed;cursor:not-allowed}.day-lock-note{margin:0 0 12px;padding:11px 12px;border-radius:12px;background:#fff;border:1px dashed #bfc9c2;color:#6f7a74;font-size:11px;font-weight:800}.locked-panel{position:relative;overflow:hidden;background:#fff;border:1px solid var(--line);border-radius:18px;padding:22px;margin-top:12px}.blur{filter:blur(5px);opacity:.35;user-select:none}.lock-message{position:absolute;inset:0;display:grid;place-content:center;text-align:center;font-weight:900}.lock-message span{font-size:28px}.count{font-size:10px;color:var(--muted);margin-bottom:10px}.list{display:grid;gap:10px}.race{background:#fff;border:1px solid var(--line);border-radius:17px;padding:14px}.head{display:flex;justify-content:space-between;gap:10px}.head b{font-size:17px}.head small{display:block;margin-top:4px;color:var(--muted);font-size:10px}.badge{font-size:9px;font-weight:900;background:var(--soft);color:var(--green);height:max-content;padding:5px 8px;border-radius:99px}.section{margin-top:11px;border-top:1px solid var(--line);padding-top:10px}.label{font-size:9px;color:var(--muted);font-weight:900}.axis{font-size:20px;font-weight:900;margin:4px 0}.line{font-size:11px;line-height:1.65;color:#39463f}.tickets{margin-top:7px;font-size:10px;color:var(--muted);line-height:1.7}details.result{margin-top:10px;border-radius:12px;background:var(--result);padding:0 10px;transition:background .18s ease}details.result[open]{padding-bottom:10px}details.result.win[open]{background:var(--win)}details.result.place[open]{background:var(--place)}details.result.miss[open]{background:var(--miss)}summary{cursor:pointer;list-style:none;font-size:11px;font-weight:900;padding:11px 0}summary::-webkit-details-marker{display:none}details.trio-result{margin-top:9px;border-top:1px dashed rgba(70,90,78,.22);padding-top:2px}details.trio-result summary{color:#32463b;padding:10px 0 7px}.trio-box{padding:8px 0 2px}.trio-status{font-size:12px;font-weight:900;margin-bottom:5px}.trio-payout{font-size:15px;font-weight:900;color:var(--green);margin:4px 0}.top3{font-weight:900;font-size:12px;line-height:1.7}.empty{padding:30px;text-align:center;color:var(--muted)}.mobile-nav{position:fixed;left:0;right:0;bottom:0;display:grid;grid-template-columns:repeat(4,1fr);background:rgba(255,255,255,.97);border-top:1px solid var(--line);padding-bottom:env(safe-area-inset-bottom)}.mobile-nav a{text-decoration:none;color:#5d6862;text-align:center;font-size:10px;font-weight:900;padding:12px 2px}@media(min-width:760px){body{padding-bottom:0}.mobile-nav{display:none}.list{grid-template-columns:repeat(2,1fr)}}"""

def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))

def esc(x):
    return html.escape(str(x if x is not None else ""), quote=True)

def result_class(z):
    try:
        f=int(z.get("axis_finish"))
    except Exception:
        return ""
    if f==1:
        return "win"
    if f in (2,3):
        return "place"
    return "miss" if f>=4 else ""

def result_label(z):
    try:
        f=int(z.get("axis_finish"))
    except Exception:
        return "結果照合待ち"
    return {1:"1着・的中",2:"2着・馬券内",3:"3着・馬券内"}.get(f,"4着以下・馬券外（軸不的中）")

def normalize_aug(r):
    p=dict(r.get("prediction") or {})
    p.setdefault("sealed",True)
    return {
        "date":r.get("date"),
        "track":r.get("track"),
        "race_no":r.get("race_no"),
        "race_name":r.get("race_name",""),
        "prediction":p,
        "result":r.get("result") or {}
    }

def card(r, open_month):
    p=r.get("prediction") or {}
    z=r.get("result") or {}
    date=str(r.get("date") or "")
    month=date[:7]
    top=" / ".join(
        f'{x.get("finish")}着 {x.get("horse_no")} {x.get("horse_name","")}'
        for x in (z.get("top3") or [])
    )
    sealed=p.get("sealed",True) is not False
    axis=" ".join(str(x) for x in (p.get("axis_no"),p.get("axis_name")) if x not in (None,""))
    cand="・".join(str(x) for x in (p.get("candidate") or [])) or "—"
    tickets=[str(x) for x in (p.get("tickets") or [])]

    if sealed:
        pred=f'<div class="axis">軸 {esc(axis or "—")}</div><div class="line">判定：{esc(p.get("decision") or "—")}</div><div class="line">候補：{esc(cand)}</div>'
        if tickets:
            pred+=f'<div class="tickets">推奨三連複：{" / ".join(esc(x) for x in tickets)}</div>'
    else:
        pred='<div class="line">このレースは発走前の正式封印がないため、予想成績の判定対象外です。</div>'

    has_result=len(z.get("top3") or [])>0
    if not tickets:
        trio='<details class="trio-result"><summary>推奨三連複の判定を見る ▼</summary><div class="trio-box"><div class="line">推奨三連複の発行なし</div></div></details>'
    else:
        if has_result and z.get("trio_hit") is True:
            status="◎ 推奨三連複 的中"
            payout=z.get("trio_payout")
            payout_html=f'<div class="trio-payout">払戻 {esc(payout)}</div>' if payout else ""
        elif has_result and z.get("trio_hit") is False:
            status="× 推奨三連複 不的中"
            payout_html=""
        else:
            status="結果確定待ち"
            payout_html=""
        trio=f'<details class="trio-result"><summary>推奨三連複の判定を見る ▼</summary><div class="trio-box"><div class="trio-status">{status}</div>{payout_html}<div class="tickets">推奨買い目：{" / ".join(esc(x) for x in tickets)}</div></div></details>'

    source=z.get("source")
    source_html=f'<div class="line"><a href="{esc(source)}" target="_blank" rel="noreferrer">JRA公式結果</a></div>' if source else ""
    hidden="" if month==open_month else " hidden"
    return f'''<article class="race" data-month="{esc(month)}" data-date="{esc(date)}" data-track="{esc(r.get("track"))}"{hidden}>
<div class="head"><div><b>{esc(r.get("track"))} {esc(r.get("race_no"))}R {esc(r.get("race_name") or "")}</b><small>{esc(date.replace("-","/"))}</small></div><span class="badge">{"封印AI予測" if sealed else "事前封印なし"}</span></div>
<div class="section"><div class="label">AI予測</div>{pred}</div>
<details class="result {result_class(z)}"><summary>{"軸の結果を見る ▼" if has_result else "結果確定待ち"}</summary><div class="label">JRA公式結果</div><div class="top3">{esc(top or "結果データなし")}</div><div class="line">軸結果：{esc(result_label(z))}</div>{source_html}{trio}</details>
</article>'''

def date_group(month, rows, locks, open_month):
    dates=sorted({str(r.get("date")) for r in rows},reverse=True)
    buttons=[f'<button class="active" data-select-date="ALL">全{len(rows)}R</button>']
    buttons += [
        f'<button data-select-date="{esc(d)}">{int(d[5:7])}/{int(d[8:10])}</button>'
        for d in dates
    ]
    buttons += [
        f'<button class="locked-day" type="button" disabled>🔒 {int(d[5:7])}/{int(d[8:10])}</button>'
        for d in locks.get(month,[])
    ]
    hidden="" if month==open_month else " hidden"
    return f'<div class="dates date-group" data-month="{esc(month)}"{hidden}>{"".join(buttons)}</div>'

def track_group(month, date, rows, open_month):
    tracks=sorted({str(r.get("track")) for r in rows if date=="ALL" or str(r.get("date"))==date})
    buttons=['<button class="active" data-select-track="ALL">全競馬場</button>']
    buttons += [f'<button data-select-track="{esc(t)}">{esc(t)}</button>' for t in tracks]
    hidden="" if (month==open_month and date=="ALL") else " hidden"
    return f'<div class="dates track-group" data-month="{esc(month)}" data-date="{esc(date)}"{hidden}>{"".join(buttons)}</div>'

def main():
    aug=load(AUGUST)
    aug_rows=[normalize_aug(r) for r in (aug.get("races") or [])]
    if len(aug_rows)!=360:
        raise SystemExit(f"August replay must be 360 races, got {len(aug_rows)}")

    exact_re=re.compile(r"^replay-(\d{4}-\d{2}-\d{2})\.json$")
    completed=[]
    canonical_dates=[]
    for path in sorted(Path("docs/data").glob("replay-*.json")):
        m=exact_re.match(path.name)
        if not m:
            continue
        payload=load(path)
        rows=payload.get("races") or []
        date=m.group(1)
        if not rows:
            continue
        if any(str(r.get("date"))!=date for r in rows):
            raise SystemExit(f"{path} contains mismatched date rows")
        result_count=sum(1 for r in rows if len((r.get("result") or {}).get("top3") or [])==3)
        if result_count!=len(rows):
            raise SystemExit(f"{path} contains incomplete replay rows: {result_count}/{len(rows)}")
        completed.extend(rows)
        canonical_dates.append(date)

    if not completed:
        raise SystemExit("No canonical replay-YYYY-MM-DD.json archives found")

    data={"2026-08":aug_rows}
    for r in completed:
        data.setdefault(str(r.get("date"))[:7],[]).append(r)
    for month in data:
        data[month]=sorted(data[month],key=lambda r:(str(r.get("date")),str(r.get("track")),int(r.get("race_no") or 0)))

    open_month=max(data)
    live=load(LIVE) if LIVE.exists() else {"races":[],"pending":[]}
    completed_dates={str(r.get("date")) for r in completed}
    locks={}
    for r in (live.get("races") or [])+(live.get("pending") or []):
        d=str(r.get("date") or "")
        if d and d not in completed_dates:
            locks.setdefault(d[:7],set()).add(d)
    locks={m:sorted(ds) for m,ds in locks.items()}

    open_months=sorted(data,reverse=True)
    month_buttons="".join(
        f'<button{" class=\"active\"" if m==open_month else ""} data-month="{esc(m)}">{int(m[5:7])}月</button>'
        for m in open_months
    )
    locked_months="".join(
        f'<button class="locked" data-month="2026-{m:02d}">🔒 {m}月</button>'
        for m in range(7,3,-1)
        if f"2026-{m:02d}" not in data
    )

    date_groups="".join(date_group(m,data[m],locks,open_month) for m in open_months)
    track_groups=[]
    for m in open_months:
        dates=["ALL"]+sorted({str(r.get("date")) for r in data[m]},reverse=True)
        track_groups.extend(track_group(m,d,data[m],open_month) for d in dates)

    all_rows=[]
    for m in open_months:
        all_rows.extend(data[m])
    cards="".join(card(r,open_month) for r in all_rows)
    initial_count=len(data[open_month])
    lock_note_hidden="" if locks.get(open_month) else " hidden"

    js=r'''
(function(){
"use strict";
var month=document.getElementById("replay-root").getAttribute("data-open-month");
var date="ALL",track="ALL";
function qa(s){return Array.prototype.slice.call(document.querySelectorAll(s))}
function show(el,on){el.hidden=!on}
function setActive(nodes,target,attr){
  nodes.forEach(function(b){b.classList.toggle("active",b.getAttribute(attr)===target)})
}
function currentDateGroup(){
  return document.querySelector('.date-group[data-month="'+month+'"]')
}
function currentTrackGroup(){
  return document.querySelector('.track-group[data-month="'+month+'"][data-date="'+date+'"]')
}
function refreshGroups(){
  qa(".date-group").forEach(function(g){show(g,g.getAttribute("data-month")===month)})
  qa(".track-group").forEach(function(g){show(g,g.getAttribute("data-month")===month&&g.getAttribute("data-date")===date)})
}
function refreshCards(){
  var count=0;
  qa(".race").forEach(function(r){
    var on=r.getAttribute("data-month")===month&&(date==="ALL"||r.getAttribute("data-date")===date)&&(track==="ALL"||r.getAttribute("data-track")===track);
    show(r,on); if(on)count++;
  });
  document.getElementById("count").textContent=count+"レース表示";
  var hasLocked=!!document.querySelector('.date-group[data-month="'+month+'"] .locked-day');
  show(document.getElementById("day-lock-note"),hasLocked);
}
qa("#months [data-month]").forEach(function(b){
  b.onclick=function(){
    var locked=b.classList.contains("locked");
    qa("#months button").forEach(function(x){x.classList.remove("active")});
    b.classList.add("active");
    show(document.getElementById("lockedView"),locked);
    show(document.getElementById("openView"),!locked);
    if(locked)return;
    month=b.getAttribute("data-month");date="ALL";track="ALL";
    refreshGroups();refreshCards();
  };
});
qa(".date-group [data-select-date]").forEach(function(b){
  b.onclick=function(){
    var g=b.closest(".date-group");
    date=b.getAttribute("data-select-date");track="ALL";
    setActive(qa('.date-group[data-month="'+month+'"] [data-select-date]'),date,"data-select-date");
    refreshGroups();refreshCards();
  };
});
qa(".track-group [data-select-track]").forEach(function(b){
  b.onclick=function(){
    track=b.getAttribute("data-select-track");
    setActive(qa('.track-group[data-month="'+month+'"][data-date="'+date+'"] [data-select-track]'),track,"data-select-track");
    refreshCards();
  };
});
refreshGroups();refreshCards();
})();
'''

    page=f'''<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><title>過去レースのAI予測｜JRA AI</title><meta name="robots" content="noindex,nofollow"><style>{CSS}</style></head><body>
<header class="top"><a href="../">JRA AI</a><a href="../app/">最新予想</a></header>
<main class="wrap"><section class="hero"><small>AI RACE ARCHIVE</small><h1>過去レースのAI予測</h1><p>各レース1つのAI予測を固定して保存。予測内容を見たあと、タップして実際の結果を確認できます。</p></section>
<div class="notice"><b>9/5 全36Rの結果反映済み</b><br>9月・8月を公開中。9/5はページ本体に固定保存した予想とJRA公式結果を表示します。7月以前はロック表示を維持します。</div>
<div class="months" id="months">{month_buttons}{locked_months}</div>
<div id="lockedView" class="locked-panel" hidden><div class="blur">札幌 11R　軸 7　候補 2・5・9<br>新潟 10R　軸 4　候補 1・6・12<br>中京 9R　軸 3　候補 5・8・11</div><div class="lock-message"><span>🔒</span><div>7月以前のAI予測は現在ロック中</div></div></div>
<div id="replay-root" data-open-month="{open_month}"><div id="openView">{date_groups}{"".join(track_groups)}<div id="count" class="count">{initial_count}レース表示</div><div id="day-lock-note" class="day-lock-note"{lock_note_hidden}>🔒 未終了日の予想は全レース終了までロック。終了後に封印済み予測と結果を過去レースへ移動します。</div><div id="content"><div class="list">{cards}</div></div></div></div></main>
<nav class="mobile-nav"><a href="../">ホーム</a><a href="../app/">最新予想</a><a href="../horses/">データ</a><a href="../consult/">相談</a></nav>
<script>{js}</script><script src="/-jra-horse-bigdata-updater/word-links.js"></script></body></html>'''

    checks={
        "no_loading_placeholder":"読込中" not in page,
        "no_dynamic_card_render":"innerHTML" not in js and "JSON.parse" not in js,
        "single_card_renderer":page.count('function card(')==0,
        "all_cards_static":page.count('class="race"')==len(all_rows),
        "initial_cards_visible":sum(1 for r in all_rows if str(r.get("date"))[:7]==open_month)==initial_count,
        "canonical_dates_present":all(d in page for d in canonical_dates)
    }
    if not all(checks.values()):
        raise SystemExit(f"replay generator verification failed: {checks}")

    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(page,encoding="utf-8")
    print(json.dumps({
        "status":"PASS",
        "open_month":open_month,
        "initial_visible_cards":initial_count,
        "total_static_cards":len(all_rows),
        "canonical_completed_dates":sorted(canonical_dates),
        "checks":checks
    },ensure_ascii=False))

if __name__=="__main__":
    main()
