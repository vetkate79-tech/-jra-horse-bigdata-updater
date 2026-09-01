(()=>{
  if(typeof openHorse!=='function')return;
  const original=openHorse;
  openHorse=function(name){
    original(name);
    const h=horses.find(x=>x.horse_name===name);
    if(!h)return;
    const isNew=(h.current_class==='NEW')||(h.tags||[]).includes('NEW')||(h.tags||[]).includes('NEW_ENTRY');
    if(!isNew)return;
    const detail=document.querySelector('#detail');
    if(!detail)return;
    const p=h.pedigree_summary||{};
    const pedigree=[p.sire?`父 ${esc(p.sire)}`:'',p.damsire?`母父 ${esc(p.damsire)}`:''].filter(Boolean).join(' / ');
    const t=h.training_summary;
    const block=document.createElement('div');
    block.innerHTML=`<div class="section newhorse"><h3>初めて見る人向け</h3><div class="newhorse-grid"><div><small>血統</small><b>${pedigree||'血統情報取得待ち'}</b></div><div><small>調教メモ</small><b>${t&&t.verified&&t.note?esc(t.note):'確認できた情報を順次追加します'}</b></div></div>${t&&t.verified&&t.source?`<p class="source-note">確認元：${esc(t.source)}</p>`:''}</div>`;
    detail.appendChild(block.firstElementChild);
  };
  const style=document.createElement('style');
  style.textContent='.newhorse-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}.newhorse-grid>div{background:#f5f7f3;border:1px solid #e5e9e4;border-radius:12px;padding:11px}.newhorse-grid small{display:block;color:#758079;font-size:9px;margin-bottom:5px}.newhorse-grid b{font-size:12px;line-height:1.6}.source-note{font-size:9px;color:#7b857f;margin:7px 2px 0}@media(max-width:520px){.newhorse-grid{grid-template-columns:1fr}}';
  document.head.appendChild(style);
})();
