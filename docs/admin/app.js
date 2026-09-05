const DEFAULT_DATA_URL = '../data/dashboard.json';
const qs = (s) => document.querySelector(s);
const qsa = (s) => [...document.querySelectorAll(s)];

const titles = {today:'今日の運用',races:'レース管理',models:'モデル管理',pdca:'PDCA / 検証',analysis:'データ分析',audit:'監査ログ',system:'システム状態',report:'報告内容'};

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
  renderAnalysis(data);
  renderUpgradeLog(data);
}

function renderUpgradeLog(data){
  const d=data.upgrade_log||{}, rows=d.upgrades||[];
  const tracking=d.tracking_started_at||'-';
  qs('#upgradeTrackingStatus').textContent=`追跡開始 ${tracking}`;
  if(!rows.length){
    qs('#upgradeLogList').innerHTML=`<div class="pdca-rule"><b>正式アップグレード履歴なし</b><br>追跡開始以降、完全アップグレードが実施された時だけここへ記録します。過去履歴は根拠なしで後付けしません。</div>`;
    return;
  }
  qs('#upgradeLogList').innerHTML=[...rows].reverse().map(x=>{
    const h=x.post_upgrade_health||{}, cmp=x.comparison_at_promotion||{}, health=h.label||h.status||'未評価';
    const validation=Array.isArray(x.validation_path)?x.validation_path.join(' → '):String(x.validation_path||'');
    const gate=typeof x.promotion_gate==='string'?x.promotion_gate:JSON.stringify(x.promotion_gate||{});
    const promotion=typeof cmp==='string'?cmp:JSON.stringify(cmp);
    return `<article class="pdca-item upgrade-item">
      <div class="pdca-item-head"><strong>${esc(x.from_model||'-')} → ${esc(x.to_model||'-')}</strong><span>${esc(x.promoted_at||'')}</span></div>
      <p><b>改善した理由</b> ${esc(x.reason_for_change||'-')}</p>
      <p><b>変更内容</b> ${esc(x.change_summary||'-')}</p>
      <p><b>検証経路</b> ${esc(validation||'-')}</p>
      <p><b>昇格条件</b> ${esc(gate||'-')}</p>
      <p><b>昇格時の旧モデル比較</b> ${esc(promotion||'-')}</p>
      <p><b>昇格後の現在</b> ${esc(health)}</p>
      ${h.current_model_metrics?`<p><b>現在値</b> ROI ${pct(h.current_model_metrics.roi)} / 的中 ${pct(h.current_model_metrics.hit_rate)} / 軸生存 ${pct(h.current_model_metrics.axis_survival)} / 組合せ漏れ ${pct(h.current_model_metrics.combo_miss_rate)} / ${esc(h.current_model_metrics.sample_scored_races)}R</p>`:''}
    </article>`;
  }).join('');
}

function summarizeRows(rows){
  const scored=rows.filter(x=>x.scored), bought=scored.filter(x=>x.bought);
  const stake=bought.reduce((s,x)=>s+Number(x.stake_yen||0),0);
  const ret=bought.reduce((s,x)=>s+Number(x.return_yen||0),0);
  const hits=bought.filter(x=>x.trio_hit).length;
  const axisTop3=scored.filter(x=>[1,2,3].includes(Number(x.axis_finish))).length;
  const comboMiss=bought.filter(x=>[1,2,3].includes(Number(x.axis_finish))&&!x.trio_hit).length;
  const returns=bought.map(x=>Number(x.return_yen||0)).sort((a,b)=>b-a);
  const retExTop=ret-(returns[0]||0);
  return {
    total_races:rows.length,scored_races:scored.length,bought_races:bought.length,
    stake_amount:stake,return_amount:ret,profit_amount:ret-stake,
    hit_rate:bought.length?hits/bought.length*100:null,hits,
    axis_survival:scored.length?axisTop3/scored.length*100:null,
    combo_miss_rate:bought.length?comboMiss/bought.length*100:null,
    roi:stake?ret/stake*100:null,roi_ex_top:stake?retExTop/stake*100:null
  };
}
function groupRows(rows,field){
  const groups=new Map();
  rows.forEach(r=>{let v=r[field];if(v==null||v==='')v='不明';const k=String(v);if(!groups.has(k))groups.set(k,[]);groups.get(k).push(r)});
  const out=[...groups].map(([value,xs])=>({value,...summarizeRows(xs)}));
  if(field==='race_no')return out.sort((a,b)=>(Number(a.value)||999)-(Number(b.value)||999));
  return out.sort((a,b)=>b.scored_races-a.scored_races||String(a.value).localeCompare(String(b.value),'ja'));
}
function jstNowParts(){
  const parts=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Tokyo',year:'numeric',month:'2-digit',day:'2-digit',weekday:'short'}).formatToParts(new Date());
  const g=t=>parts.find(x=>x.type===t)?.value||'';
  return {date:`${g('year')}-${g('month')}-${g('day')}`,weekday:g('weekday')};
}
function weeklyRowsForDisplay(rows){
  const now=jstNowParts(), wd=now.weekday;
  if(['Tue','Wed','Thu','Fri'].includes(wd))return {waiting:true,rows:[],label:'来週のレース終了までお待ちください'};
  const scoredDates=[...new Set(rows.filter(x=>x.scored).map(x=>x.date).filter(Boolean))].sort();
  if(!scoredDates.length)return {waiting:false,rows:[],label:'今週の結果接続待ち'};
  const latest=scoredDates.at(-1);
  const base=new Date(latest+'T00:00:00+09:00');
  const day=base.getUTCDay();
  const sat=new Date(base); sat.setUTCDate(base.getUTCDate()-(day===0?1:0));
  const sun=new Date(sat); sun.setUTCDate(sat.getUTCDate()+1);
  const iso=d=>d.toISOString().slice(0,10);
  const dates=new Set([iso(sat),iso(sun)]);
  const selected=rows.filter(x=>dates.has(x.date)&&x.scored);
  return {waiting:false,rows:selected,label:`${[...dates].join('〜')} / ${selected.length}R結果接続`};
}
function renderAnalysis(data){
  const a=data.analytics||{}, allRows=a.races||[];
  const weekly=weeklyRowsForDisplay(allRows);
  qs('#weeklyResultStatus').textContent=weekly.label;
  qs('#weeklyResultMessage').textContent=weekly.waiting?'火曜日以降は次開催の結果待ち表示です。過去データは条件別分析から引き続き参照できます。':'';
  if(weekly.waiting){
    renderKpis(qs('#analysisKpis'),[
      {label:'今週の暫定結果',value:'結果待ち',sub:'来週のレース終了後に更新'},
      {label:'投資',value:'-',sub:'過去データは保持済み'},
      {label:'払戻',value:'-',sub:'過去データは保持済み'},
      {label:'ROI',value:'-',sub:'次開催待ち'},
      {label:'軸生存率',value:'-',sub:'次開催待ち'}
    ]);
  }else{
    const s=summarizeRows(weekly.rows);
    renderKpis(qs('#analysisKpis'),[
      {label:'今週の投資',value:yen(s.stake_amount),sub:`${s.bought_races}R購入評価`},
      {label:'今週の払戻',value:yen(s.return_amount),sub:`${s.hits}R的中`},
      {label:'今週の収支',value:yen(s.profit_amount),sub:'払戻 - 投資'},
      {label:'今週のROI',value:s.roi==null?'-':pct(s.roi),sub:'暫定'},
      {label:'今週の軸生存率',value:s.axis_survival==null?'-':pct(s.axis_survival),sub:`${s.scored_races}R結果接続`}
    ]);
  }

  const labels={date:'日付',track:'競馬場',race_no:'レース',race_category:'年齢区分',race_class:'クラス',surface:'芝/ダート',distance_m:'距離',distance_band:'距離帯',track_condition:'馬場',weather:'天候',field_size:'頭数',field_size_band:'頭数帯',decision:'購入判定',axis_grade:'軸結果',race_state:'状態'};
  const dims=['date','track','race_no','race_category','race_class','surface','distance_m','distance_band','track_condition','weather','field_size','field_size_band','decision','axis_grade','race_state'];
  const sel=qs('#analysisDimension'), mode=qs('#analysisDateMode'), from=qs('#analysisDateFrom'), to=qs('#analysisDateTo'), day=qs('#analysisDateDay');
  sel.innerHTML=dims.map(d=>`<option value="${esc(d)}">${esc(labels[d]||d)}</option>`).join('');
  const dates=[...new Set(allRows.map(r=>r.date).filter(Boolean))].sort();
  const min=dates[0]||'',max=dates.at(-1)||'';
  [from,to,day].forEach(x=>{if(min)x.min=min;if(max)x.max=max});
  if(!from.value)from.value=min;if(!to.value)to.value=max;if(!day.value)day.value=max;

  const updateVisibility=()=>{
    const m=mode.value;
    qs('#analysisFromWrap').hidden=m!=='range';
    qs('#analysisToWrap').hidden=m!=='range';
    qs('#analysisDayWrap').hidden=m!=='day';
  };
  const filtered=()=>{
    if(mode.value==='day')return allRows.filter(r=>r.date===day.value);
    if(mode.value==='range')return allRows.filter(r=>(!from.value||r.date>=from.value)&&(!to.value||r.date<=to.value));
    return allRows;
  };
  const draw=()=>{
    updateVisibility();
    const subset=filtered(), rows=groupRows(subset,sel.value);
    qs('#analysisTableBody').innerHTML=rows.map(r=>`<tr><td><b>${esc(r.value)}</b></td><td>${r.bought_races||0}</td><td>${r.hit_rate==null?'-':pct(r.hit_rate)}</td><td>${r.axis_survival==null?'-':pct(r.axis_survival)}</td><td>${r.combo_miss_rate==null?'-':pct(r.combo_miss_rate)}</td><td>${yen(r.stake_amount)}</td><td>${yen(r.return_amount)}</td><td>${yen(r.profit_amount)}</td><td>${r.roi==null?'-':pct(r.roi)}</td></tr>`).join('')||'<tr><td colspan="9" class="muted">指定期間の集計データなし</td></tr>';
  };
  [sel,mode,from,to,day].forEach(x=>x.onchange=draw); draw();

  qs('#optimizerList').innerHTML=(a.optimization_candidates||[]).map(x=>`<div class="model-card"><div class="row"><strong>${esc(x.type)} · ${esc(labels[x.dimension]||x.dimension)}=${esc(x.value)}</strong><span>${esc(x.status)}</span></div><p>sample ${esc(x.sample)} / ROI ${x.roi==null?'-':pct(x.roi)} / 軸生存 ${x.axis_top3_rate==null?'-':pct(x.axis_top3_rate)} / 組合せ漏れ ${x.combo_miss_rate==null?'-':pct(x.combo_miss_rate)}</p><p>${esc(x.action)}</p></div>`).join('')||'<p class="muted">改善候補なし。最低サンプル到達後に自動生成します。</p>';
}

function renderBars(el,items){
  const max=Math.max(1,...items.map(x=>Number(x.value||0)));
  el.innerHTML=items.map(x=>`<div><div class="bar-label"><span>${esc(x.label)}</span><span>${esc(x.value)}</span></div><div class="bar-track"><div class="bar-fill" style="width:${Math.max(2,Number(x.value||0)/max*100)}%"></div></div></div>`).join('') || '<p class="muted">データなし</p>';
}

async function boot(){
  const dataUrl = new URLSearchParams(location.search).get('data') || window.JRA_ERP_DATA_URL || DEFAULT_DATA_URL;
  try{
    const [res,detailRes]=await Promise.all([fetch(dataUrl,{cache:'no-store'}),fetch('../data/management_analytics.json',{cache:'no-store'})]);
    if(!res.ok) throw new Error(`HTTP ${res.status}`);
    const data=await res.json();
    if(detailRes.ok){
      const detail=await detailRes.json();
      data.analytics={...(data.analytics||{}),races:detail.races||[],summary:detail.summary||data.analytics?.summary};
    }
    render(data);
  }
  catch(err){qs('#connectionLabel').textContent='DATA NOT CONNECTED';qs('.sidebar-footer .dot').className='dot bad';render({summary:{},analytics:{races:[]},risks:[{name:'データ接続',level:'bad',detail:`${dataUrl} を取得できません。予想側が共通JSONを出力すると自動表示されます。`}],sources:[{name:'ERP data adapter',status:'bad',detail:String(err.message||err)}],mechanisms:[]});}
}
boot();

async function loadPdcaReport(){
  try{
    const r=await fetch('../data/live_pdca.json',{cache:'no-store'});
    if(!r.ok)throw new Error('HTTP '+r.status);
    const d=await r.json();
    qs('#pdcaReportStatus').textContent=d.mode||'POST_RESULT_PDCA_ONLY';
    const scored=Number(d.scored_race_count||0),pending=Number(d.pending_race_count||0);
    qs('#pdcaReportSummary').innerHTML=
      `<div class="report-lead"><strong>最新の実運用PDCA</strong><p>結果接続 ${scored}R / 結果待ち ${pending}R</p></div>`+
      `<div class="report-note"><b>学習目標</b><span>${esc(d.axis_learning_objective||'TOP3_SURVIVAL_FIRST')}</span></div>`+
      `<div class="report-note"><b>固定ルール</b><span>${esc(d.governance||'結果後の診断は封印済み予想を書き換えない')}</span></div>`;
    const fc=d.failure_counts||{},dc=d.detailed_failure_counts||{};
    const findings=[
      ['軸飛び',fc.axis_outside_top3||0],
      ['軸生存・三連複漏れ',fc.axis_survived_but_trio_missed||0],
      ['軸＋三連複的中',fc.axis_and_trio_hit||0],
      ['相手候補漏れ',dc.OPPONENT_CANDIDATE_MISS||0],
      ['買い目変換漏れ',dc.TICKET_CONVERSION_MISS||0]
    ];
    qs('#pdcaFindings').innerHTML=findings.map(x=>`<article class="pdca-item"><div class="pdca-item-head"><strong>${esc(x[0])}</strong><span>${esc(x[1])}R</span></div></article>`).join('');
    qs('#pdcaImprovements').innerHTML=(d.recommended_actions||[]).map((x,i)=>`<article class="pdca-item"><div class="pdca-item-head"><strong>P${i+1}</strong></div><p>${esc(x)}</p></article>`).join('')||'<p class="muted">結果接続後に自動生成</p>';
    qs('#pdcaMetrics').innerHTML=['軸3着内率','三連複的中率','相手候補漏れ','買い目変換漏れ'].map(x=>`<span>${esc(x)}</span>`).join('');
    qs('#pdcaGovernance').innerHTML=[
      '封印済み予想は結果後に変更しない',
      'PDCAは診断専用でproductionを自動上書きしない',
      '過去PDCAは日付・予想ハッシュ別historyへ保存'
    ].map(x=>`<div class="pdca-rule">${esc(x)}</div>`).join('');
  }catch(e){
    qs('#pdcaReportStatus').textContent='DATA ERROR';
    qs('#pdcaReportSummary').innerHTML='<p class="muted">最新PDCAデータを読み込めませんでした。</p>';
  }
}

async function loadComparisonReport(){
  try{
    const r=await fetch('../data/erp-report-latest.json',{cache:'no-store'});
    if(!r.ok)throw new Error('WAITING');
    const d=await r.json(),c=d.report_content||{},m=d.comparison||{};
    qs('#comparisonReportStatus').textContent=d.status||'COMPLETED';
    qs('#comparisonReportContent').innerHTML=`<div class="report-note"><b>依頼内容</b><span>${esc(c.request||'')}</span></div><div class="report-note"><b>結果</b><span>${esc(c.result||'')}</span></div><div class="report-note"><b>考察</b><span>${esc(c.consideration||'')}</span></div><div class="report-note"><b>自動発火</b><span>${esc(d.trigger?.condition||'')}／${esc(d.trigger?.scheduled_runs||'')}</span></div>`;
    qs('#comparisonRaceBody').innerHTML=(d.race_details||[]).map(x=>`<tr><td><b>${esc(x.track)} ${esc(x.race_no)}R</b></td><td>${esc(x.old_axis||'-')}</td><td>${esc(x.new_axis||'-')}</td><td>${esc((x.actual_top3||[]).join('-'))}</td><td>${x.old_axis_top3?'軸○':'軸×'} / ${x.old_trio_hit?'的中':'外れ'}</td><td>${x.new_axis_top3?'軸○':'軸×'} / ${x.new_trio_hit?'的中':'外れ'}</td></tr>`).join('');
  }catch(e){
    qs('#comparisonReportStatus').textContent='比較対象の全結果待ち';
    qs('#comparisonReportContent').innerHTML='<div class="report-note"><b>依頼内容</b><span>比較対象開催の終了後、新型と旧型を同じJRA公式結果で比較する。</span></div><div class="report-note"><b>状態</b><span>ERP Workflowが対象レースの1〜3着確定を確認後、自動生成します。</span></div>';
    qs('#comparisonRaceBody').innerHTML='<tr><td colspan="6" class="muted">全レース結果確定後に自動掲載</td></tr>';
  }
}
loadComparisonReport();
