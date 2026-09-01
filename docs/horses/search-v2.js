(()=>{
'use strict';
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot',"'":'&#039;'}[c]));
const pct=v=>v==null||v===''?'--':(Number(v)*100).toFixed(1)+'%';
const kata=s=>String(s??'').replace(/[ぁ-ゖ]/g,ch=>String.fromCharCode(ch.charCodeAt(0)+0x60));
const norm=s=>kata(String(s??'').normalize('NFKC').toLowerCase()).replace(/[\s・･._\-ー]/g,'');
let horses=[], weekly=new Map(), cat='ALL';
const STYLE_CATS={STYLE_ESCAPE:'ESCAPE',STYLE_FRONT:'FRONT',STYLE_STALK:'STALK',STYLE_CLOSER:'CLOSER',STYLE_DEEP_CLOSER:'DEEP_CLOSER'};
function has(h,x){return (h.tags||[]).includes(x)||(h.current_class||'')===x}
function categoryMatch(h){
 if(cat==='ALL')return true;
 if(cat==='GRADED')return (h.tags||[]).includes('GRADED');
 if(cat==='UNBEATEN')return h.unbeaten===true&&Number(h.wins||0)>=2;
 if(STYLE_CATS[cat])return h.running_style===STYLE_CATS[cat];
 return has(h,cat);
}
function searchBlob(h){return norm([h.horse_name,h.trainer,h.sire,h.damsire,h.current_class_label,h.running_style_label,...(h.graded_race_names||[])].filter(Boolean).join(' '))}
function filtered(){const q=norm($('#q')?.value||'');return horses.filter(h=>categoryMatch(h)&&(!q||searchBlob(h).includes(q))).sort((a,b)=>String(a.horse_name||'').localeCompare(String(b.horse_name||''),'ja'))}
function tagHtml(h){
 const tags=[];
 if((h.tags||[]).includes('GRADED'))tags.push('重賞出走馬');
 if((h.tags||[]).includes('OPEN'))tags.push('オープン馬');
 if(h.current_class_label)tags.push(h.current_class_label);else if(h.current_class)tags.push(h.current_class);
 if(h.running_style_label&&h.running_style!=='UNKNOWN')tags.push(h.running_style_label);
 if((h.tags||[]).includes('NEW_ENTRY'))tags.push('出走前登録');
 if(weekly.has(h.horse_id))tags.push('今週出走');
 return [...new Set(tags)].map(x=>`<span class="tag">${esc(x)}</span>`).join('');
}
function render(){
 const rows=filtered(),q=norm($('#q')?.value||''),count=$('#count'),list=$('#list');if(!count||!list)return;
 count.textContent=q?`${rows.length.toLocaleString()}頭見つかりました`:`${rows.length.toLocaleString()}頭`;
 const shown=q?rows:rows.slice(0,500);
 list.innerHTML=shown.map(h=>`<button class="horse" data-hid="${esc(h.horse_id||'')}" data-name="${esc(h.horse_name||'')}"><div class="horse-top"><div><b>${esc(h.horse_name)}</b><small>${esc(h.sex_age||'性齢確認中')} ${h.trainer?'/ 調教師 '+esc(h.trainer):''}</small></div><span class="arrow">›</span></div><div class="tags">${tagHtml(h)}</div></button>`).join('')||`<div class="empty">${q?'登録済み馬の中に該当する馬はいません。':'該当する馬はいません'}</div>`;
 $$('.horse').forEach(b=>b.onclick=()=>openHorse(b.dataset.hid,b.dataset.name));
}
function raceDate(r){return String(r.date||r.race_date||'')}
function label(v,fallback='確認中'){return v==null||v===''?fallback:esc(v)}
function openHorse(hid,name){
 const base=horses.find(x=>hid&&x.horse_id===hid)||horses.find(x=>x.horse_name===name);if(!base)return;
 const w=weekly.get(base.horse_id)||null;
 const isNew=has(base,'NEW')||(base.tags||[]).includes('NEW_ENTRY');
 const status=base.active===true?'現役':base.active===false?'抹消':'確認中';
 const styleNote=base.running_style_provisional&&base.running_style!=='UNKNOWN'?'（暫定）':'';
 const elite=[];
 if((base.tags||[]).includes('OPEN'))elite.push('<b>クラス区分</b> オープン馬');
 if((base.tags||[]).includes('GRADED')){
   const grades=(base.graded_experience||[]).join('・');
   const names=(base.graded_race_names||[]).join('、');
   elite.push(`<b>重賞出走歴</b> ${esc([grades,names].filter(Boolean).join(' / ')||'確認済み')}`);
 }
 const basic=`<div class="section"><h3>基本データ</h3><div class="race"><b>クラス</b> ${label(base.current_class_label||base.current_class)}<br><b>脚質</b> ${label(base.running_style_label)}${styleNote}<br><b>父</b> ${label(base.sire||base.pedigree_summary?.sire)}<br><b>母父</b> ${label(base.damsire||base.pedigree_summary?.damsire)}<br><b>登録状態</b> ${status}${elite.length?'<br>'+elite.join('<br>'):''}${base.latest_race_date?`<br><b>最新出走</b> ${esc(base.latest_race_date)}${base.latest_finish?` / ${esc(base.latest_finish)}着`:''}`:''}</div></div>`;
 const pedigree=isNew?`<div class="section"><h3>新馬の血統</h3><div class="race"><b>父</b> ${label(base.sire||base.pedigree_summary?.sire)}<br><b>母父</b> ${label(base.damsire||base.pedigree_summary?.damsire)}${base.pedigree_summary?.dam?`<br><b>母</b> ${esc(base.pedigree_summary.dam)}`:''}</div></div>`:'';
 const training=isNew?`<div class="section"><h3>調教メモ</h3><div class="race">${base.training_summary?esc(base.training_summary):'確認できた調教情報を順次追加します。'}</div></div>`:'';
 const raceWeek=w?`<div class="section"><h3>今週の出走</h3><div class="race"><b>${esc(w.race?.date||'')} ${esc(w.race?.track||'')} ${esc(w.race?.race_no||'')}R ${esc(w.race?.race_name||'')}</b>${w.horse_no?`<br>馬番 ${esc(w.horse_no)}`:''}</div></div>`:'';
 const stats=w?`<div class="stats"><div class="stat"><small>勝率</small><b>${pct(w.win_rate)}</b></div><div class="stat"><small>連対率</small><b>${pct(w.quinella_rate)}</b></div><div class="stat"><small>3着内率</small><b>${pct(w.show_rate)}</b></div></div>`:'';
 const recent=w?(w.recent_starts||[]):[];
 const recentHtml=w?`<div class="section"><h3>今週だけ表示する近走データ</h3>${recent.map(r=>`<div class="race"><b>${esc(raceDate(r))} ${esc(r.course||r.venue||'')} ${esc(r.race_no||'')}R ${esc(r.race_name||'')}</b><br>${esc(r.surface||'')} ${r.distance_m?esc(r.distance_m)+'m':''}${r.finish?' / '+esc(r.finish)+(String(r.finish).includes('着')?'':'着'):''}</div>`).join('')||'近走データ確認中'}</div>`:'';
 $('#detail').innerHTML=`<h2>${esc(base.horse_name)}</h2><div class="meta">${esc(base.sex_age||'')} ${base.trainer?'/ 調教師 '+esc(base.trainer):''}</div><div class="tags">${tagHtml(base)}</div>${basic}${raceWeek}${stats}${pedigree}${training}${recentHtml}`;
 $('#sheet')?.classList.add('open');
}
function bind(){
 const q=$('#q');if(q){q.placeholder='馬名・父・母父・調教師・脚質・重賞名を検索';q.oninput=render;}
 $('#filter')?.addEventListener('click',()=>$('#filterSheet')?.classList.add('open'));
 $('[data-filter-close]')?.addEventListener('click',()=>$('#filterSheet')?.classList.remove('open'));
 $('[data-close]')?.addEventListener('click',()=>$('#sheet')?.classList.remove('open'));
 $$('#filterSheet [data-cat]').forEach(b=>b.onclick=()=>{cat=b.dataset.cat;const label=$('#filterLabel');if(label)label.textContent=b.textContent;$$('#filterSheet [data-cat]').forEach(x=>x.classList.toggle('active',x===b));$('#filterSheet')?.classList.remove('open');render()});
}
async function getJson(url){const r=await fetch(url+'?ts='+Date.now(),{cache:'no-store'});if(!r.ok)throw new Error(url+' '+r.status);return r.json()}
async function init(){
 bind();
 try{
   let base;
   try{base=await getJson('../data/horses/base_catalog.json');}
   catch(e){console.info('lightweight master not ready; using catalog fallback',e);base=await getJson('../data/horses/catalog.json');}
   horses=(base.horses||[]).filter(h=>h&&h.horse_name);
   try{const w=await getJson('../data/horses/weekly_runner_details.json');weekly=new Map((w.runners||[]).map(x=>[x.horse_id,x]));}catch(e){console.info('weekly detail not ready',e)}
   render();
 }catch(e){const c=$('#count'),l=$('#list');if(c)c.textContent='データ読み込みエラー';if(l)l.innerHTML='<div class="empty">馬データを読み込めませんでした。時間をおいて再読み込みしてください。</div>';console.error(e)}
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
