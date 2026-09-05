(()=>{
  const root='/-jra-horse-bigdata-updater/';
  if(location.pathname.startsWith(root+'admin'))return;
  document.querySelectorAll('.mobile-nav,.global-bottom-nav').forEach(x=>x.remove());
  const items=[
    ['ホーム',root],['馬を選ぶ',root+'app/'],['馬データ',root+'horses/'],['AI',root+'consult/'],['ワード',root+'words/']
  ];
  const style=document.createElement('style');
  style.textContent=`body{padding-bottom:88px!important}.global-bottom-nav{position:fixed;z-index:2147483000;left:50%;bottom:0;transform:translateX(-50%);width:min(100%,720px);display:grid;grid-template-columns:repeat(5,1fr);background:rgba(255,253,249,.96);border:1px solid #e6e0d6;border-bottom:0;border-radius:24px 24px 0 0;box-shadow:0 -8px 28px rgba(31,48,39,.09);padding:max(11px,env(safe-area-inset-bottom)) 8px calc(11px + env(safe-area-inset-bottom));backdrop-filter:blur(14px)}.global-bottom-nav a{position:relative;color:#647168;text-decoration:none;text-align:center;font-size:12px;font-weight:800;line-height:1.35;padding:8px 2px}.global-bottom-nav a[aria-current=page]{color:#2f6a4f}.global-bottom-nav a[aria-current=page]::after{content:'';position:absolute;left:22%;right:22%;bottom:0;height:4px;border-radius:9px;background:#5b8c70}@media(max-width:420px){.global-bottom-nav a{font-size:11px}}`;
  document.head.append(style);
  const nav=document.createElement('nav');nav.className='global-bottom-nav';nav.setAttribute('aria-label','共通メニュー');
  const path=location.pathname.replace(/index\.html$/,'');
  items.forEach(([label,href],i)=>{const a=document.createElement('a');a.href=href;a.textContent=label;const active=i===0?path===root:path.startsWith(href);if(active)a.setAttribute('aria-current','page');nav.append(a)});
  document.body.append(nav);
})();
