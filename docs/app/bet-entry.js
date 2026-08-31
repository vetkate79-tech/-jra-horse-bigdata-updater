let catalog={races:[]};
let s={date:null,track:null,race:null,bet:'単勝',mode:'通常',col:0,sel:[new Set(),new Set(),new Set()]};
const $=q=>document.querySelector(q),$$=q=>[...document.querySelectorAll(q)];
const uniq=a=>[...new Set(a)];
const currentRace=()=>catalog.races.find(r=>r.date===s.date&&r.track===s.track&&Number(r.race_no)===Number(s.race));
const horse=n=>(currentRace()?.horses||[]).find(h=>String(h.n)===String(n));
const frameClass=f=>`frame-${f||1}`;
function resetSelection(){s.col=0;s.sel=[new Set(),new Set(),new Set()];$('#aiResult').innerHTML='';}
function combos(){
  const out=new Set(),a=[...s.sel[0]],b=[...s.sel[1]],c=[...s.sel[2]];
  if(s.bet==='単勝'||s.bet==='複勝')return a.sort((x,y)=>+x-+y);
  if(s.bet==='馬連'||s.bet==='ワイド'||s.bet==='馬単'){
    const y=s.mode==='BOX'?a:b;
    a.forEach(x=>y.forEach(z=>{if(x!==z){const v=s.bet==='馬単'?`${x}-${z}`:[+x,+z].sort((m,n)=>m-n).join('-');out.add(v)}}));
    return [...out];
  }
  if(s.bet==='三連複'){
    if(s.mode==='BOX'){
      const z=a.map(Number).sort((x,y)=>x-y);for(let i=0;i<z.length;i++)for(let j=i+1;j<z.length;j++)for(let k=j+1;k<z.length;k++)out.add(`${z[i]}-${z[j]}-${z[k]}`)
    }else a.forEach(x=>b.forEach(y=>c.forEach(z=>{const v=[+x,+y,+z];if(new Set(v).size===3)out.add(v.sort((m,n)=>m-n).join('-'))})));
    return [...out];
  }
  if(s.bet==='三連単'){
    if(s.mode==='BOX'){
      a.forEach(x=>a.forEach(y=>a.forEach(z=>{if(new Set([x,y,z]).size===3)out.add(`${x}-${y}-${z}`)})));
    }else a.forEach(x=>b.forEach(y=>c.forEach(z=>{if(new Set([x,y,z]).size===3)out.add(`${x}-${y}-${z}`)})));
    return [...out];
  }
  return [];
}
function renderSeg(sel,vals,cur,cb,label=v=>v){$(sel).innerHTML=vals.map(v=>`<button class="${cur===v?'on':''}" data-v="${v}">${label(v)}</button>`).join('');$$(sel+' [data-v]').forEach(b=>b.onclick=()=>cb(b.dataset.v));}
function render(){
  const dates=uniq(catalog.races.map(r=>r.date)).sort().reverse();
  if(!s.date||!dates.includes(s.date))s.date=dates[0]||null;
  renderSeg('#dateSeg',dates,s.date,v=>{s.date=v;const tracks=uniq(catalog.races.filter(r=>r.date===v).map(r=>r.track));s.track=tracks[0]||null;const races=catalog.races.filter(r=>r.date===v&&r.track===s.track);s.race=races[0]?.race_no||null;resetSelection();render()},v=>v.slice(5).replace('-','/'));
  const tracks=uniq(catalog.races.filter(r=>r.date===s.date).map(r=>r.track));
  if(!s.track||!tracks.includes(s.track))s.track=tracks[0]||null;
  renderSeg('#trackSeg',tracks,s.track,v=>{s.track=v;const rs=catalog.races.filter(r=>r.date===s.date&&r.track===v);s.race=rs[0]?.race_no||null;resetSelection();render()});
  const races=catalog.races.filter(r=>r.date===s.date&&r.track===s.track).sort((a,b)=>a.race_no-b.race_no);
  if(!races.some(r=>Number(r.race_no)===Number(s.race)))s.race=races[0]?.race_no||null;
  $('#raceStrip').innerHTML=races.map(r=>`<button class="${Number(s.race)===Number(r.race_no)?'on':''}" data-race="${r.race_no}">${r.race_no}<small>R</small></button>`).join('');
  $$('[data-race]').forEach(b=>b.onclick=()=>{s.race=+b.dataset.race;resetSelection();render()});
  const bets=['単勝','複勝','馬連','ワイド','三連複','三連単','馬単'];
  $('#betTypes').innerHTML=bets.map(v=>`<button class="${s.bet===v?'on':''}" data-bet="${v}">${v==='複勝'?'軸候補（複勝）':v}</button>`).join('');
  $$('[data-bet]').forEach(b=>b.onclick=()=>{s.bet=b.dataset.bet;s.mode=(s.bet==='単勝'||s.bet==='複勝')?'通常':'フォーメーション';resetSelection();render()});
  const triple=['三連複','三連単'].includes(s.bet);const modes=triple?['フォーメーション','BOX']:['通常','BOX'];
  $('#modeTabs').innerHTML=(s.bet==='単勝'||s.bet==='複勝')?'':modes.map(v=>`<button class="${s.mode===v?'on':''}" data-mode="${v}">${v}</button>`).join('');
  $$('[data-mode]').forEach(b=>b.onclick=()=>{s.mode=b.dataset.mode;resetSelection();render()});
  let cols=1;if(['馬連','ワイド','馬単'].includes(s.bet)&&s.mode!=='BOX')cols=2;if(triple&&s.mode!=='BOX')cols=3;
  $('#columnTabs').innerHTML=Array.from({length:cols},(_,i)=>`<button class="${s.col===i?'on':''}" data-col="${i}"><small>${cols===1?'選択':`${i+1}列目`}</small><b>${s.sel[i].size?s.sel[i].size+'頭':'未選択'}</b></button>`).join('');
  $$('[data-col]').forEach(b=>b.onclick=()=>{s.col=+b.dataset.col;render()});
  const r=currentRace();
  $('#selectedRace').textContent=r?`${r.track} ${r.race_no}R ${r.race_name||''}`:'レース未選択';
  $('#selectedBet').textContent=`${s.bet==='複勝'?'軸候補（複勝）':s.bet}${s.mode==='通常'?'':' '+s.mode}`;
  const hs=r?.horses||[];
  $('#horses').innerHTML=hs.length?hs.map(h=>`<button class="horse ${s.sel[s.col].has(String(h.n))?'selected':''}" data-horse="${h.n}"><span class="frame ${frameClass(h.frame)}">${h.frame||''}</span><span class="num">${h.n}</span><span class="horse-main"><span class="name">${h.name}</span><span class="meta">${[h.sex,h.weight&&h.weight+'kg',h.jockey].filter(Boolean).join(' ・ ')}</span></span><span class="recent"><small>${r.sample_incomplete?'UI試験':'出馬表'}</small><b>${r.start_time||''}</b></span><span class="check"></span></button>`).join(''):`<div class="empty-race">このレースの出馬表はまだ試験データに入っていません。</div>`;
  $$('[data-horse]').forEach(b=>b.onclick=()=>{const n=String(b.dataset.horse);if(s.bet==='単勝'||s.bet==='複勝'){s.sel[0].clear();s.sel[0].add(n)}else if(s.sel[s.col].has(n))s.sel[s.col].delete(n);else s.sel[s.col].add(n);render()});
  const cs=combos();$('#pointCount').textContent=`${cs.length}点`;$('#totalPoints').textContent=`${cs.length}点`;$('#ticketText').textContent=cs.length?cs.join(' / '):'出馬表から気になる馬を選んでください';$('.consult').disabled=!cs.length;
  $('.consult').textContent='選んだ馬を確認';
  if(r?.sample_incomplete)$('#ticketText').insertAdjacentHTML('beforeend','<br><small>※現在はUI一本化試験のため、JRA公式で確認済みの馬名だけを表示しています。</small>');
}
$('.consult').onclick=()=>{const r=currentRace(),cs=combos();if(!r||!cs.length)return;const names=uniq(s.sel.flatMap(x=>[...x])).map(n=>`${n} ${horse(n)?.name||''}`);$('#aiResult').innerHTML=`<div class="ai-card"><h3>${r.track} ${r.race_no}R</h3><p>${r.race_name||''} / ${r.surface||''}${r.distance_m?` ${r.distance_m}m`:''}</p><div class="pickline"><b>選んだ馬</b><br>${names.join('<br>')}</div><p class="demo-label">今は使用感・データ一本化の試験表示です。予想はまだ出しません。</p></div>`;};
fetch('../data/race_cards.json',{cache:'no-store'}).then(r=>r.json()).then(d=>{catalog=d||{races:[]};render()}).catch(()=>{catalog={races:[]};render()});
