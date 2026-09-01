(()=>{
'use strict';
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
const pct=v=>v==null||v===''?'--':(Number(v)*100).toFixed(1)+'%';
const kata=s=>String(s??'').replace(/[ぁ-ゖ]/g,ch=>String.fromCharCode(ch.charCodeAt(0)+0x60));
const norm=s=>kata(String(s??'').normalize('NFKC').toLowerCase()).replace(/[\s・･._\-ー]/g,'');
let horses=[], cat='ALL';
function has(h,x){return (h.tags||[]).includes(x)||(h.current_class||'')===x}
function categoryMatch(h){
 if(cat==='ALL')return true;
 if(cat==='GRADED')return !!((h.graded_starts||[]).length||(h.tags||[]).includes('GRADED'));
 if(cat==='UNBEATEN')return h.unbeaten===true&&Number(h.wins||0)>=2;
 return has(h,cat);
}
function searchBlob(h){
 return norm([h.horse_name,h.trainer,h.sire,h.dam,h.damsire,h.owner,h.breeder,h.current_class_label].filter(Boolean).join(' '));
}
function filtered(){
 const q=norm($('#q')?.value||'');
 return horses.filter(h=>categoryMatch(h)&&(!q||searchBlob(h).includes(q))).sort((a,b)=>String(a.horse_name||'').localeCompare(String(b.horse_name||''),'ja'));
}
function tagHtml(h){
 const tags=[];
 for(const g of h.graded_experience||[])tags.push(g);
 if(h.current_class_label)tags.push(h.current_class_label);
 else if(h.current_class)tags.push(h.current_class);
 if((h.tags||[]).includes('NEW_ENTRY'))tags.push('出走前登録');
 return [...new Set(tags)].map(x=>`<span class="tag">${esc(x)}</span>`).join('');
}
function render(){
 const rows=filtered(), q=norm($('#q')?.value||'');
 const count=$('#count'), list=$('#list'); if(!count||!list)return;
 count.textContent=q?`${rows.length.toLocaleString()}頭見つかりました`:`${rows.length.toLocaleString()}頭`;
 const shown=q?rows:rows.slice(0,500);
 list.innerHTML=shown.map(h=>`<button class="horse" data-hid="${esc(h.horse_id||'')}" data-name="${esc(h.horse_name||'')}"><div class="horse-top"><div><b>${esc(h.horse_name)}</b><small>${esc(h.sex_age||'')} ${h.trainer?'/ '+esc(h.trainer):''}</small></div><span class="arrow">›</span></div><div class="tags">${tagHtml(h)}</div></button>`).join('') || `<div class="empty">${q?'登録済み馬の中に該当する馬はいません。':'該当する馬はいません'}</div>`;
 $$('.horse').forEach(b=>b.onclick=()=>openHorse(b.dataset.hid,b.dataset.name));
}
function raceDate(r){return String(r.date||r.race_date||'')}
function openHorse(hid,name){
 const h=horses.find(x=>hid&&x.horse_id===hid)||horses.find(x=>x.horse_name===name); if(!h)return;
 const raceRows=[...(h.target_starts||[]),...(h.recent_starts||[]),...(h.graded_starts||[])];
 const seen=new Set(), dedup=raceRows.filter(r=>{const k=[raceDate(r),r.course||r.venue,r.race_no,r.race_name].join('|');if(seen.has(k))return false;seen.add(k);return true}).sort((a,b)=>raceDate(b).localeCompare(raceDate(a)));
 const isNew=has(h,'NEW')||(h.tags||[]).includes('NEW_ENTRY');
 const pedigree=isNew?`<div class="section"><h3>血統</h3><div class="race"><b>父</b> ${esc(h.sire||h.pedigree_summary?.sire||'確認中')}<br><b>母父</b> ${esc(h.damsire||h.pedigree_summary?.damsire||'確認中')}${h.dam||h.pedigree_summary?.dam?`<br><b>母</b> ${esc(h.dam||h.pedigree_summary?.dam)}`:''}</div></div>`:'';
 const training=isNew?`<div class="section"><h3>調教メモ</h3><div class="race">${h.training_summary?esc(h.training_summary):'確認できた調教情報を順次追加します。'}</div></div>`:'';
 $('#detail').innerHTML=`<h2>${esc(h.horse_name)}</h2><div class="meta">${esc(h.sex_age||'')} ${h.trainer?'/ 調教師 '+esc(h.trainer):''}</div><div class="tags">${tagHtml(h)}</div><div class="stats"><div class="stat"><small>勝率</small><b>${pct(h.win_rate)}</b></div><div class="stat"><small>連対率</small><b>${pct(h.quinella_rate)}</b></div><div class="stat"><small>3着内率</small><b>${pct(h.show_rate)}</b></div></div>${pedigree}${training}<div class="section"><h3>登録済みレース</h3>${dedup.map(r=>`<div class="race"><b>${esc(raceDate(r))} ${esc(r.course||r.venue||'')} ${esc(r.race_no||'')}R ${esc(r.race_name||'')}</b><br>${esc(r.surface||'')} ${r.distance_m?esc(r.distance_m)+'m':''}${r.finish?' / '+esc(r.finish)+(String(r.finish).includes('着')?'':'着'):''}</div>`).join('')||'履歴なし'}</div>`;
 $('#sheet')?.classList.add('open');
}
function bind(){
 const q=$('#q'); if(q){q.placeholder='馬名・父・母父・調教師を検索'; q.oninput=render;}
 $$('#filterSheet [data-cat]').forEach(b=>b.onclick=()=>{cat=b.dataset.cat; const label=$('#filterLabel'); if(label)label.textContent=b.textContent; $$('#filterSheet [data-cat]').forEach(x=>x.classList.toggle('active',x===b)); $('#filterSheet')?.classList.remove('open'); render();});
}
async function init(){
 bind();
 try{const r=await fetch('../data/horses/catalog.json?ts='+Date.now(),{cache:'no-store'});if(!r.ok)throw new Error('catalog '+r.status);const d=await r.json();horses=(d.horses||[]).filter(h=>h&&h.horse_name);render();}
 catch(e){const c=$('#count'),l=$('#list');if(c)c.textContent='データ読み込みエラー';if(l)l.innerHTML='<div class="empty">馬データを読み込めませんでした。時間をおいて再読み込みしてください。</div>';console.error(e)}
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
