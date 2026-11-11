'use strict';
// The catalogue supplies prices; users supply quantities, eligibility and FX.
window.FeePlanner = class {
  constructor(onChange) {
    this.onChange=onChange; this.catalogue=null; this.items=[];
    this.$=id=>document.getElementById(id);
    this.node=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
    this.fmt=n=>Number(n).toLocaleString('en-US',{maximumFractionDigits:6});
    ['fee-search','fee-category','fee-currency'].forEach(id=>this.$(id).addEventListener('input',()=>this.renderCatalogue()));
  }
  async load() {
    try {
      const response=await fetch('/api/planning/fees'),data=await response.json();
      if(!response.ok)throw new Error(data.error);
      this.catalogue=data;
      this.$('fee-count').textContent=`${data.metadata.fee_count} 項 · ${data.metadata.source_count} 個來源 · 查閱 ${data.metadata.accessed_on.join('、')}`;
      this.$('fee-downloads').hidden=false;this.renderCatalogue();
    } catch(e) {this.$('fee-status').textContent=`費用資料未能載入：${e.message} 可繼續使用手動預算。`;}
  }
  link(s) {
    const a=this.node('a',`${s.publisher} · ${s.title}`);a.href=s.url;a.target='_blank';a.rel='noopener noreferrer';return a;
  }
  price(r) {
    if(r.price_status==='custom_quote')return '需要個別報價';
    if(r.price_status==='rule_dependent')return '須按交易條件核對';
    if(r.price_status==='conditional_rate')return `${this.fmt(r.rate_fraction*100)}% · 條件式分成`;
    if(r.price_status==='free')return '免費基本授權／方案';
    const units={seat:'席位',user:'使用者',licence:'授權',game:'遊戲',app:'App',developer_account:'開發者帳戶',membership:'會員',device:'設備'};
    const periods={month:'月',year:'年',one_time:'一次性'};
    return `${r.price_status==='minimum'?'最低 ':''}${r.currency} ${this.fmt(r.amount)} / ${units[r.charging_unit]||r.charging_unit} · ${periods[r.display_period]||r.display_period}`;
  }
  terms(r) {
    const modes={free:'基本費用為零；仍須符合資格',one_time:'一次性費用',annual:'按完整年度計算',committed_monthly:`按月繳付；${r.commitment_months} 個月承諾期`,monthly_assumption_required:'合約期未核實；需填逐月預算假設'};
    return modes[r.calculation_mode]||'僅供參考，不計入固定成本';
  }
  details(r) {
    const d=this.node('details',undefined,'fee-details');d.append(this.node('summary','條件與官方來源'));
    if(r.eligibility)d.append(this.node('p',`適用資格：${r.eligibility}`));
    d.append(this.node('p',r.conditions));
    if(r.configuration)d.append(this.node('p',`配置：${r.configuration}`));
    d.append(this.node('p',`查閱 ${r.accessed_on} · ${r.market_locale}`,'fine'));
    if(r.tax_status!=='not_applicable')d.append(this.node('p',r.tax_status==='excludes_applicable_taxes'?'來源價格未含適用稅項。':'來源稅項處理未確定，未自動加入稅項。','fine'));
    if(r.applicability==='optional_apple_platform_reference')d.append(this.node('p','Apple 平台擴展參考；並非 Steam／Android 必需費用。','fine'));
    if(r.applicability==='non_game_reference_only')d.append(this.node('p','其他商業用途參考；不作一般遊戲開發的額外席位費。','fine'));
    for(const s of r.sources){d.append(this.link(s),this.node('p',`原文位置：${s.source_locator}`,'fine'));if(s.evidence_method==='official_search_extract')d.append(this.node('p','本項依官方網頁的搜尋索引文字核對；直接擷取未成功。','fine'));}
    return d;
  }
  renderCatalogue() {
    if(!this.catalogue)return;
    const query=this.$('fee-search').value.trim().toLowerCase(),category=this.$('fee-category').value,currency=this.$('fee-currency').value;
    const rows=this.catalogue.fees.filter(r=>(!query||`${r.product} ${r.vendor} ${r.plan}`.toLowerCase().includes(query))&&(!category||r.category===category)&&(!currency||r.currency===currency));
    const table=this.node('table'),head=this.node('thead'),hr=this.node('tr');
    ['工具／方案','參考價格與計費方式','資格與來源','選用'].forEach(text=>{const th=this.node('th',text);th.scope='col';hr.append(th);});head.append(hr);table.append(head);
    const body=this.node('tbody');
    for(const r of rows){
      const tr=this.node('tr');tr.dataset.feeId=r.fee_id;
      const name=this.node('td');name.append(this.node('strong',r.product),this.node('small',r.plan));
      const price=this.node('td');price.append(this.node('span',this.price(r)),this.node('small',this.terms(r)));
      const evidence=this.node('td');evidence.append(this.details(r));
      const action=this.node('td'),used=this.items.some(i=>i.reference.vendor===r.vendor&&i.reference.product===r.product);
      const button=this.node('button',used?'已選此工具':r.calculation_mode?'加入預算':'僅供參考','outline');button.type='button';button.disabled=used||!r.calculation_mode;button.dataset.addFee=r.fee_id;
      button.addEventListener('click',()=>this.add(r));action.append(button);tr.append(name,price,evidence,action);body.append(tr);
    }
    table.append(body);this.$('fee-list').replaceChildren(table);
    this.$('fee-status').textContent=rows.length?`顯示 ${rows.length} / ${this.catalogue.metadata.fee_count} 項；已選 ${this.items.length} 項。`:'沒有符合條件的費用，請調整搜尋或篩選。';
  }
  add(r) {
    if(this.items.some(i=>i.reference.product===r.product&&i.reference.vendor===r.vendor))return;
    const target=this.$('budget-currency').value;
    this.items.push({reference:r,quantity:1,fx_rate:r.currency===target||r.price_status==='free'?1:null,target_currency:target,eligibility_confirmed:false,billing_assumption:null});
    this.renderSelections();this.renderCatalogue();this.onChange('已加入參考費用，請核對數量、換算率及適用條件。');
  }
  clear() {this.items=[];this.renderSelections();this.renderCatalogue();}
  currencyChanged() {
    const currency=this.$('budget-currency').value;
    for(const i of this.items){i.target_currency=currency;i.fx_rate=i.reference.currency===currency||i.reference.price_status==='free'?1:null;i.eligibility_confirmed=false;}
    this.renderSelections();
  }
  renderSelections() {
    const container=this.$('fee-selections');container.replaceChildren();
    if(!this.items.length){container.append(this.node('p','未選用參考費用；可直接輸入自己的預算。','fine'));return;}
    for(const item of this.items){
      const r=item.reference,row=this.node('fieldset',undefined,'fee-selection');row.dataset.feeId=r.fee_id;
      row.append(this.node('legend',`${r.product} · ${r.plan}`),this.node('p',`${this.price(r)}；${this.terms(r)}`,'fine'));
      if(r.eligibility)row.append(this.node('p',`適用資格：${r.eligibility}`,'fine'));
      row.append(this.details(r));
      const fields=this.node('div',undefined,'budget-grid');
      const qtyLabel=this.node('label',`數量（${r.charging_unit}）`),qty=this.node('input');qty.type='number';qty.min=1;qty.max=1000;qty.step=1;qty.required=true;qty.value=item.quantity;qty.dataset.feeField='quantity';qty.addEventListener('input',()=>item.quantity=qty.valueAsNumber);qtyLabel.append(qty);fields.append(qtyLabel);
      const fixed=r.price_status==='free'||r.currency===item.target_currency;
      const fxLabel=this.node('label',r.price_status==='free'?'免費項目（無須換算）':`1 ${r.currency} = 多少 ${item.target_currency}？`),fx=this.node('input');fx.type='number';fx.min=0.000001;fx.max=1000000;fx.step='any';fx.required=true;fx.value=item.fx_rate??'';fx.readOnly=fixed;fx.dataset.feeField='fx_rate';fx.addEventListener('input',()=>item.fx_rate=fx.valueAsNumber);fxLabel.append(fx,this.node('small',fixed?'換算率固定為 1。':'自行填寫預算換算率；系統不會自動取得市場匯率。'));fields.append(fxLabel);
      if(r.calculation_mode==='monthly_assumption_required'){
        const l=this.node('label','付款／合約期預算假設'),select=this.node('select');select.required=true;select.dataset.feeField='billing_assumption';
        for(const [value,title] of [['','請選擇；官方頁未列明合約期'],['monthly_flexible_user_assumption','我假設逐月付款，可逐月停止']]){const o=this.node('option',title);o.value=value;select.append(o);}
        select.value=item.billing_assumption??'';select.addEventListener('change',()=>{item.billing_assumption=select.value||null;this.onChange();});l.append(select);fields.append(l);
      }
      row.append(fields);
      const confirm=this.node('label',undefined,'fee-confirm'),check=this.node('input');check.type='checkbox';check.required=true;check.checked=item.eligibility_confirmed;check.dataset.feeField='eligibility_confirmed';check.addEventListener('input',()=>item.eligibility_confirmed=check.checked);
      confirm.append(check,this.node('span','我已核對適用資格、收費條件及數量，並確認沒有在其他開支重複計入。'));
      const remove=this.node('button','移除此項','outline');remove.type='button';remove.dataset.removeFee=r.fee_id;remove.addEventListener('click',()=>{this.items=this.items.filter(i=>i!==item);this.renderSelections();this.renderCatalogue();this.onChange();});
      row.append(confirm,remove);container.append(row);
    }
  }
  selection() {
    if(!this.items.length)return {};
    return {fee_selection:{revision:this.catalogue.metadata.revision,items:this.items.map(({reference,...i})=>({fee_id:reference.fee_id,...i}))}};
  }
};
