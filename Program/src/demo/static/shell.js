'use strict';
// Shared, local-only navigation. Data availability is supplied by the analysis page.
window.GameShell = (() => {
  const sections = [
    ['overview', '市場總覽', 'overview'],
    ['distribution', '數量與價格分布', 'distribution'],
    ['relationships', '變數之間的關係', 'relationships'],
    ['cohorts', '按發售時間比較', 'cohorts'],
    ['rankings', '遊戲排名與明細', 'rankings'],
  ];
  const icons = {
    overview:'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',
    distribution:'M4 20V12h4v8 M10 20V4h4v16 M16 20V8h4v12 M2 20h20',
    relationships:'M4 17l5-6 5 3 6-9 M4 17h.01 M9 11h.01 M14 14h.01 M20 5h.01',
    cohorts:'M3 5h18v16H3z M7 3v4 M17 3v4 M3 10h18 M7 14h3 M14 17h3',
    rankings:'M8 6h13 M8 12h13 M8 18h13 M3 6h1 M3 12h1 M3 18h1',
    revenue:'M4 20h16 M6 17V9 M12 17V4 M18 17v-6',
  };
  const element=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
  const icon=name=>{const n=document.createElementNS('http://www.w3.org/2000/svg','svg');n.setAttribute('viewBox','0 0 24 24');n.setAttribute('aria-hidden','true');n.setAttribute('focusable','false');const p=document.createElementNS(n.namespaceURI,'path');p.setAttribute('d',icons[name]||icons.overview);n.append(p);return n;};
  const marketLinks=new Map(),links=[];
  let activeMarket=sections.some(([id])=>id===location.hash.slice(1))?location.hash.slice(1):'overview';
  let opened=false;
  const mobile=matchMedia('(max-width: 960px)');
  const header=document.querySelector('body > header'),main=document.querySelector('body > main');
  if(!header||!main)return {setMarketSections(){},setMarketSection(){}};
  document.body.classList.add('app-shell');header.className='app-header';main.id=main.id||'main-content';main.tabIndex=-1;
  header.replaceChildren();
  const skip=element('a','跳到主要內容','app-skip');skip.href='#'+main.id;document.body.prepend(skip);
  const toggle=element('button',undefined,'app-menu-toggle');toggle.type='button';toggle.setAttribute('aria-label','開啟導覽選單');toggle.setAttribute('aria-expanded','false');toggle.setAttribute('aria-controls','app-sidebar');toggle.append(element('span','☰'));
  const brand=element('a',undefined,'brand');brand.href='/market';brand.append(element('span','◈','app-brand-symbol'),document.createTextNode('GameScope'));
  const brandBlock=element('div',undefined,'app-brand-block');brandBlock.append(toggle,brand);
  const heading=element('div',undefined,'app-page-context'),crumb=element('span','資料分析','app-page-group'),pageTitle=element('strong','市場總覽','app-page-title');heading.append(crumb,pageTitle);
  const badge=element('span','歷史資料 · 本機工具','app-status-badge');header.append(brandBlock,heading,badge);
  const sidebar=element('aside',undefined,'app-sidebar');sidebar.id='app-sidebar';sidebar.setAttribute('aria-label','GameScope 導覽');
  const close=element('button','關閉選單 ×','app-sidebar-close');close.type='button';close.addEventListener('click',()=>setOpen(false));sidebar.append(close);
  const nav=element('nav');nav.setAttribute('aria-label','主要導覽');sidebar.append(nav);
  const makeGroup=(title,subheading)=>{const group=element('section',undefined,'app-nav-group');group.append(element('h2',title),element('p',subheading,'app-nav-hint'));const list=element('ul');group.append(list);nav.append(group);return list;};
  const analysis=makeGroup('資料分析','從歷史資料探索市場');
  function addLink(list,{id,href,title,iconName,step}){
    const li=element('li'),a=element('a',undefined,'app-nav-link');a.href=href;a.dataset.shellLink=id;
    a.append(step?element('span',`Step ${step}`,'app-step'):icon(iconName));
    const body=element('span',undefined,'app-nav-link-body'),label=element('span',title,'app-nav-label');body.append(label);a.append(body);li.append(a);list.append(li);links.push({id,a,title});
    a.addEventListener('click',()=>{if(opened){setOpen(false,false);if(new URL(a.href).pathname===location.pathname)main.focus({preventScroll:true});}});
    return {a,body,label};
  }
  for(const [id,title,iconName] of sections){const item=addLink(analysis,{id,href:`/market#${id}`,title,iconName});item.a.dataset.marketSection=id;const status=element('small',undefined,'app-nav-availability');status.hidden=true;item.body.append(status);marketLinks.set(id,{...item,status});}
  addLink(analysis,{id:'revenue',href:'/revenue',title:'Steam 營收分析',iconName:'revenue'});
  const planning=makeGroup('開發規劃','以分析依據整理你的計劃');
  addLink(planning,{id:'comparison',href:'/',title:'比較規劃方向',step:1});
  const references=addLink(planning,{id:'references',href:'/revenue#reference-panel',title:'尋找相近遊戲',step:2});
  const referenceNote=element('small',undefined,'app-nav-availability');referenceNote.hidden=true;references.body.append(referenceNote);
  addLink(planning,{id:'budget',href:'/planning#budget-section',title:'估算與比較成本',step:3});
  addLink(planning,{id:'summary',href:'/plan',title:'檢視規劃摘要',step:4});
  const foot=element('div',undefined,'app-sidebar-footer');foot.append(element('strong','資料與假設分開解讀'),element('p','市場數字來自歷史樣本；成本由你的輸入計算。'));sidebar.append(foot);
  const backdrop=element('button',undefined,'app-sidebar-backdrop');backdrop.type='button';backdrop.tabIndex=-1;backdrop.setAttribute('aria-hidden','true');backdrop.hidden=true;backdrop.addEventListener('click',()=>setOpen(false));
  header.after(sidebar,backdrop);
  function current(){
    if(location.pathname==='/market')return activeMarket;
    if(location.pathname==='/revenue')return location.hash==='#reference-panel'?'references':'revenue';
    return {'/':'comparison','/planning':'budget','/plan':'summary'}[location.pathname]||'overview';
  }
  function renderCurrent(){
    const key=current();for(const {id,a,title} of links){if(id===key){a.setAttribute('aria-current','page');pageTitle.textContent=title;crumb.textContent=['comparison','references','budget','summary'].includes(id)?'開發規劃':'資料分析';}else a.removeAttribute('aria-current');}
    if(key==='references'){const panel=document.getElementById('reference-panel');if(panel)panel.open=true;}
  }
  function setMarketSection(id){if(!sections.some(([known])=>known===id))return;activeMarket=id;renderCurrent();}
  function setMarketSections(states){
    if(!Array.isArray(states))return;
    for(const state of states){const item=marketLinks.get(state.id);if(!item)continue;
      const status=String(state.status||'available'),unavailable=['unavailable','unsupported','empty','insufficient','error'].includes(status),partial=['partial','limited'].includes(status),pending=['pending','loading','unchecked'].includes(status);
      item.a.dataset.availability=status;item.status.hidden=!(unavailable||partial||pending);
      item.status.textContent=unavailable?'資料不足 · 查看原因':partial?'資料有局限':pending?'待核對資料':'';
      if(state.reason){item.a.title=String(state.reason);item.status.setAttribute('aria-label',`${item.status.textContent}：${state.reason}`);}else{item.a.removeAttribute('title');item.status.removeAttribute('aria-label');}
      // Remain navigable so users can read why a view is unavailable.
      item.a.classList.toggle('app-nav-unavailable',unavailable);
    }
  }
  function updatePlanning(state){
    const android=state?.comparison?.platform==='mobile';referenceNote.hidden=!android;referenceNote.textContent=android?'Android 尚未提供':'';
    references.a.title=android?'目前規劃為 Android；相近遊戲搜尋只提供 Steam，可在說明頁繼續成本預算。':'依玩法與觀察價格尋找 Steam 參考作品';
  }
  function setOpen(value,restoreFocus=true){
    opened=!!value&&mobile.matches;document.body.classList.toggle('app-menu-open',opened);toggle.setAttribute('aria-expanded',String(opened));toggle.setAttribute('aria-label',opened?'關閉導覽選單':'開啟導覽選單');backdrop.hidden=!opened;main.inert=opened;
    sidebar.inert=mobile.matches&&!opened;
    if(opened){sidebar.setAttribute('role','dialog');sidebar.setAttribute('aria-modal','true');close.focus();}
    else{sidebar.removeAttribute('role');sidebar.removeAttribute('aria-modal');if(restoreFocus&&mobile.matches)toggle.focus();}
  }
  toggle.addEventListener('click',()=>setOpen(!opened));mobile.addEventListener('change',()=>setOpen(false,false));
  document.addEventListener('keydown',event=>{if(!opened)return;if(event.key==='Escape'){event.preventDefault();setOpen(false);return;}if(event.key!=='Tab')return;const focusable=[...sidebar.querySelectorAll('a[href],button:not([disabled])')].filter(n=>n.getClientRects().length);const first=focusable[0],last=focusable.at(-1);if(event.shiftKey&&(document.activeElement===first||!sidebar.contains(document.activeElement))){event.preventDefault();last.focus();}else if(!event.shiftKey&&(document.activeElement===last||!sidebar.contains(document.activeElement))){event.preventDefault();first.focus();}});
  window.addEventListener('hashchange',()=>{if(location.pathname==='/market'&&sections.some(([id])=>id===location.hash.slice(1)))activeMarket=location.hash.slice(1);renderCurrent();});
  window.addEventListener('DOMContentLoaded',()=>updatePlanning(window.PlanningFlow?.read()));
  setOpen(false,false);renderCurrent();
  return {setMarketSection,setMarketSections,updatePlanning};
})();
