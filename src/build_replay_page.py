#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import re
from pathlib import Path

AUGUST=Path("docs/data/august-validation-archive.json")
SEPT=Path("docs/data/replay-2026-09-05.json")
OUT=Path("docs/replay/index.html")

CSS=r""":root{--bg:#f4f6f3;--paper:#fff;--ink:#101814;--muted:#69756e;--line:#dce3de;--green:#08704a;--soft:#e9f4ee;--lock:#edf0ee;--result:#fff4dc;--win:#e5f4eb;--place:#e8f2fb;--miss:#fbefed}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Hiragino Sans","Yu Gothic",sans-serif;padding-bottom:74px}.top{height:54px;position:sticky;top:0;z-index:20;display:flex;align-items:center;justify-content:space-between;padding:0 14px;background:rgba(244,246,243,.96);border-bottom:1px solid var(--line)}.top a{text-decoration:none;color:var(--ink);font-weight:900}.wrap{max-width:920px;margin:auto;padding:18px 14px 30px}.hero small{font-size:10px;color:var(--green);font-weight:900;letter-spacing:.1em}.hero h1{font-size:27px;margin:7px 0 8px}.hero p,.notice{font-size:12px;line-height:1.7;color:var(--muted)}.notice{margin:14px 0;background:#fff;border:1px solid var(--line);border-radius:14px;padding:12px}.months,.dates{display:flex;gap:8px;overflow:auto;margin:16px 0 10px}.months button,.dates button{border:1px solid var(--line);background:#fff;border-radius:999px;padding:9px 14px;font-weight:900;white-space:nowrap}.months button.active,.dates button.active{background:var(--ink);color:#fff}.months button.locked{background:var(--lock);color:#8a938e}.dates button.locked-day{background:var(--lock);color:#8a938e;border-style:dashed;cursor:not-allowed}.day-lock-note{margin:0 0 12px;padding:11px 12px;border-radius:12px;background:#fff;border:1px dashed #bfc9c2;color:#6f7a74;font-size:11px;font-weight:800}.locked-panel{position:relative;overflow:hidden;background:#fff;border:1px solid var(--line);border-radius:18px;padding:22px;margin-top:12px}.blur{filter:blur(5px);opacity:.35;user-select:none}.lock-message{position:absolute;inset:0;display:grid;place-content:center;text-align:center;font-weight:900}.lock-message span{font-size:28px}.count{font-size:10px;color:var(--muted);margin-bottom:10px}.list{display:grid;gap:10px}.race{background:#fff;border:1px solid var(--line);border-radius:17px;padding:14px}.head{display:flex;justify-content:space-between;gap:10px}.head b{font-size:17px}.head small{display:block;margin-top:4px;color:var(--muted);font-size:10px}.badge{font-size:9px;font-weight:900;background:var(--soft);color:var(--green);height:max-content;padding:5px 8px;border-radius:99px}.section{margin-top:11px;border-top:1px solid var(--line);padding-top:10px}.label{font-size:9px;color:var(--muted);font-weight:900}.axis{font-size:20px;font-weight:900;margin:4px 0}.line{font-size:11px;line-height:1.65;color:#39463f}.tickets{margin-top:7px;font-size:10px;color:var(--muted);line-height:1.7}details.result{margin-top:10px;border-radius:12px;background:var(--result);padding:0 10px;transition:background .18s ease}details.result[open]{padding-bottom:10px}details.result.win[open]{background:var(--win)}details.result.place[open]{background:var(--place)}details.result.miss[open]{background:var(--miss)}summary{cursor:pointer;list-style:none;font-size:11px;font-weight:900;padding:11px 0}summary::-webkit-details-marker{display:none}details.trio-result{margin-top:9px;border-top:1px dashed rgba(70,90,78,.22);padding-top:2px}details.trio-result summary{color:#32463b;padding:10px 0 7px}.trio-box{padding:8px 0 2px}.trio-status{font-size:12px;font-weight:900;margin-bottom:5px}.trio-payout{font-size:15px;font-weight:900;color:var(--green);margin:4px 0}.top3{font-weight:900;font-size:12px;line-height:1.7}.empty{padding:30px;text-align:center;color:var(--muted)}.mobile-nav{position:fixed;left:0;right:0;bottom:0;display:grid;grid-template-columns:repeat(4,1fr);background:rgba(255,255,255,.97);border-top:1px solid var(--line);padding-bottom:env(safe-area-inset-bottom)}.mobile-nav a{text-decoration:none;color:#5d6862;text-align:center;font-size:10px;font-weight:900;padding:12px 2px}@media(min-width:760px){body{padding-bottom:0}.mobile-nav{display:none}.list{grid-template-columns:repeat(2,1fr)}}"""

def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))

def esc(x):
    return html.escape(str(x if x is not None else ""), quote=True)

def result_class(z):
    try:f=int(z.get("axis_finish"))
    except Exception:return ""
    if f==1:return "win"
    if f in (2,3):return "place"
    if f>=4:return "miss"
    return ""

def result_label(z):
    try:f=int(z.get("axis_finish"))
    except Exception:return "結果照合待ち"
    return {1:"1着・的中",2:"2着・馬券内",3:"3着・馬券内"}.get(f,"4着以下・馬券外（軸不的中）")

def card(r):
    p=r.get("prediction") or {}
    z=r.get("result") or {}
    top=" / ".join(f'{x.get("finish")}着 {x.get("horse_no")} {x.get("horse_name","")}' for x in (z.get("top3") or []))
    sealed=p.get("sealed",True) is not False
    axis=" ".join(str(x) for x in (p.get("axis_no"),p.get("axis_name")) if x not in (None,""))
    cand="・".join(str(x) for x in (p.get("candidate") or [])) or "—"
    tickets=[str(x) for x in (p.get("tickets") or [])]
    has_result=len(z.get("top3") or [])>0
    if sealed:
        pred=f'<div class="axis">軸 {esc(axis or "—")}</div><div class="line">判定：{esc(p.get("decision") or "—")}</div><div class="line">候補：{esc(cand)}</div>'
        if tickets: pred+=f'<div class="tickets">推奨三連複：{" / ".join(esc(x) for x in tickets)}</div>'
    else:
        pred='<div class="line">このレースは発走前の正式封印がないため、予想成績の判定対象外です。</div>'
    if tickets:
        if has_result and z.get("trio_hit") is True:
            status="◎ 推奨三連複 的中"
            payout=z.get("trio_payout")
            payout_html=f'<div class="trio-payout">払戻 {esc(payout)}</div>' if payout else ""
        elif has_result and z.get("trio_hit") is False:
            status="× 推奨三連複 不的中"; payout_html=""
        else:
            status="結果確定待ち"; payout_html=""
        trio=f'<details class="trio-result"><summary>推奨三連複の判定を見る ▼</summary><div class="trio-box"><div class="trio-status">{status}</div>{payout_html}<div class="tickets">推奨買い目：{" / ".join(esc(x) for x in tickets)}</div></div></details>'
    else:
        trio='<details class="trio-result"><summary>推奨三連複の判定を見る ▼</summary><div class="trio-box"><div class="line">推奨三連複の発行なし</div></div></details>'
    source=z.get("source")
    source_html=f'<div class="line"><a href="{esc(source)}" target="_blank" rel="noreferrer">JRA公式結果</a></div>' if source else ""
    return f'''<article class="race" data-date="{esc(r.get("date"))}" data-track="{esc(r.get("track"))}">
<div class="head"><div><b>{esc(r.get("track"))} {esc(r.get("race_no"))}R {esc(r.get("race_name") or "")}</b><small>{esc(str(r.get("date") or "").replace("-","/"))}</small></div><span class="badge">{"封印AI予測" if sealed else "事前封印なし"}</span></div>
<div class="section"><div class="label">AI予測</div>{pred}</div>
<details class="result {result_class(z)}"><summary>{"軸の結果を見る ▼" if has_result else "結果確定待ち"}</summary><div class="label">JRA公式結果</div><div class="top3">{esc(top or "結果データなし")}</div><div class="line">軸結果：{esc(result_label(z))}</div>{source_html}{trio}</details>
</article>'''

def normalize_aug(r):
    p=dict(r.get("prediction") or {})
    p.setdefault("sealed",True)
    return {"date":r.get("date"),"track":r.get("track"),"race_no":r.get("race_no"),"race_name":r.get("race_name",""),"prediction":p,"result":r.get("result") or {}}

def main():
    sept=load(SEPT)
    sep_rows=sept.get("races") or []
    if len(sep_rows)!=36:
        raise SystemExit(f"9/5 replay must be 36 races, got {len(sep_rows)}")
    if sum(1 for r in sep_rows if len((r.get("result") or {}).get("top3") or [])==3)!=36:
        raise SystemExit("9/5 replay must have 36 completed results")
    aug=load(AUGUST)
    aug_rows=[normalize_aug(r) for r in (aug.get("races") or [])]
    if len(aug_rows)!=360:
        raise SystemExit(f"August replay must be 360 races, got {len(aug_rows)}")

    data={"2026-09":sep_rows,"2026-08":aug_rows}
    initial=sorted(sep_rows,key=lambda r:(str(r.get("track")),int(r.get("race_no") or 0)))
    initial_cards="".join(card(r) for r in initial)
    embedded=json.dumps(data,ensure_ascii=False,separators=(",",":")).replace("<","\\u003c")

    js=r'''
(function(){
"use strict";
var DATA=JSON.parse(document.getElementById("replay-data").textContent);
var month="2026-09", date="ALL", track="ALL";
function q(s){return document.querySelector(s)}
function qa(s){return Array.prototype.slice.call(document.querySelectorAll(s))}
function e(s){return String(s==null?"":s).replace(/[&<>"']/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[c]})}
function rclass(z){var f=Number(z.axis_finish);if(f===1)return"win";if(f===2||f===3)return"place";if(isFinite(f)&&f>=4)return"miss";return""}
function rlabel(z){var f=Number(z.axis_finish);if(f===1)return"1着・的中";if(f===2)return"2着・馬券内";if(f===3)return"3着・馬券内";if(isFinite(f)&&f>=4)return"4着以下・馬券外（軸不的中）";return"結果照合待ち"}
function card(r){
 var p=r.prediction||{},z=r.result||{},sealed=p.sealed!==false,t=z.top3||[],tickets=p.tickets||[];
 var top=t.map(function(x){return x.finish+"着 "+x.horse_no+" "+(x.horse_name||"")}).join(" / ");
 var axis=[p.axis_no,p.axis_name].filter(function(x){return x!==undefined&&x!==null&&x!==""}).join(" ");
 var cand=(p.candidate||[]).join("・")||"—";
 var pred=sealed?'<div class="axis">軸 '+e(axis||"—")+'</div><div class="line">判定：'+e(p.decision||"—")+'</div><div class="line">候補：'+e(cand)+'</div>':'<div class="line">このレースは発走前の正式封印がないため、予想成績の判定対象外です。</div>';
 if(sealed&&tickets.length)pred+='<div class="tickets">推奨三連複：'+tickets.map(e).join(" / ")+'</div>';
 var trio='<details class="trio-result"><summary>推奨三連複の判定を見る ▼</summary><div class="trio-box">';
 if(!tickets.length)trio+='<div class="line">推奨三連複の発行なし</div>';
 else{
   var st=(t.length&&z.trio_hit===true)?"◎ 推奨三連複 的中":(t.length&&z.trio_hit===false)?"× 推奨三連複 不的中":"結果確定待ち";
   trio+='<div class="trio-status">'+st+'</div>';
   if(t.length&&z.trio_hit===true&&z.trio_payout)trio+='<div class="trio-payout">払戻 '+e(z.trio_payout)+'</div>';
   trio+='<div class="tickets">推奨買い目：'+tickets.map(e).join(" / ")+'</div>';
 }
 trio+='</div></details>';
 var src=z.source?'<div class="line"><a href="'+e(z.source)+'" target="_blank" rel="noreferrer">JRA公式結果</a></div>':"";
 return '<article class="race"><div class="head"><div><b>'+e(r.track)+' '+e(r.race_no)+'R '+e(r.race_name||"")+'</b><small>'+e(String(r.date||"").replace(/-/g,"/"))+'</small></div><span class="badge">'+(sealed?"封印AI予測":"事前封印なし")+'</span></div><div class="section"><div class="label">AI予測</div>'+pred+'</div><details class="result '+rclass(z)+'"><summary>'+((t.length)?"軸の結果を見る ▼":"結果確定待ち")+'</summary><div class="label">JRA公式結果</div><div class="top3">'+e(top||"結果データなし")+'</div><div class="line">軸結果：'+e(rlabel(z))+'</div>'+src+trio+'</details></article>';
}
function base(){return DATA[month]||[]}
function dates(){
 var ds=[];base().forEach(function(r){if(ds.indexOf(r.date)<0)ds.push(r.date)});ds.sort().reverse();
 q("#dates").innerHTML='<button class="'+(date==="ALL"?"active":"")+'" data-date="ALL">全'+base().length+'R</button>'+ds.map(function(d){return '<button class="'+(date===d?"active":"")+'" data-date="'+e(d)+'">'+Number(d.slice(5,7))+'/'+Number(d.slice(8))+'</button>'}).join("")+(month==="2026-09"?'<button class="locked-day" type="button" disabled>🔒 9/6</button>':"");
 qa("#dates [data-date]").forEach(function(b){b.onclick=function(){date=b.getAttribute("data-date");track="ALL";dates();tracks();render()}})
}
function tracks(){
 var ts=[],rows=base().filter(function(r){return date==="ALL"||r.date===date});
 rows.forEach(function(r){if(ts.indexOf(r.track)<0)ts.push(r.track)});ts.sort();
 q("#tracks").innerHTML='<button class="'+(track==="ALL"?"active":"")+'" data-track="ALL">全競馬場</button>'+ts.map(function(t){return '<button class="'+(track===t?"active":"")+'" data-track="'+e(t)+'">'+e(t)+'</button>'}).join("");
 qa("#tracks [data-track]").forEach(function(b){b.onclick=function(){track=b.getAttribute("data-track");tracks();render()}})
}
function render(){
 var rows=base().filter(function(r){return (date==="ALL"||r.date===date)&&(track==="ALL"||r.track===track)}).sort(function(a,b){return String(b.date).localeCompare(String(a.date))||String(a.track).localeCompare(String(b.track))||Number(a.race_no)-Number(b.race_no)});
 q("#count").textContent=rows.length+"レース表示";
 q("#content").innerHTML=(month==="2026-09"?'<div class="day-lock-note">🔒 9/6は全レース終了までロック。終了後に封印済み予測と結果を過去レースへ移動します。</div>':"")+'<div class="list">'+rows.map(card).join("")+'</div>';
}
qa("#months [data-month]").forEach(function(b){b.onclick=function(){
 var m=b.getAttribute("data-month");
 qa("#months button").forEach(function(x){x.classList.remove("active")});b.classList.add("active");
 var locked=b.classList.contains("locked");q("#lockedView").hidden=!locked;q("#openView").hidden=locked;
 if(locked)return;
 month=m;date="ALL";track="ALL";dates();tracks();render();
}});
dates();tracks();
})();
'''
    page=f'''<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><title>過去レースのAI予測｜JRA AI</title><meta name="robots" content="noindex,nofollow"><style>{CSS}</style></head><body>
<header class="top"><a href="../">JRA AI</a><a href="../app/">最新予想</a></header>
<main class="wrap"><section class="hero"><small>AI RACE ARCHIVE</small><h1>過去レースのAI予測</h1><p>各レース1つのAI予測を固定して保存。予測内容を見たあと、タップして実際の結果を確認できます。</p></section>
<div class="notice"><b>9/5 全36Rの結果反映済み</b><br>9月・8月を公開中。9/5はページ生成時点で36Rを固定表示します。7月以前はロック表示を維持します。</div>
<div class="months" id="months"><button class="active" data-month="2026-09">9月</button><button data-month="2026-08">8月</button><button class="locked" data-month="2026-07">🔒 7月</button><button class="locked" data-month="2026-06">🔒 6月</button><button class="locked" data-month="2026-05">🔒 5月</button><button class="locked" data-month="2026-04">🔒 4月</button></div>
<div id="lockedView" class="locked-panel" hidden><div class="blur">札幌 11R　軸 7　候補 2・5・9<br>新潟 10R　軸 4　候補 1・6・12<br>中京 9R　軸 3　候補 5・8・11</div><div class="lock-message"><span>🔒</span><div>7月以前のAI予測は現在ロック中</div></div></div>
<div id="openView"><div id="dates" class="dates"><button class="active">全36R</button><button>9/5</button><button class="locked-day" disabled>🔒 9/6</button></div><div id="tracks" class="dates"><button class="active">全競馬場</button></div><div id="count" class="count">36レース表示</div><div id="content"><div class="day-lock-note">🔒 9/6は全レース終了までロック。終了後に封印済み予測と結果を過去レースへ移動します。</div><div class="list">{initial_cards}</div></div></div></main>
<nav class="mobile-nav"><a href="../">ホーム</a><a href="../app/">最新予想</a><a href="../horses/">データ</a><a href="../consult/">相談</a></nav>
<script type="application/json" id="replay-data">{embedded}</script><script>{js}</script><script src="/-jra-horse-bigdata-updater/word-links.js"></script></body></html>'''
    if "読込中" in page:
        raise SystemExit("generated replay page must not contain 読込中")
    if page.count('class="race"') < 36:
        raise SystemExit("generated replay page must contain at least 36 static race cards")
    if page.count('id="replay-data"') != 1:
        raise SystemExit("replay data must be embedded exactly once")
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(page,encoding="utf-8")
    print(json.dumps({"status":"PASS","initial_static_cards":36,"september_races":len(sep_rows),"august_races":len(aug_rows),"single_embedded_data":True,"loading_placeholder":False},ensure_ascii=False))

if __name__=="__main__":
    main()
