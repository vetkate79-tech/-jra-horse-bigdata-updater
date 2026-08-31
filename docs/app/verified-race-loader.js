(()=>{
  const fallbackDates=['2026-08-30','2026-08-29'];
  const fallbackTracks=['新潟','中京','札幌'];
  let cards=[];
  const uniq=a=>[...new Set(a)];
  const byNo=(a,b)=>Number(a)-Number(b);
  function currentCard(){return cards.find(r=>r.date===s.date&&r.track===s.track&&Number(r.race_no)===Number(s.race))||null}
  function sanitizeSelections(horses){
    const valid=new Set((horses||[]).map(h=>String(h.n)));
    s.sel=s.sel.map(set=>new Set([...set].filter(n=>valid.has(String(n)))));
  }
  function syncBefore(){
    if(cards.length){
      demo.dates=uniq(cards.map(x=>x.date)).sort().reverse();
      if(!demo.dates.includes(s.date))s.date=demo.dates[0];
      demo.tracks=uniq(cards.filter(x=>x.date===s.date).map(x=>x.track));
      if(!demo.tracks.includes(s.track))s.track=demo.tracks[0];
      demo.races=uniq(cards.filter(x=>x.date===s.date&&x.track===s.track).map(x=>Number(x.race_no))).sort(byNo);
      if(!demo.races.includes(Number(s.race)))s.race=demo.races[0];
      const card=currentCard();
      demo.horses=card?.horses||[];
      sanitizeSelections(demo.horses);
    }else{
      demo.dates=fallbackDates;
      demo.tracks=fallbackTracks;
      demo.races=[1,2,3,4,5,6,7,8,9,10,11,12];
      demo.horses=[];
      s.sel=[new Set(),new Set(),new Set()];
    }
  }
  function syncAfter(){
    const card=currentCard();
    const title=document.querySelector('#selectedRace');
    const horses=document.querySelector('#horses');
    if(card){
      if(title)title.textContent=`${card.track} ${card.race_no}R${card.race_name?' '+card.race_name:''}`;
      document.body.dataset.raceId=card.race_id||'';
      document.body.dataset.raceSource=card.source||'';
    }else{
      if(horses)horses.innerHTML='<div style="padding:28px 14px;text-align:center;color:#6f7973;font-size:12px;line-height:1.7"><b style="display:block;color:#253129;margin-bottom:4px">出馬表取得待ち</b>JRA公式で確認できた出走馬だけを表示します。別レースの仮馬を流用しません。</div>';
      const btn=document.querySelector('.consult');if(btn)btn.disabled=true;
    }
  }
  const original=render;
  render=function(){syncBefore();original();syncAfter()};
  fetch('../data/race_cards.json',{cache:'no-store'}).then(r=>r.ok?r.json():Promise.reject()).then(d=>{
    cards=(d.races||[]).filter(r=>r&&r.date&&r.track&&r.race_no&&Array.isArray(r.horses));
    render();
  }).catch(()=>{cards=[];render()});
})();
