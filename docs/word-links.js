(()=>{
'use strict';
const BASE='/-jra-horse-bigdata-updater/';
const INDEX=BASE+'data/word-index.json';
const PROSE_SELECTOR='p,.summary,.description,.desc,.notice,.principle,.help,.intro-copy,.body-copy,[data-word-links-scope]';
const SKIP=new Set(['SCRIPT','STYLE','TEXTAREA','INPUT','SELECT','OPTION','BUTTON','A','CODE','PRE','NOSCRIPT','H1','H2','H3','H4','H5','H6','LABEL']);
const norm=s=>String(s||'').normalize('NFKC').toLowerCase();
const jp=/[一-龯々〆ヵヶぁ-ゖァ-ヶー]/u;
const latin=/[A-Za-z0-9_]/;
function css(){const s=document.createElement('style');s.textContent='.jra-word-link{color:#2f6fae!important;text-decoration:none;border-bottom:1px dotted #7aa5cf;cursor:pointer;font-weight:600}.jra-word-link:active{opacity:.65}.horse,.filter,.choice,.feature,.card,.mini-links a,.hero-actions a,.week,.quick button,.search button,.term{cursor:pointer;-webkit-tap-highlight-color:transparent;transition:transform .16s ease,box-shadow .16s ease,border-color .16s ease}.horse,.filter,.feature,.card,.mini-links a,.term{box-shadow:0 7px 20px rgba(43,64,52,.07)}.horse:hover,.filter:hover,.feature:hover,.card:hover,.mini-links a:hover,.term:hover{transform:translateY(-2px);box-shadow:0 12px 28px rgba(43,64,52,.11)}.horse:active,.filter:active,.choice:active,.feature:active,.card:active,.mini-links a:active,.hero-actions a:active,.week:active,.quick button:active,.search button:active,.term:active{transform:scale(.975)}.horse .arrow{display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:50%;background:#e8f4ee;color:#0b7146;font-weight:950}.filter small{display:inline-flex;align-items:center;gap:4px;padding:5px 8px;border-radius:999px;background:#e8f4ee}.top a,.mobile-nav a{cursor:pointer}.mobile-nav a.active{position:relative}.mobile-nav a.active:after{content:"";position:absolute;left:32%;right:32%;bottom:4px;height:3px;border-radius:999px;background:currentColor}';document.head.appendChild(s)}
function pageHref(url){return BASE+url}
function boundaryOK(text,start,end,hit){
  const before=start>0?text[start-1]:'';
  const after=end<text.length?text[end]:'';
  const first=hit[0]||'',last=hit[hit.length-1]||'';
  if(jp.test(first)&&jp.test(before))return false;
  if(jp.test(last)&&jp.test(after))return false;
  if(latin.test(first)&&latin.test(before))return false;
  if(latin.test(last)&&latin.test(after))return false;
  return true;
}
function findNext(text,from,words){
  let best=null;
  for(const w of words){
    let seek=from;
    while(seek<text.length){
      const i=text.indexOf(w.text,seek);if(i<0)break;
      const end=i+w.text.length;
      if(boundaryOK(text,i,end,w.text)){if(!best||i<best.i||(i===best.i&&w.text.length>best.w.text.length))best={i,end,w};break;}
      seek=i+1;
    }
  }
  return best;
}
function linkTextNode(node,words){
  const text=node.nodeValue;if(!text)return;
  const frag=document.createDocumentFragment();let pos=0,changed=false;
  while(pos<text.length){
    const m=findNext(text,pos,words);if(!m)break;
    if(m.i>pos)frag.appendChild(document.createTextNode(text.slice(pos,m.i)));
    const a=document.createElement('a');a.className='jra-word-link';a.href=pageHref(m.w.entry.url);a.textContent=text.slice(m.i,m.end);a.dataset.word=m.w.entry.term;frag.appendChild(a);
    pos=m.end;changed=true;
  }
  if(!changed)return;
  if(pos<text.length)frag.appendChild(document.createTextNode(text.slice(pos)));
  node.parentNode.replaceChild(frag,node);
}
function run(doc){
  const seen=new Set(),words=[];
  for(const e of doc.terms||[]){
    for(const raw of [e.term,...(e.aliases||[])]){
      const text=String(raw||'').normalize('NFKC');if(!text)continue;
      const k=norm(text);if(seen.has(k))continue;seen.add(k);words.push({text,entry:e});
    }
  }
  words.sort((a,b)=>b.text.length-a.text.length);if(!words.length)return;
  const roots=[...document.querySelectorAll(PROSE_SELECTOR)].filter(el=>!el.closest('nav,header,[data-no-word-links],.jra-word-link'));
  const nodes=[];
  for(const root of roots){
    const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT,{acceptNode(n){const p=n.parentElement;if(!p||SKIP.has(p.tagName)||p.closest('[data-no-word-links],.jra-word-link,a,button,nav,header,h1,h2,h3,h4,h5,h6'))return NodeFilter.FILTER_REJECT;return n.nodeValue.trim()?NodeFilter.FILTER_ACCEPT:NodeFilter.FILTER_REJECT}});
    while(walker.nextNode())nodes.push(walker.currentNode);
  }
  [...new Set(nodes)].forEach(n=>linkTextNode(n,words));
}
async function init(){css();try{const r=await fetch(INDEX+'?ts='+Date.now(),{cache:'no-store'});if(!r.ok)throw new Error(r.status);run(await r.json())}catch(e){console.error('word links',e)}}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
