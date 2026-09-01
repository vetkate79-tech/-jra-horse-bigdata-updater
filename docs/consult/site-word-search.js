(()=>{
'use strict';
const kata=s=>String(s??'').replace(/[ぁ-ゖ]/g,ch=>String.fromCharCode(ch.charCodeAt(0)+0x60));
const norm=s=>kata(String(s??'').normalize('NFKC').toLowerCase()).replace(/[\s・･._\-ー()（）]/g,'');
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
const mergeTerms=(base,extra)=>{const map=new Map();[...base,...extra].forEach(x=>{if(!x||!x.term)return;const key=norm(x.term);const old=map.get(key)||{};const aliases=[...(old.aliases||[]),...(x.aliases||[])];map.set(key,{...old,...x,aliases:[...new Set(aliases.filter(Boolean))]});});return [...map.values()].sort((a,b)=>String(a.term).localeCompare(String(b.term),'ja'));};
const matches=(x,q)=>{if(!q)return true;const blob=[x.term,x.reading,x.category,x.summary,x.short_definition,...(x.aliases||[])].filter(Boolean).map(norm).join(' ');return blob.includes(q);};
const slug=term=>'t-'+[...new TextEncoder().encode(String(term))].map(b=>b.toString(16).padStart(2,'0')).join('');
const termUrl=term=>`../words/${slug(term)}/`;
const decorateAliases=x=>{const a=x.aliases||[];return a.length?`<div class="reading">関連：${a.map(esc).join('・')}</div>`:'';};
function install(){
  renderWords=function(){
    const input=document.querySelector('#wordQ');if(!input)return;
    const q=norm(input.value);
    const rows=terms.filter(x=>matches(x,q));
    document.querySelector('#wordCount').textContent=`${rows.length}語`;
    document.querySelector('#wordList').innerHTML=rows.map(x=>`<article class="term"><div class="term-head"><div><h2>${esc(x.term)}</h2><span class="reading">${esc(x.reading||'')}</span>${decorateAliases(x)}</div><span class="tag">${esc(x.category||'サイト用語')}</span></div><p>${esc(x.summary||x.short_definition||'')}</p><a class="source" href="${termUrl(x.term)}">この言葉のページを見る →</a>${x.source_url?`<a class="source" style="margin-left:10px" href="${esc(x.source_url)}" target="_blank" rel="noopener">出典：${esc(x.source_name||'参照元')}</a>`:''}</article>`).join('')||'<div class="empty">該当する用語はありません</div>';
  };
  Promise.all([
    fetch('../data/site-terms.json?ts='+Date.now(),{cache:'no-store'}).then(r=>r.ok?r.json():{terms:[]}).catch(()=>({terms:[]})),
    fetch('../data/site-terms-extra.json?ts='+Date.now(),{cache:'no-store'}).then(r=>r.ok?r.json():{terms:[]}).catch(()=>({terms:[]}))
  ]).then(([official,extra])=>{terms=mergeTerms(terms,[...(official.terms||[]),...(extra.terms||[])]);renderWords();});
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install);else install();
})();
