(()=>{
'use strict';
const kata=s=>String(s??'').replace(/[ぁ-ゖ]/g,ch=>String.fromCharCode(ch.charCodeAt(0)+0x60));
const norm=s=>kata(String(s??'').normalize('NFKC').toLowerCase()).replace(/[\s・･._\-ー()（）]/g,'');
const mergeTerms=(base,extra)=>{
  const map=new Map();
  [...base,...extra].forEach(x=>{
    if(!x||!x.term)return;
    const key=norm(x.term);
    const old=map.get(key)||{};
    const aliases=[...(old.aliases||[]),...(x.aliases||[])];
    map.set(key,{...old,...x,aliases:[...new Set(aliases.filter(Boolean))]});
  });
  return [...map.values()].sort((a,b)=>String(a.term).localeCompare(String(b.term),'ja'));
};
const matches=(x,q)=>{
  if(!q)return true;
  const blob=[x.term,x.reading,x.category,x.summary,x.short_definition,...(x.aliases||[])].filter(Boolean).map(norm).join(' ');
  return blob.includes(q);
};
const decorateAliases=x=>{
  const a=x.aliases||[];
  return a.length?`<div class="reading">関連：${a.map(esc).join('・')}</div>`:'';
};
const cleanCandidate=x=>{
  const t=String(x?.term||'');
  if(!t||t.length>10||Number(x.occurrences||0)<2)return false;
  if(/[<>{}=]|(?:この|その|ます|です|する|され|http|class|function)/.test(t))return false;
  if(/[ァ-ヶ]$/.test(t)&&t.length>4&&!/(ペース|クラス)$/.test(t))return false;
  return true;
};
function install(){
  const original=window.renderWords||renderWords;
  renderWords=function(){
    const input=document.querySelector('#wordQ'); if(!input)return original?.();
    const q=norm(input.value);
    const rows=terms.filter(x=>matches(x,q));
    document.querySelector('#wordCount').textContent=`${rows.length}語`;
    document.querySelector('#wordList').innerHTML=rows.map(x=>`<article class="term" data-term-card="${esc(x.term)}"><div class="term-head"><div><h2>${esc(x.term)}</h2><span class="reading">${esc(x.reading||'')}</span>${decorateAliases(x)}</div><span class="tag">${esc(x.category||'サイト用語')}</span></div><p>${esc(x.summary||x.short_definition||'サイト内で使われている用語です。詳しい意味はAIに聞けます。')}</p>${x.source_url?`<a class="source" href="${esc(x.source_url)}" target="_blank" rel="noopener">出典：${esc(x.source_name||'参照元')}</a>`:'<span class="source">${esc(x.source_name||'JRA AI サイト内用語')}</span>'}</article>`).join('')||'<div class="empty">該当する用語はありません</div>';
    document.querySelectorAll('[data-term-card]').forEach(x=>x.onclick=()=>{showPane('askPane');document.querySelector('#q').value=`${x.dataset.termCard}ってどういう意味？`;document.querySelector('#ask').click()});
  };
  Promise.all([
    fetch('../data/site-terms.json?ts='+Date.now(),{cache:'no-store'}).then(r=>r.ok?r.json():{terms:[]}).catch(()=>({terms:[]})),
    fetch('../data/site-terms-extra.json?ts='+Date.now(),{cache:'no-store'}).then(r=>r.ok?r.json():{terms:[]}).catch(()=>({terms:[]})),
    fetch('../data/site-term-candidates.json?ts='+Date.now(),{cache:'no-store'}).then(r=>r.ok?r.json():{terms:[]}).catch(()=>({terms:[]}))
  ]).then(([official,extra,candidates])=>{
    const auto=(candidates.terms||[]).filter(cleanCandidate);
    terms=mergeTerms(terms,[...(official.terms||[]),...(extra.terms||[]),...auto]);
    renderWords();
  });
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install);else install();
})();
