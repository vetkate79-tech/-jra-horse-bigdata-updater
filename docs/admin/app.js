const DEFAULT_DATA_URL = '../data/dashboard.json';
const qs = (s) => document.querySelector(s);
const qsa = (s) => [...document.querySelectorAll(s)];

const titles = {today:'今日の運用',races:'レース管理',models:'モデル管理',pdca:'PDCA / 検証',analysis:'データ分析',audit:'監査ログ',system:'システム状態',report:'報告内容','site-analytics':'サイト分析'};

qs('#refreshButton')?.addEventListener('click',()=>{
  const url=new URL(location.href);
  url.searchParams.set('refresh',Date.now().toString());
  location.replace(url.toString());
});

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
  const shadowRegistry=qs('#shadowRegistry');
  if(shadowRegistry)shadowRegistry.innerHTML=(data.shadow_registry||[]).map(x=>`<article class="model-card"><div class="row"><strong>${esc(x.name)}</strong><span>${esc(x.status)}</span></div><p><b>現在地</b> ${esc(x.stage)}</p><p><b>根拠</b> ${esc(x.evidence)}</p><p><b>昇格まで</b> ${esc(x.remaining)}</p><p class="muted">${esc(x.code)}</p></article>`).join('')||'<p class="muted">Shadow登録なし</p>';

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
  const runtime=data.runtime_ownership||{}, gh=runtime.github_pages||{}, mirror=runtime.standby_sync||{}, replit=runtime.replit||{};
  const runtimeRows=[
    {name:'本番実行オーナー',value:runtime.runtime_owner_repo||'-',detail:'JRA取得・純予想・封印・市場・結果・PDCAの正規実行元'},
    {name:'正規公開URL',value:runtime.canonical_public_url||'-',detail:'ユーザー向けの唯一の正規公開面'},
    {name:'GitHub Pages',value:gh.role||'未定義',detail:gh.note||''},
    {name:'配信用ミラー',value:mirror.repository||runtime.standby_repo||'-',detail:'静的ミラー/バックアップ。予想・市場・結果・PDCAを書き込まない'},
    {name:'Replit',value:replit.role||'DEVELOPMENT_ONLY',detail:replit.required_for_runtime===false?'本番必須依存なし。コード作成・修正・一時検証のみ。':'要確認'}
  ];
  qs('#runtimeOwnership').innerHTML=runtimeRows.map(x=>`<div class="risk"><div class="risk-row"><strong>${esc(x.name)}</strong><span>${esc(x.value)}</span></div><p>${esc(x.detail)}</p></div>`).join('');
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

function renderAnalysis(data){
  const a=data.analytics||{}, s=data.summary||{}, breakdowns=a.breakdowns||{}, rawRows=a.races||[];
  renderKpis(qs('#analysisKpis'),[
    {label:'累計投資',value:yen(s.stake_amount),sub:'結果接続済み購入分'},
    {label:'累計払戻',value:yen(s.return_amount),sub:'公式3連複払戻'},
    {label:'累計収支',value:yen(s.profit_amount),sub:'払戻 - 投資'},
    {label:'累計ROI',value:pct(s.roi),sub:'管理詳細'},
    {label:'最大払戻除外ROI',value:pct(s.roi_ex_top),sub:'一発依存除外'}
  ]);
  const sel=qs('#analysisDimension'),mode=qs('#analysisDateMode'),day=qs('#analysisDateDay'),from=qs('#analysisDateFrom'),to=qs('#analysisDateTo');
  const labels={date:'日付',track:'競馬場',race_no:'レース',race_category:'年齢区分',race_class:'クラス',surface:'芝/ダート',distance_m:'距離',distance_band:'距離帯',track_condition:'馬場',weather:'天候',field_size:'頭数',field_size_band:'頭数帯',decision:'購入判定',axis_grade:'軸結果',race_state:'状態'};
  const dims=Object.keys(breakdowns); sel.innerHTML=dims.map(d=>`<option value="${esc(d)}">${esc(labels[d]||d)}</option>`).join('');
  const dates=[...new Set(rawRows.map(r=>r.date).filter(Boolean))].sort(), latest=dates[dates.length-1]||'';
  if(day&&!day.value)day.value=s.display_date||latest;if(from&&!from.value)from.value=dates[0]||'';if(to&&!to.value)to.value=latest;
  const toggle=()=>{qs('#analysisDateDayWrap').hidden=mode.value!=='day';qs('#analysisDateFromWrap').hidden=mode.value!=='range';qs('#analysisDateToWrap').hidden=mode.value!=='range'};
  const filtered=()=>rawRows.filter(r=>mode.value==='all'||(mode.value==='day'&&r.date===day.value)||(mode.value==='range'&&(!from.value||r.date>=from.value)&&(!to.value||r.date<=to.value)));
  const aggregate=(rows,field)=>{const groups=new Map();for(const r of rows){const value=String(r[field]??'不明');if(!groups.has(value))groups.set(value,[]);groups.get(value).push(r)}return [...groups].map(([value,xs])=>{const bought=xs.filter(x=>x.bought),scored=xs.filter(x=>x.scored),stake=bought.reduce((n,x)=>n+Number(x.stake_yen||0),0),ret=bought.reduce((n,x)=>n+Number(x.return_yen||0),0),hits=bought.filter(x=>x.trio_hit).length,axis=scored.filter(x=>[1,2,3].includes(Number(x.axis_finish))).length,miss=bought.filter(x=>[1,2,3].includes(Number(x.axis_finish))&&!x.trio_hit).length;return{value,bought_races:bought.length,hit_rate:bought.length?hits/bought.length*100:null,axis_top3_rate:scored.length?axis/scored.length*100:null,combo_miss_rate:bought.length?miss/bought.length*100:null,stake_yen:stake,return_yen:ret,profit_yen:ret-stake,roi:stake?ret/stake*100:null}})};
  const draw=()=>{toggle();const rows=mode.value==='all'?(breakdowns[sel.value]||[]):aggregate(filtered(),sel.value);qs('#analysisTableBody').innerHTML=rows.map(r=>`<tr><td><b>${esc(r.value)}</b></td><td>${r.bought_races||0}</td><td>${r.hit_rate==null?'-':pct(r.hit_rate)}</td><td>${r.axis_top3_rate==null?'-':pct(r.axis_top3_rate)}</td><td>${r.combo_miss_rate==null?'-':pct(r.combo_miss_rate)}</td><td>${yen(r.stake_yen)}</td><td>${yen(r.return_yen)}</td><td>${yen(r.profit_yen)}</td><td>${r.roi==null?'-':pct(r.roi)}</td></tr>`).join('')||'<tr><td colspan="9" class="muted">来週のレース終了までお待ちください</td></tr>'};
  [sel,mode,day,from,to].forEach(x=>{if(x)x.onchange=draw});draw();
  qs('#optimizerList').innerHTML=(a.optimization_candidates||[]).map(x=>`<div class="model-card"><div class="row"><strong>${esc(x.type)} · ${esc(labels[x.dimension]||x.dimension)}=${esc(x.value)}</strong><span>${esc(x.status)}</span></div><p>sample ${esc(x.sample)} / ROI ${x.roi==null?'-':pct(x.roi)} / 軸生存 ${x.axis_top3_rate==null?'-':pct(x.axis_top3_rate)} / 組合せ漏れ ${x.combo_miss_rate==null?'-':pct(x.combo_miss_rate)}</p><p>${esc(x.action)}</p></div>`).join('')||'<p class="muted">改善候補なし。最低サンプル到達後に自動生成します。</p>';
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

// Source lineage: live_pdca.json -> erp-pdca-latest.json
async function loadPdcaReport(){
  try{
    const r=await fetch('../data/erp-pdca-latest.json',{cache:'no-store'});
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

async function loadComparisonReport(){
  if(!qs('#comparisonReportContent'))return;
  try{
    const [lr,latestResponse]=await Promise.all([fetch('../data/erp-report-log.json',{cache:'no-store'}),fetch('../data/erp-report-latest.json',{cache:'no-store'})]);if(!lr.ok)throw new Error('LOG');
    const log=await lr.json(),reports=log.reports||[];
    qs('#comparisonReportStatus').textContent=reports.some(x=>x.status==='COMPLETED')?'更新済み':'結果待ち';
    qs('#comparisonReportContent').innerHTML=reports.map((x,i)=>`<details class="report-tree-node" ${i===0?'open':''}><summary><span>${esc(x.date||'')}</span><strong>${esc(x.title||'報告')}</strong><em>${esc(x.status||'')}</em></summary><div class="report-tree-body"><div class="report-note"><b>依頼内容</b><span>${esc(x.request||'')}</span></div><div class="report-note"><b>結果</b><span>${esc(x.result||'')}</span></div><div class="report-note"><b>考察</b><span>${esc(x.consideration||'')}</span></div></div></details>`).join('');
    if(!latestResponse.ok)throw new Error('WAITING');
    const d=await latestResponse.json();
    qs('#comparisonRaceBody').innerHTML=(d.race_details||[]).map(x=>`<tr><td><b>${esc(x.track)} ${esc(x.race_no)}R</b></td><td>${esc(x.old_axis||'-')}</td><td>${esc(x.new_axis||'-')}</td><td>${esc((x.actual_top3||[]).join('-'))}</td><td>${x.old_axis_top3?'軸○':'軸×'} / ${x.old_trio_hit?'的中':'外れ'}</td><td>${x.new_axis_top3?'軸○':'軸×'} / ${x.new_trio_hit?'的中':'外れ'}</td></tr>`).join('');
  }catch(e){
    if(!qs('#comparisonReportContent').innerHTML){qs('#comparisonReportStatus').textContent='全結果待ち';qs('#comparisonReportContent').innerHTML='<div class="report-note"><b>状態</b><span>報告ログを準備しています。</span></div>'}
    qs('#comparisonRaceBody').innerHTML='<tr><td colspan="6" class="muted">全レース結果確定後に自動掲載</td></tr>';
  }
}
loadComparisonReport();

async function loadSiteAnalytics(){
  if(!qs('#siteAnalyticsKpis'))return;
  try{
    const r=await fetch('../data/site_analytics.json',{cache:'no-store'});if(!r.ok)throw new Error('HTTP '+r.status);
    const d=await r.json(),t=d.traffic||{},a=d.affiliate||{};
    qs('#analyticsConnection').textContent=d.status==='CONNECTED'?'接続済み':'未接続';
    renderKpis(qs('#siteAnalyticsKpis'),[
      {label:'ページ表示',value:t.pageviews==null?'未接続':Number(t.pageviews).toLocaleString('ja-JP'),sub:'選択期間'},
      {label:'利用者',value:t.users==null?'未接続':Number(t.users).toLocaleString('ja-JP'),sub:'重複除外'},
      {label:'セッション',value:t.sessions==null?'未接続':Number(t.sessions).toLocaleString('ja-JP'),sub:'訪問回数'},
      {label:'成果クリック',value:a.clicks==null?'未接続':Number(a.clicks).toLocaleString('ja-JP'),sub:'広告・提携導線'},
      {label:'確定報酬',value:a.revenue_yen==null?'未接続':yen(a.revenue_yen),sub:'承認済み成果'}]);
    qs('#trafficDetails').innerHTML=(d.traffic_dimensions||[]).map(x=>`<div class="risk"><div class="risk-row"><strong>${esc(x.label)}</strong><span>${esc(x.status)}</span></div><p>${esc(x.detail)}</p></div>`).join('');
    qs('#affiliateDetails').innerHTML=(d.affiliate_dimensions||[]).map(x=>`<div class="risk"><div class="risk-row"><strong>${esc(x.label)}</strong><span>${esc(x.status)}</span></div><p>${esc(x.detail)}</p></div>`).join('');
    qs('#analyticsRoadmap').innerHTML=(d.roadmap||[]).map(x=>`<div class="model-card"><div class="row"><strong>${esc(x.name)}</strong><span>${esc(x.status)}</span></div><p>${esc(x.detail)}</p></div>`).join('');
  }catch(e){qs('#analyticsConnection').textContent='DATA ERROR';renderKpis(qs('#siteAnalyticsKpis'),[{label:'計測データ',value:'未接続',sub:'データ源の接続待ち'}]);}
}
loadSiteAnalytics();
