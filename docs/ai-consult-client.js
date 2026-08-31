(()=>{
const ENDPOINT=window.JRA_AI_CONSULT_ENDPOINT||'/api/consult';
let glossary=[];
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
const featureGuide=(q,ctx={})=>{
  const s=String(q||'');
  if(/オッズ|妙味|期待値|買い時|締切|配当/.test(s)) return {title:'オッズを使う判断は「詳細分析」で確認',body:'能力評価とオッズは分けて扱います。オッズ取得後の「市場・妙味」までデータが揃えば、買う価値があるかを判断できます。今の段階で数値を推測して答えることはしません。',href:'/analysis/',label:'詳細分析を見る'};
  if(/軸|飛ぶ|崩れ|敗因|リスク|展開/.test(s)) return {title:'この質問は「詳細分析」が向いています',body:'軸耐久性、軸飛びリスク、想定ペース、敗因シミュレーションを同じレースのデータから確認できます。材料が揃っていない場合は、AIが馬名や確率を作らず判定待ちにします。',href:'/analysis/',label:'詳細分析を見る'};
  if(/この馬|馬の成績|血統|騎手|近走|どんな馬/.test(s)) return {title:'その馬の情報は「馬データ」で確認できます',body:'馬ごとの近走・基本情報・クラスなど、登録済みの実データを確認してからAIに聞くと、見当違いの回答を避けられます。',href:'/horses/',label:'馬データを見る'};
  if(/今日|今週|出走|レース|何R|競馬場/.test(s)) return {title:'現在の出走情報が必要です',body:'開催日・競馬場・レースを選んでからAIに聞くと、そのレースの文脈で回答できます。出走情報が未取得の状態では推測しません。',href:'/app/',label:'レースを選ぶ'};
  if(/買い目|単勝|複勝|馬連|ワイド|三連複|三連単|馬単/.test(s)) return {title:'買い目を入力してAIと答え合わせできます',body:'出馬表から自分の予想を選ぶと、その買い目が成立する展開や崩れるパターンをAI相談に渡せます。',href:'/app/',label:'AI答え合わせを使う'};
  return {title:'AI回答にはバックエンド接続が必要です',body:'この質問は辞書の固定文では返しません。AI接続後はそのまま質問文をAIへ送り、分からない場合は必要なデータや使うべき機能を案内する設計です。',href:'/consult/',label:'相談ページに戻る'};
};
const linkTerms=text=>{
  let out=esc(text);
  [...glossary].sort((a,b)=>b.term.length-a.term.length).forEach(t=>{
    const term=esc(t.term);
    out=out.split(term).join(`<a class="ai-term-link" href="/consult/?word=${encodeURIComponent(t.term)}">${term}</a>`);
  });
  return out.replace(/\n/g,'<br>');
};
async function askAI(question,context={}){
  const res=await fetch(ENDPOINT,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question,context,policy:{no_guessing:true,no_market_leak:true,prefer_feature_guidance:true,glossary_is_reference_only:true}})});
  if(!res.ok) throw new Error(`AI endpoint unavailable: ${res.status}`);
  const data=await res.json();
  if(!data||!data.answer) throw new Error('AI response missing answer');
  return data;
}
function renderLoading(box){box.classList.add('show');box.innerHTML='<div class="ai-consult-loading"><span></span><b>AIが確認しています</b><small>必要なデータが足りない場合は、推測せず確認方法をご案内します。</small></div>'}
function renderGuidance(box,g){box.classList.add('show');box.innerHTML=`<small>AI GUIDE</small><h2>${esc(g.title)}</h2><p>${esc(g.body)}</p><a class="ai-feature-link" href="${g.href}">${esc(g.label)} →</a>`}
function renderAnswer(box,data){box.classList.add('show');box.innerHTML=`<small>AI ANSWER</small><h2>${esc(data.title||'AIからの回答')}</h2><p>${linkTerms(data.answer)}</p>${data.feature?`<a class="ai-feature-link" href="${esc(data.feature.href)}">${esc(data.feature.label||'この機能で確認する')} →</a>`:''}`}
window.JRAAIConsult={
  async ask({question,box,context={}}){if(!question||!box)return;renderLoading(box);try{const data=await askAI(question,context);renderAnswer(box,data)}catch(e){renderGuidance(box,featureGuide(question,context))}},
  guide:featureGuide
};
fetch('/data/glossary.json',{cache:'no-store'}).then(r=>r.ok?r.json():{terms:[]}).then(d=>glossary=d.terms||[]).catch(()=>{});
})();