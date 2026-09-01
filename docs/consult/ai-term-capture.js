(()=>{
  const KEY='jra-ai-term-candidates-v1';
  function load(){try{return JSON.parse(localStorage.getItem(KEY)||'[]')}catch{return[]}}
  function save(rows){localStorage.setItem(KEY,JSON.stringify(rows.slice(-500)))}
  function upsert(term){
    if(!term||!term.term)return;
    const rows=load();
    const name=String(term.term).trim();
    const hit=rows.find(x=>x.term===name);
    if(hit){
      hit.count=(hit.count||1)+1;
      hit.last_seen_at=new Date().toISOString();
      if(!hit.short_definition&&term.short_definition)hit.short_definition=term.short_definition;
      if(!hit.reading&&term.reading)hit.reading=term.reading;
      if(!hit.category&&term.category)hit.category=term.category;
      hit.confidence=Math.max(Number(hit.confidence||0),Number(term.confidence||0));
    }else{
      rows.push({
        term:name,reading:term.reading||null,category:term.category||'AI回答用語',
        short_definition:term.short_definition||null,confidence:Number(term.confidence||0),
        source_hint:term.source_hint||null,count:1,first_seen_at:new Date().toISOString(),last_seen_at:new Date().toISOString(),
        storage_state:'LOCAL_CANDIDATE_UNTIL_SHARED_BACKEND'
      });
    }
    save(rows);
  }
  window.JRATermCapture={capture:(terms=[])=>terms.forEach(upsert),list:load};
  window.addEventListener('jra-ai-answer',e=>{
    const terms=e.detail?.terms_used||[];
    terms.forEach(upsert);
  });
  // Consult already loads this file on every visit. Chain-load the full site
  // terminology search so new site terms become searchable without duplicating
  // script tags across pages.
  const s=document.createElement('script');
  s.src='./site-word-search.js?ts=20260901';
  s.defer=true;
  document.head.appendChild(s);
})();
