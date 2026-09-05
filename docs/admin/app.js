const DEFAULT_DATA_URL = '../data/dashboard.json';
const qs = (s) => document.querySelector(s);
const qsa = (s) => [...document.querySelectorAll(s)];

const titles = {today:'今日の運用',races:'レース管理',models:'モデル管理',pdca:'PDCA / 検証',audit:'監査ログ',system:'システム状態'};

qsa('.nav-item').forEach(btn=>btn.addEventListener('click',()=>{
  qsa('.nav-item').forEach(x=>x.classList.remove('active')); btn.classList.add('active');
  qsa('.view').forEach(x=>x.classList.remove('active')); qs(`#view-${btn.dataset.view}`).classList.add('active');
  qs('#pageTitle').textContent=titles[btn.dataset.view]||'';
}));

const yen = n => `¥${Number(n||0).toLocaleString('ja-JP')}`;
const pct = n => `${Number(n||0).toFixed(1)}%`;
const esc = s => String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));

function badge(v){return `<span class="badge ${esc(v)}">${esc(v)}</span>`}
function renderKpis(el, items){el.innerHTML=items.map(x=>`<div class="kpi"><div class="k">${esc(x.label)}</div><div class="v">${esc(x.value)}</div><div class="s">${esc(x.sub||'')}</div></div>`).join('')}

function render(data){
  const summary=data.summary||{};
  qs('#modelVersion').textContent=`model: ${summary.model_version||'-'}`;
  qs('#snapshotTime').textContent=`snapshot: ${summary.snapshot_time||'-'}`;
  qs('#connectionLabel').textContent='DATA CONNECTED';

  renderKpis(qs('#kpis'),[
    {label:'対象レース',value:summary.total_races||0,sub:`購入 ${summary.buy_races||0} / PASS ${summary.pass_races||0}`},
    {label:'本日ROI',value:pct(summary.roi),sub:`払戻 ${yen(summary.return_amount)}`},
    {label:'的中率',value:pct(summary.hit_rate),sub:`的中 ${summary.hits||0}R`},
    {label:'日次予算',value:yen(summary.daily_budget),sub:`残 ${yen(summary.remaining_budget)}`},
    {label:'最大払戻除外ROI',value:pct(summary.roi_ex_top),sub:'一発依存監査'}
  ]);

  const races=data.races||[]; qs('#raceCount').textContent=`${races.length} races`;
  qs('#raceTableBody').innerHTML=races.map(r=>`<tr><td><b>${esc(r.track)} ${esc(r.race_no)}R</b></td><td>${esc(r.start_time)}</td><td>${badge(r.classification||'PASS')}</td><td>${esc(r.axis||'-')}</td><td><span class="state">${esc(r.race_state||'-')}</span></td><td>${r.ev==null?'-':Number(r.ev).toFixed(2)}</td><td>${yen(r.stake)}</td></tr>`).join('') || '<tr><td colspan="7" class="muted">レースデータ未接続</td></tr>';

  const risks=data.risks||[]; qs('#riskCards').innerHTML=risks.map(x=>`<div class="risk"><div class="risk-row"><strong>${esc(x.name)}</strong><span class="dot ${x.level==='ok'?'ok':x.level==='bad'?'bad':'warn'}"></span></div><p>${esc(x.detail)}</p></div>`).join('');

  const flow=data.state_counts||{}; const states=['DATA_PENDING','DATA_READY','PREDICTED','SEALED','PRE_RACE_CHECK','EV_CONFIRMED','PASS','RESULT_PENDING','SCORED','PDCA_RECORDED'];
  qs('#stateFlow').innerHTML=states.map(s=>`<div class="state-node"><span class="label">${esc(s)}</span><div class="count">${flow[s]||0}</div></div>`).join('');

  qs('#raceCards').innerHTML=races.map(r=>`<article class="race-card"><div class="meta">${esc(r.start_time)} · ${esc(r.surface||'')} ${esc(r.distance||'')}m</div><h3>${esc(r.track)} ${esc(r.race_no)}R ${badge(r.classification||'PASS')}</h3><div class="meta">軸 ${esc(r.axis||'-')} / 軸耐久 ${esc(r.axis_durability||'-')} / 相手内完結 ${esc(r.axis_failure_risk||'-')}</div><div class="ticket">${esc(r.ticket_summary||'買い目未確定')}</div></article>`).join('') || '<p class="muted">レースデータ未接続</p>';

  const models=data.models||[]; qs('#modelCards').innerHTML=models.map(m=>`<div class="model-card"><div class="row"><strong>${esc(m.name)}</strong><span>${esc(m.status)}</span></div><p>ROI ${pct(m.roi)} / 的中 ${pct(m.hit_rate)} / ${esc(m.note||'')}</p></div>`).join('');

  const mechs=data.mechanisms||[]; qs('#mechanisms').innerHTML=mechs.map(m=>`<div class="mechanism"><b>${esc(m.name)}</b><span>${esc(m.status)} · ${esc(m.note||'')}</span></div>`).join('');

  renderKpis(qs('#pdcaKpis'),[
    {label:'軸生存率',value:pct(summary.axis_survival),sub:'3着以内'},
    {label:'3列目漏れ率',value:pct(summary.third_column_miss_rate),sub:'買い目変換'},
    {label:'完全消し好走率',value:pct(summary.elimination_miss_rate),sub:'軽微補修監視'},
    {label:'最大DD',value:pct(summary.max_drawdown),sub:'資金リスク'},
    {label:'購入率',value:pct(summary.purchase_rate),sub:'全対象比'}
  ]);

  renderBars(qs('#errorBars'),data.error_types||[]);
  renderBars(qs('#roleBars'),data.role_distribution||[]);

  qs('#auditList').innerHTML=(data.audit||[]).map(a=>`<div class="audit"><div class="muted">${esc(a.time)}</div><div class="level">${esc(a.level)}</div><div><strong>${esc(a.title)}</strong><p>${esc(a.detail)}</p></div></div>`).join('') || '<p class="muted">監査ログなし</p>';

  qs('#sourceList').innerHTML=(data.sources||[]).map(x=>`<div class="risk"><div class="risk-row"><strong>${esc(x.name)}</strong><span class="dot ${x.status==='ok'?'ok':x.status==='bad'?'bad':'warn'}"></span></div><p>${esc(x.detail)}</p></div>`).join('');
}

function renderBars(el,items){
  const max=Math.max(1,...items.map(x=>Number(x.value||0)));
  el.innerHTML=items.map(x=>`<div><div class="bar-label"><span>${esc(x.label)}</span><span>${esc(x.value)}</span></div><div class="bar-track"><div class="bar-fill" style="width:${Math.max(2,Number(x.value||0)/max*100)}%"></div></div></div>`).join('') || '<p class="muted">データなし</p>';
}

async function boot(){
  const dataUrl = new URLSearchParams(location.search).get('data') || window.JRA_ERP_DATA_URL || DEFAULT_DATA_URL;
  try{const res=await fetch(dataUrl,{cache:'no-store'}); if(!res.ok) throw new Error(`HTTP ${res.status}`); render(await res.json());}
  catch(err){qs('#connectionLabel').textContent='DATA NOT CONNECTED';qs('.sidebar-footer .dot').className='dot bad';render({summary:{},risks:[{name:'データ接続',level:'bad',detail:`${dataUrl} を取得できません。予想側が共通JSONを出力すると自動表示されます。`}],sources:[{name:'ERP data adapter',status:'bad',detail:String(err.message||err)}],mechanisms:[]});}
}
boot();

async function loadPdcaReport(){
  try{
    const r=await fetch('../data/erp-pdca-2026-09-05.json',{cache:'no-store'});
    if(!r.ok)throw new Error('HTTP '+r.status);
    const d=await r.json(),s=d.summary||{},v=d.validation_plan||{};
    qs('#pdcaReportStatus').textContent=d.status||'READY';
    qs('#pdcaReportSummary').innerHTML=`
      <div class="report-lead"><strong>${esc(d.title||'実運用分析')}</strong><p>${esc(s.scope||'')}</p></div>
      <div class="report-note"><b>未見検証</b><span>${esc(v.immediate_holdout||'')}</span></div>
      <div class="report-note"><b>固定ルール</b><span>${esc(s.immutable_rule||'')}</span></div>`;
    qs('#pdcaFindings').innerHTML=(d.findings||[]).map(x=>`<article class="pdca-item"><div class="pdca-item-head"><strong>${esc(x.id)} ${esc(x.title)}</strong><span>${esc(x.status||'')}</span></div><p><b>観測</b> ${esc(x.observation)}</p><p><b>リスク</b> ${esc(x.risk)}</p><p><b>対応</b> ${esc(x.current_action)}</p></article>`).join('');
    qs('#pdcaImprovements').innerHTML=(d.improvement_candidates||[]).map(x=>`<article class="pdca-item"><div class="pdca-item-head"><strong>P${esc(x.priority)} ${esc(x.name)}</strong></div><p><b>方法</b> ${esc(x.method)}</p><p><b>狙い</b> ${esc(x.expected_effect)}</p><p><b>検証</b> ${esc(x.validation)}</p><p><b>採用条件</b> ${esc(x.promotion_gate)}</p></article>`).join('');
    qs('#pdcaMetrics').innerHTML=(v.metrics||[]).map(x=>`<span>${esc(x)}</span>`).join('');
    qs('#pdcaGovernance').innerHTML=[...(v.decomposition||[]),...(v.governance||[])].map(x=>`<div class="pdca-rule">${esc(x)}</div>`).join('');
  }catch(e){
    qs('#pdcaReportStatus').textContent='DATA ERROR';
    qs('#pdcaReportSummary').innerHTML='<p class="muted">PDCA詳細レポートを読み込めませんでした。</p>';
  }
}
loadPdcaReport();
