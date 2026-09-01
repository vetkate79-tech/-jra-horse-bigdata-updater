(()=>{
'use strict';
const BASE='/ -jra-horse-bigdata-updater/'.replace(' ','');
const INDEX=BASE+'data/word-index.json';
const SKIP=new Set(['SCRIPT','STYLE','TEXTAREA','INPUT','SELECT','OPTION','BUTTON','A','CODE','PRE','NOSCRIPT']);
const norm=s=>String(s||'').normalize('NFKC').toLowerCase();
function css(){const s=document.createElement('style');s.textContent='.jra-word-link{color:#2f6fae!important;text-decoration:none;border-bottom:1px dotted #7aa5cf;cursor:pointer;font-weight:600}.jra-word-link:active{opacity:.65}';document.head.appendChild(s)}
function escapeRx(s){return s.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')}
function pageHref(url){return BASE+url}
function linkTextNode(node,entries,rx){
  const text=node.nodeValue;if(!text||!rx.test(text))return;rx.lastIndex=0;
  const frag=document.createDocumentFragment();let last=0,m;
  while((m=rx.exec(text))){
    if(m.index>last)frag.appendChild(document.createTextNode(text.slice(last,m.index)));
    const hit=m[0];const e=entries.get(norm(hit));
    if(!e){frag.appendChild(document.createTextNode(hit));last=rx.lastIndex;continue}
    const a=document.createElement('a');a.className='jra-word-link';a.href=pageHref(e.url);a.textContent=hit;a.dataset.word=e.term;frag.appendChild(a);last=rx.lastIndex;
  }
  if(last<text.length)frag.appendChild(document.createTextNode(text.slice(last)));
  node.parentNode.replaceChild(frag,node);
}
function run(doc){
  const entries=new Map();const words=[];
  for(const e of doc.terms||[]){for(const w of [e.term,...(e.aliases||[])]){if(!w||String(w).length<2)continue;const k=norm(w);if(!entries.has(k)){entries.set(k,e);words.push(String(w))}}}
  words.sort((a,b)=>b.length-a.length);if(!words.length)return;
  const rx=new RegExp(words.map(escapeRx).join('|'),'giu');
  const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT,{acceptNode(n){const p=n.parentElement;if(!p||SKIP.has(p.tagName)||p.closest('[data-no-word-links],.jra-word-link'))return NodeFilter.FILTER_REJECT;const t=n.nodeValue.trim();return t?NodeFilter.FILTER_ACCEPT:NodeFilter.FILTER_REJECT}});
  const nodes=[];while(walker.nextNode())nodes.push(walker.currentNode);nodes.forEach(n=>linkTextNode(n,entries,rx));
}
async function init(){css();try{const r=await fetch(INDEX+'?ts='+Date.now(),{cache:'no-store'});if(!r.ok)throw new Error(r.status);run(await r.json())}catch(e){console.error('word links',e)}}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
