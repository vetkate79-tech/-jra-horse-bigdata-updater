(()=>{
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
  let pred=null;
  async function load(){
    try{pred=await fetch('../data/live_predictions_sealed.json',{cache:'no-store'}).then(r=>r.json());render()}catch(e){}
  }
  function current(){
    const dateBtn=document.querySelector('#weekDateSeg button.on');
    const trackBtn=document.querySelector('#trackSeg button.on');
    const raceBtn=document.querySelector('#raceStrip button.on');
    if(!dateBtn||!trackBtn||!raceBtn)return null;
    const ds=(dateBtn.dataset.date||'').trim();
    const track=(trackBtn.dataset.track||trackBtn.textContent||'').trim();
    const raceNo=Number(raceBtn.dataset.race||raceBtn.querySelector('b')?.textContent||0);
    return pred?.races?.find(r=>r.date===ds&&r.track===track&&Number(r.race_no)===raceNo)||null;
  }
  function render(){
    let box=document.getElementById('newHorseUnratedZone');
    const host=document.querySelector('.race-head');
    if(!host)return;
    if(!box){
      box=document.createElement('div');
      box.id='newHorseUnratedZone';
      box.style.cssText='margin-top:14px;padding:14px 16px;border:1px dashed #8b8175;border-radius:14px;background:#f1ede7;display:none';
      host.insertAdjacentElement('afterend',box);
    }
    const race=current();
    const xs=race?.unrated_dark_horses||race?.analysis?.unrated_dark_horses||[];
    const isNew=race?.analysis?.model_version==='NEW_HORSE_DEDICATED_V1';
    if(!isNew||!xs.length){box.style.display='none';box.innerHTML='';return;}
    box.style.display='block';
    box.innerHTML=`<small style="display:block;letter-spacing:.08em;color:#6f665d">除外ゾーン</small><b style="display:block;margin:3px 0 7px">未評価馬（完全ダークホース）</b><p style="margin:0 0 9px;font-size:13px;line-height:1.55">能力が低いという意味ではありません。新馬専用機構で必要な情報が不足し、順位を付けると誤評価になるためランキングから除外しています。</p>${xs.map(x=>`<div style="padding:8px 0;border-top:1px solid #d8d0c7"><b>${esc(x.n||'—')} ${esc(x.name||'')}</b><small style="display:block;margin-top:2px;color:#6f665d">未評価・完全ダークホース${(x.missing_evidence||[]).length?` / 不足: ${esc((x.missing_evidence||[]).join(', '))}`:''}</small></div>`).join('')}`;
  }
  document.addEventListener('click',()=>setTimeout(render,80));
  new MutationObserver(()=>render()).observe(document.body,{subtree:true,attributes:true,attributeFilter:['class']});
  load();
})();
