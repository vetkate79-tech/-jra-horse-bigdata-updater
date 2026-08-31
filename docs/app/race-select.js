(()=>{
const $=s=>document.querySelector(s);
let data={races:[]};
let state={date:'',track:'',raceNo:null,selected:new Set()};
const uniq=a=>[...new Set(a)];
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
const fmtDate=s=>s?`${Number(s.slice(5,7))}/${Number(s.slice(8,10))}`:'';
function racesForDate(){return data.races.filter(r=>r.date===state.date)}
function racesForTrack(){return data.races.filter(r=>r.date===state.date&&r.track===state.track)}
function currentRace(){return data.races.find(r=>r.date===state.date&&r.track===state.track&&Number(r.race_no)===Number(state.raceNo))||null}
function normalize(){
  const dates=uniq(data.races.map(r=>r.date)).sort().reverse();
  if(!dates.includes(state.date))state.date=dates[0]||'';
  const tracks=uniq(racesForDate().map(r=>r.track));
  if(!tracks.includes(state.track))state.track=tracks[0]||'';
  const raceNos=uniq(racesForTrack().map(r=>Number(r.race_no))).sort((a,b)=>a-b);
  if(!raceNos.includes(Number(state.raceNo)))state.raceNo=raceNos[0]??null;
  const valid=new Set((currentRace()?.horses||[]).map(h=>String(h.n)));
  state.selected=new Set([...state.selected].filter(n=>valid.has(n)));
}
function renderDates(){
  const dates=uniq(data.races.map(r=>r.date)).sort().reverse();
  $('#dateSeg').innerHTML=dates.map(d=>`<button class="${d===state.date?'on':''}" data-date="${esc(d)}"><b>${fmtDate(d)}</b><small>${d===dates[0]?'最新':''}</small></button>`).join('');
  document.querySelectorAll('[data-date]').forEach(b=>b.onclick=()=>{state.date=b.dataset.date;state.track='';state.raceNo=null;state.selected.clear();normalize();render()});
}
function renderTracks(){
  const tracks=uniq(racesForDate().map(r=>r.track));
  $('#trackSeg').innerHTML=tracks.map(t=>`<button class="${t===state.track?'on':''}" data-track="${esc(t)}">${esc(t)}</button>`).join('');
  document.querySelectorAll('[data-track]').forEach(b=>b.onclick=()=>{state.track=b.dataset.track;state.raceNo=null;state.selected.clear();normalize();render()});
}
function renderRaces(){
  const rows=racesForTrack().slice().sort((a,b)=>Number(a.race_no)-Number(b.race_no));
  $('#raceStrip').innerHTML=rows.map(r=>`<button class="${Number(r.race_no)===Number(state.raceNo)?'on':''}" data-race="${r.race_no}"><b>${r.race_no}</b><small>R</small></button>`).join('');
  document.querySelectorAll('[data-race]').forEach(b=>b.onclick=()=>{state.raceNo=Number(b.dataset.race);state.selected.clear();render()});
}
function renderRaceCard(){
  const r=currentRace();
  if(!r){
    $('#raceTitle').textContent='レースを選択';
    $('#raceMeta').textContent='';
    $('#horses').innerHTML='<div class="empty-card"><b>出馬表取得待ち</b><span>このレースの馬名データはまだありません。</span></div>';
    $('#selectedCount').textContent='0頭';
    $('#selectedNames').textContent='気になる馬をタップしてください';
    return;
  }
  $('#raceTitle').textContent=`${r.track} ${r.race_no}R ${r.race_name||''}`.trim();
  $('#raceMeta').textContent=[r.start_time,r.surface,r.distance_m?`${r.distance_m}m`:null].filter(Boolean).join(' ・ ');
  const horses=(r.horses||[]).slice().sort((a,b)=>Number(a.n)-Number(b.n));
  $('#horses').innerHTML=horses.length?horses.map(h=>`<button class="horse-row ${state.selected.has(String(h.n))?'selected':''}" data-horse="${esc(h.n)}"><span class="frame frame-${h.frame||''}">${h.frame||'—'}</span><span class="horse-no">${esc(h.n)}</span><span class="horse-info"><b>${esc(h.name)}</b><small>${[h.sex,h.weight?`${h.weight}kg`:null,h.jockey].filter(Boolean).join(' ・ ')}</small></span><span class="pick">${state.selected.has(String(h.n))?'✓':'＋'}</span></button>`).join(''):'<div class="empty-card"><b>出馬表取得待ち</b><span>このレースの馬名データはまだありません。</span></div>';
  document.querySelectorAll('[data-horse]').forEach(b=>b.onclick=()=>{const n=b.dataset.horse;state.selected.has(n)?state.selected.delete(n):state.selected.add(n);renderRaceCard()});
  const selected=horses.filter(h=>state.selected.has(String(h.n)));
  $('#selectedCount').textContent=`${selected.length}頭`;
  $('#selectedNames').textContent=selected.length?selected.map(h=>`${h.n} ${h.name}`).join(' / '):'気になる馬をタップしてください';
  document.body.dataset.date=state.date;document.body.dataset.track=state.track;document.body.dataset.race=String(state.raceNo||'');
}
function render(){normalize();renderDates();renderTracks();renderRaces();renderRaceCard()}
function showError(){
  $('#dateSeg').innerHTML='';$('#trackSeg').innerHTML='';$('#raceStrip').innerHTML='';
  $('#raceTitle').textContent='出馬表を読み込めませんでした';
  $('#raceMeta').textContent='';
  $('#horses').innerHTML='<div class="empty-card"><b>データ読込エラー</b><span>ページを再読み込みしてください。</span></div>';
}
fetch('../data/race_cards.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw new Error(String(r.status));return r.json()}).then(d=>{data={races:Array.isArray(d.races)?d.races:[]};if(!data.races.length)throw new Error('empty');render()}).catch(showError);
})();
