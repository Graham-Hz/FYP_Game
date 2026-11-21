/* Offline, accessible charts: compact screen plots and source-complete SVG exports. */
(() => {
  'use strict';
  const NS='http://www.w3.org/2000/svg',FONT='Segoe UI, Microsoft JhengHei, Arial, sans-serif';
  const COLORS=['#14745b','#426cba','#bd7623','#8851a0','#b44e59'];
  const observers=new WeakMap(),exports=new WeakMap(),measure=document.createElement('canvas').getContext('2d');
  // Scrolling can fire pointerover without a person moving the mouse. Only a
  // changed pointer position should take precedence over a focused chart mark.
  const movedPointers=new WeakSet();let pointerPosition=null;
  document.addEventListener('pointermove',event=>{if(!pointerPosition||event.clientX!==pointerPosition.x||event.clientY!==pointerPosition.y)movedPointers.add(event);pointerPosition={x:event.clientX,y:event.clientY};},true);
  let serial=0;
  // Keep source labels untouched in metadata; translate notation only for readers.
  const readable=value=>String(value??'').replace(/\(n\s*=\s*([\d,]+)\)/g,(_,n)=>`\n樣本 ${Number(n.replace(/,/g,'')).toLocaleString('en-US')} 款`).replace(/\bn\s*=\s*([\d,]+)/g,(_,n)=>`樣本 ${Number(n.replace(/,/g,'')).toLocaleString('en-US')} 款`).replace(/\bn\s*([≥≤<>])/g,'樣本數 $1');
  const node=(tag,value,cls)=>{const n=document.createElement(tag);if(value!==undefined)n.textContent=readable(value);if(cls)n.className=cls;return n;};
  const s=(tag,attrs={},value)=>{const n=document.createElementNS(NS,tag);Object.entries(attrs).forEach(([k,v])=>n.setAttribute(k,String(v)));if(value!==undefined)n.textContent=value;return n;};
  const text=(parent,x,y,value,attrs={})=>{const n=s('text',{x,y,fill:'#18382e','font-size':14,'pointer-events':'none',...attrs},readable(value));parent.append(n);return n;};
  const number=v=>Number.isFinite(v)?v.toLocaleString('en-US',{maximumFractionDigits:v!==0&&Math.abs(v)<.01?6:2}):'未提供';
  const short=v=>Math.abs(v)>=1e9?`${number(v/1e9)}B`:Math.abs(v)>=1e6?`${number(v/1e6)}M`:Math.abs(v)>=1e3?`${number(v/1e3)}k`:number(v);
  const axisLabel=(label,unit)=>unit&&!(label||'').includes(unit)?`${label||'數值'} (${unit})`:label||unit||'數值';
  const finite=values=>values.filter(Number.isFinite);
  const contentWidth=el=>{const css=getComputedStyle(el);return Math.max(0,el.clientWidth-(parseFloat(css.paddingLeft)||0)-(parseFloat(css.paddingRight)||0));};
  function width(value,size=14){measure.font=`${size}px ${FONT}`;return measure.measureText(String(value)).width;}
  function wrap(value,limit,size=14){const output=[];for(const paragraph of readable(value||'').split('\n')){let line='';for(const token of paragraph.match(/\S+\s*|\s+/g)||['']){if(width(line+token,size)<=limit){line+=token;continue;}if(line.trim()){output.push(line.trim());line='';}if(width(token,size)<=limit){line=token;continue;}for(const char of token){if(line&&width(line+char,size)>limit){output.push(line.trim());line='';}line+=char;}}output.push(line.trim());}return output;}
  function niceScale(values,{integer=false,zero=true,count=4}={}){
    const valid=finite(values);let low=valid.length?Math.min(...valid):0,high=valid.length?Math.max(...valid):1;
    if(zero){low=Math.min(0,low);high=Math.max(0,high);}if(low===high){if(high===0)high=1;else{low-=Math.abs(low)*.1;high+=Math.abs(high)*.1;}}
    const raw=(high-low)/Math.max(1,count),power=10**Math.floor(Math.log10(raw)),fraction=raw/power;
    let step=(fraction<=1?1:fraction<=2?2:fraction<=5?5:10)*power;if(integer)step=Math.max(1,Math.ceil(step));
    const min=Math.floor(low/step)*step,max=Math.ceil(high/step)*step,ticks=[];
    for(let value=min,n=0;value<=max+step/100&&n<20;value+=step,n++)ticks.push(Number(value.toPrecision(12)));
    return {min,max:max===min?min+step:max,ticks,position:value=>(value-min)/((max-min)||step)};
  }
  function axis(values,scale='linear',options={}){
    if(scale!=='log1p')return niceScale(values,options);
    const valid=finite(values).filter(value=>value>=0),max=Math.max(1,...valid),top=Math.log1p(max),end=Math.ceil(Math.log10(max)),start=Math.min(0,end-5),ticks=[0];
    for(let exponent=start;exponent<=end;exponent++){for(const multiplier of [1,2,5]){const value=multiplier*10**exponent;if(value<=max&&(!options.integer||value>=1))ticks.push(value);}}
    if(ticks[ticks.length-1]!==max)ticks.push(max);
    return {min:0,max,ticks,position:value=>value>=0?Math.log1p(value)/top:NaN};
  }
  function mark(element,label,callback,item){
    const description=readable(label)+(typeof callback==='function'?'\n點選或按 Enter 查看對應資料。':'');
    element.setAttribute('tabindex','0');element.setAttribute('aria-label',description);element.dataset.chartLabel=description;
    if(typeof callback==='function'){element.setAttribute('role','button');element.classList.add('game-chart-selectable');element.addEventListener('click',()=>callback(item));element.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();callback(item);}});}return element;
  }
  function tooltips(figure,svg,id){
    const tip=node('div',undefined,'game-chart-tooltip');tip.id=id;tip.setAttribute('role','tooltip');tip.hidden=true;figure.append(tip);let active=null,focused=null,pointerMode=false,escaped=false;
    function hide(){tip.hidden=true;if(active)active.removeAttribute('aria-describedby');active=null;}
    function place(event){
      if(!active)return;const box=active.getBoundingClientRect(),pointer=event?.type?.startsWith('pointer');
      let x=pointer?event.clientX:box.left+box.width/2,y=pointer?event.clientY:box.bottom;
      const rect=tip.getBoundingClientRect();x=Math.max(8,Math.min(x+12,innerWidth-rect.width-8));
      y=y+14+rect.height>innerHeight?Math.max(8,y-rect.height-12):y+14;
      tip.style.left=`${x}px`;tip.style.top=`${y}px`;
    }
    function targetOf(event){const target=event.target.closest?.('[data-chart-label]');return target&&svg.contains(target)?target:null;}
    function show(target,event){if(!target)return;hide();active=target;tip.textContent=target.dataset.chartLabel;tip.hidden=false;target.setAttribute('aria-describedby',id);place(event);}
    function focusTooltip(){if(focused&&!escaped)show(focused);else hide();}
    svg.addEventListener('focusin',event=>{focused=targetOf(event);pointerMode=false;escaped=false;focusTooltip();});
    svg.addEventListener('focusout',()=>{focused=null;escaped=false;hide();});
    svg.addEventListener('pointerover',event=>{if(focused&&!pointerMode)return;escaped=false;show(targetOf(event),event);});
    svg.addEventListener('pointermove',event=>{if(focused&&!pointerMode&&!movedPointers.has(event))return;if(movedPointers.has(event)){pointerMode=true;escaped=false;}if(!escaped)show(targetOf(event),event);});
    svg.addEventListener('pointerdown',event=>{pointerMode=true;escaped=false;show(targetOf(event),event);});
    svg.addEventListener('pointerleave',()=>{pointerMode=false;focusTooltip();});
    svg.addEventListener('pointerout',event=>{if(focused&&!pointerMode)return;if(active&&!active.contains(event.relatedTarget))hide();});
    svg.addEventListener('keydown',event=>{if(event.key==='Escape'){escaped=true;hide();}});
    figure.querySelector('.game-chart-viewport')?.addEventListener('scroll',()=>{if(focused&&!pointerMode)focusTooltip();else hide();},{passive:true});
  }
  function legend(svg,series,W,force=false){if(series.length<2&&!force)return 8;let x=16,y=18;for(const item of series){const label=item.label||item.key||'數值',needed=Math.min(W-32,width(label)+28);if(x+needed>W-16&&x>16){x=16;y+=23;}svg.append(s('rect',{x,y:y-11,width:12,height:12,rx:2,fill:item.color}));text(svg,x+19,y,label);x+=needed+20;}return y+14;}
  function spacedTicks(scale,length,gap){const values=[];for(const value of scale.ticks){if(!values.length||(scale.position(value)-scale.position(values[values.length-1]))*length>=gap)values.push(value);}const last=scale.ticks[scale.ticks.length-1];if(values[values.length-1]!==last){if(values.length>1&&(scale.position(last)-scale.position(values[values.length-1]))*length<gap)values.pop();if(!values.length||(scale.position(last)-scale.position(values[values.length-1]))*length>=gap)values.push(last);}return values;}
  function grid(svg,scale,{left,top,plotW,plotH},horizontal=false){for(const value of spacedTicks(scale,horizontal?plotW:plotH,horizontal?65:30)){if(horizontal){const x=left+scale.position(value)*plotW;svg.append(s('line',{x1:x,x2:x,y1:top,y2:top+plotH,stroke:'#e1e8e4'}));text(svg,x,top+plotH+22,short(value),{'text-anchor':'middle'});}else{const y=top+plotH-scale.position(value)*plotH;svg.append(s('line',{x1:left,x2:left+plotW,y1:y,y2:y,stroke:'#e1e8e4'}));text(svg,left-10,y+5,short(value),{'text-anchor':'end'});}}}
  function table(parent,headers,rows){const detail=node('details',undefined,'game-chart-data');detail.append(node('summary','查看圖表數值'));const scroll=node('div',undefined,'table-scroll'),t=node('table'),head=node('thead'),tr=node('tr');headers.forEach(label=>{const th=node('th',label);th.scope='col';tr.append(th);});head.append(tr);t.append(head);const body=node('tbody');rows.forEach(values=>{const row=node('tr');values.forEach((value,i)=>{const cell=node(i===0?'th':'td',value);if(i===0)cell.scope='row';row.append(cell);});body.append(row);});t.append(body);scroll.append(t);detail.append(scroll);parent.append(detail);}
  function provenance(parent,config){const values=[config.source,config.method].filter(Boolean);if(!values.length)return;const detail=node('details',undefined,'game-chart-provenance');detail.append(node('summary','來源與分析方法'));values.forEach(value=>detail.append(node('p',value)));parent.append(detail);}
  function exportImage(svg){
    const stored=exports.get(svg);if(!stored)return svg.cloneNode(true);
    const {config,W,H}=stored,titleLines=wrap(config.title||'資料圖表',W-40,20),descriptionLines=wrap(config.description||'',W-40),scaleNote=scaleDescription(config),sourceLines=wrap([config.availability?.status==='limited'?`資料局限：${config.availability.reason} ${config.availability.action}`:'',scatterSummary(config),scaleNote,config.source,config.method].filter(Boolean).join('\n'),W-40);
    const header=24+titleLines.length*26+(config.description?descriptionLines.length*20+10:0),footer=sourceLines.length*20+28;
    const output=s('svg',{xmlns:NS,width:W,height:header+H+footer,viewBox:`0 0 ${W} ${header+H+footer}`,'font-family':FONT,role:'img'});
    output.append(s('title',{},config.title||'資料圖表'),s('desc',{},config.description||''),s('metadata',{},JSON.stringify(config)),s('rect',{width:W,height:header+H+footer,fill:'#fff'}));
    titleLines.forEach((line,i)=>text(output,20,27+i*26,line,{'font-size':20,'font-weight':700}));if(config.description)descriptionLines.forEach((line,i)=>text(output,20,27+titleLines.length*26+i*20,line,{fill:'#4d665c'}));
    const plot=s('g',{transform:`translate(0 ${header})`});[...svg.children].filter(child=>!['title','desc','metadata'].includes(child.localName)).forEach(child=>plot.append(child.cloneNode(true)));
    plot.querySelectorAll('[data-chart-label]').forEach(mark=>{mark.removeAttribute('aria-describedby');mark.append(s('title',{},mark.dataset.chartLabel));});output.append(plot);
    sourceLines.forEach((line,i)=>text(output,20,header+H+19+i*20,line,{fill:'#4d665c'}));return output;
  }
  function download(svg,filename='gamescope-chart.svg'){if(!(svg instanceof SVGElement))return;const raw='<?xml version="1.0" encoding="UTF-8"?>\n'+new XMLSerializer().serializeToString(exportImage(svg)),url=URL.createObjectURL(new Blob([raw],{type:'image/svg+xml;charset=utf-8'}));const a=node('a');a.href=url;a.download=filename.endsWith('.svg')?filename:`${filename}.svg`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
  function barPlot(svg,config,rows,series,W){
    const values=finite(rows.flatMap(row=>row.values||[])),integer=config.integerTicks??/[款份次人]/.test(config.unit||''),top=legend(svg,series,W,config.showLegend===true)+8;
    const left=Math.min(190,Math.max(120,Math.round(W*.29))),right=Math.min(160,Math.max(72,...values.map(value=>width(number(value))+18))),plotW=W-left-right;
    const minRowHeight=Number.isFinite(config.rowHeight)?Math.min(96,Math.max(34,config.rowHeight)):34;
    const labels=rows.map(row=>wrap(row.label,left-24).slice(0,3)),heights=labels.map(a=>Math.max(minRowHeight,series.length*18+10,a.length*16+10)),plotH=heights.reduce((a,b)=>a+b,0),scale=niceScale(values,{integer,count:Math.max(1,Math.min(4,Math.floor(plotW/80)))});grid(svg,scale,{left,top,plotW,plotH},true);
    let start=top;rows.forEach((row,i)=>{const center=start+heights[i]/2;labels[i].forEach((line,j)=>text(svg,left-14,center+(j-(labels[i].length-1)/2)*16+5,line,{'text-anchor':'end'}));series.forEach((item,j)=>{const value=row.values?.[j],y=center+(j-(series.length-1)/2)*18;if(!Number.isFinite(value)){text(svg,left+5,y+5,'未提供',{fill:'#6b7771'});return;}const x0=left+scale.position(Math.min(value,0))*plotW,x1=left+scale.position(Math.max(value,0))*plotW;svg.append(mark(s('rect',{x:x0,y:y-6,width:Math.max(0,x1-x0),height:12,rx:2,fill:item.color}),`${row.label} · ${item.label}: ${number(value)} ${config.unit||''}`,(row.filter||row.cohort)?config.onSelectRow:undefined,row));text(svg,value<0?x0-5:x1+5,y+5,number(value),{'text-anchor':value<0?'end':'start'});});start+=heights[i];});text(svg,left,top+plotH+45,config.yLabel||config.unit||'數值',{fill:'#4d665c'});return top+plotH+58;
  }
  function stackedPlot(svg,config,rows,series,W){
    const left=Math.min(220,Math.max(175,Math.round(W*.26))),right=28,plotW=W-left-right,top=legend(svg,series,W,true)+18,rowH=88,plotH=rows.length*rowH;
    const scale={ticks:[0,25,50,75,100],position:value=>value/100};grid(svg,scale,{left,top,plotW,plotH},true);
    rows.forEach((row,i)=>{
      const cy=top+(i+.5)*rowH,label=wrap(row.label,left-22).slice(0,3),lines=[...label,`n = ${number(row.n)}`];
      lines.forEach((line,j)=>text(svg,left-12,cy+(j-(lines.length-1)/2)*17+5,line,{'text-anchor':'end'}));
      if(!row.n||!row.values?.some(Number.isFinite)){text(svg,left+8,cy+5,'沒有樣本；比例未計算',{fill:'#526a5e'});return;}
      svg.append(s('rect',{x:left,y:cy-17,width:plotW,height:34,fill:'#edf1ef',rx:3}));let offset=0;
      series.forEach((item,index)=>{
        const value=row.values[index];if(!Number.isFinite(value)||value<0)return;
        const x=left+offset*plotW/100,segmentW=Math.max(0,Math.min(value,100-offset))*plotW/100;offset+=value;
        if(segmentW<=0)return;
        const label=`${row.label}\n${item.label}：${number(value)}%\n${number(row.counts?.[index])} / ${number(row.n)} 款（此組全部樣本）`;
        const segment=mark(s('rect',{x,y:cy-17,width:segmentW,height:34,fill:item.color,stroke:'#fff','stroke-width':1}),label,config.onSelectSegment,{row,series:item,index});
        segment.dataset.cohort=row.cohort||'';segment.dataset.tier=item.key||'';svg.append(segment);
        const caption=`${number(value)}%`;
        if(segmentW>width(caption)+12){const color=item.color||'#14745b',rgb=/^#[a-f\d]{6}$/i.test(color)?[1,3,5].map(n=>parseInt(color.slice(n,n+2),16)):[20,116,91];
          const linear=rgb.map(v=>v/255<=.04045?v/3294.6:((v/255+.055)/1.055)**2.4),luminance=.2126*linear[0]+.7152*linear[1]+.0722*linear[2];
          text(svg,x+segmentW/2,cy+5,caption,{'text-anchor':'middle',fill:luminance<.179?'#fff':'#000','pointer-events':'none'});
        }
      });
    });text(svg,left,top+plotH+48,'組內比例 (%) · 每組使用自己的分母',{fill:'#4d665c'});return top+plotH+63;
  }
  function linePlot(svg,config,rows,series,W){
    const values=finite(rows.flatMap(row=>row.values||[])),top=legend(svg,series,W)+24,left=76,right=36,plotW=W-left-right,plotH=260,scale=niceScale(values,{integer:config.integerTicks??/[款份次人]/.test(config.unit||''),count:4});grid(svg,scale,{left,top,plotW,plotH});text(svg,16,top-9,config.yLabel||config.unit||'數值',{fill:'#4d665c'});
    const X=i=>rows.length===1?left+plotW/2:left+i*plotW/(rows.length-1),Y=value=>top+plotH-scale.position(value)*plotH,interval=Math.max(1,Math.ceil(rows.length/Math.max(2,Math.floor(plotW/66))));rows.forEach((row,i)=>{const last=rows.length-1;if((i%interval===0&&(i===0||X(last)-X(i)>=62))||i===last)text(svg,X(i),top+plotH+24,row.label,{'text-anchor':'middle'});});
    series.forEach((item,j)=>{let segment=[];const flush=()=>{if(segment.length>1)svg.append(s('polyline',{points:segment.join(' '),fill:'none',stroke:item.color,'stroke-width':2.5}));segment=[];};rows.forEach((row,i)=>{const value=row.values?.[j];if(!Number.isFinite(value)){flush();return;}segment.push(`${X(i)},${Y(value)}`);});flush();rows.forEach((row,i)=>{const value=row.values?.[j];if(!Number.isFinite(value))return;svg.append(mark(s('circle',{cx:X(i),cy:Y(value),r:4,fill:item.color,stroke:'#fff','stroke-width':1}),`${row.label} · ${item.label}: ${number(value)} ${config.unit||''}`));if(rows.length<=6)text(svg,X(i),Y(value)+(j%2===0?-9:19),number(value),{'text-anchor':i===0?'start':i===rows.length-1?'end':'middle',fill:item.color});});});return top+plotH+48;
  }
  function histogramPlot(svg,config,rows,series,W){
    const left=72,right=28,top=28,plotW=W-left-right,plotH=260,valid=rows.filter(row=>Number.isFinite(row.lower)&&Number.isFinite(row.upper)&&row.upper>row.lower&&Number.isFinite(row.values?.[0]));
    const rawBounds=valid.flatMap(row=>[row.lower,row.upper]),x=axis(rawBounds,config.xScale,{count:5,integer:/[款份次人]/.test(config.xUnit||'')}),y=niceScale(valid.map(row=>row.values[0]),{integer:true,count:4});grid(svg,y,{left,top,plotW,plotH});
    for(const value of spacedTicks(x,plotW,65))text(svg,left+x.position(value)*plotW,top+plotH+24,short(value),{'text-anchor':'middle'});
    valid.forEach(row=>{const a=left+x.position(row.lower)*plotW,b=left+x.position(row.upper)*plotW,height=y.position(row.values[0])*plotH;svg.append(mark(s('rect',{x:a+.5,y:top+plotH-height,width:Math.max(1,b-a-1),height,fill:series[0].color}),`${row.label} · ${number(row.values[0])} 款；範圍 ${number(row.lower)} 至 ${number(row.upper)}`));});text(svg,14,18,config.yLabel||'遊戲款數',{fill:'#4d665c'});text(svg,left+plotW/2,top+plotH+47,[config.xLabel,config.xUnit||config.unit].filter(Boolean).join(' · '),{'text-anchor':'middle',fill:'#4d665c'});return top+plotH+63;
  }
  function boxPlot(svg,config,rows,W){
    const left=Math.min(210,Math.max(165,Math.round(W*.26))),right=30,top=20,plotW=W-left-right,rowH=56,plotH=rows.length*rowH;
    const values=finite(rows.flatMap(row=>[...(row.values||[]),...(row.outliers||[])])),x=axis(values,config.xScale,{count:5,integer:/[款份次人]/.test(config.unit||'')});grid(svg,x,{left,top,plotW,plotH},true);
    rows.forEach((row,i)=>{const cy=top+(i+.5)*rowH;[...wrap(row.label,left-24).slice(0,2),`n = ${number(row.n)}`].forEach((line,j,a)=>text(svg,left-14,cy+(j-(a.length-1)/2)*16+5,line,{'text-anchor':'end'}));if(!row.values||row.values.length<5||row.values.some(value=>!Number.isFinite(value))){text(svg,left+5,cy+5,'未提供');return;}
      const [low,q1,median,q3,high]=row.values.map(value=>left+x.position(value)*plotW),group=s('g');group.append(s('line',{x1:low,x2:high,y1:cy,y2:cy,stroke:'#336f60','stroke-width':2}),s('line',{x1:low,x2:low,y1:cy-8,y2:cy+8,stroke:'#336f60','stroke-width':2}),s('line',{x1:high,x2:high,y1:cy-8,y2:cy+8,stroke:'#336f60','stroke-width':2}),s('rect',{x:q1,y:cy-12,width:Math.max(1,q3-q1),height:24,fill:'#b8dacf',stroke:'#14745b','stroke-width':1.5}),s('line',{x1:median,x2:median,y1:cy-12,y2:cy+12,stroke:'#12493b','stroke-width':2.5}));
      svg.append(mark(group,`${row.label} · n=${number(row.n)}；下鬚 ${number(row.values[0])}；Q1 ${number(row.values[1])}；中位數 ${number(row.values[2])}；Q3 ${number(row.values[3])}；上鬚 ${number(row.values[4])}；離群值 ${number(row.outlier_count)} 個`));
      (row.outliers||[]).filter(Number.isFinite).forEach(value=>svg.append(mark(s('circle',{cx:left+x.position(value)*plotW,cy,r:3,fill:'#fff',stroke:'#b46c22','stroke-width':1.5}),`${row.label} · 離群值 ${number(value)} ${config.unit||''}`)));
    });const caption=wrap(axisLabel(config.xLabel,config.xUnit||config.unit),plotW);caption.forEach((line,i)=>text(svg,left,top+plotH+45+i*18,line,{fill:'#4d665c'}));return top+plotH+60+(caption.length-1)*18;
  }
  function scatterPlot(svg,config,points,W){
    const left=80,right=28,top=32,plotW=W-left-right,plotH=280,x=axis(points.map(point=>point.x),config.xScale,{count:5,integer:/[款份次人]/.test(config.xUnit||'')}),y=axis(points.map(point=>point.y),config.yScale,{count:4,integer:/[款份次人]/.test(config.yUnit||'')});grid(svg,y,{left,top,plotW,plotH});
    for(const value of spacedTicks(x,plotW,65))text(svg,left+x.position(value)*plotW,top+plotH+24,short(value),{'text-anchor':'middle'});
    points.forEach(point=>svg.append(mark(s('circle',{cx:left+x.position(point.x)*plotW,cy:top+plotH-y.position(point.y)*plotH,r:3.5,fill:'#14745b','fill-opacity':.55,stroke:'#fff','stroke-width':.4}),`${point.label||point.id} · ${config.xLabel||'X'} ${number(point.x)} ${config.xUnit||''}；${config.yLabel||'Y'} ${number(point.y)} ${config.yUnit||''}`,config.onPointSelect,point)));
    text(svg,14,18,[config.yLabel,config.yUnit].filter(Boolean).join(' · '),{fill:'#4d665c'});text(svg,left+plotW/2,top+plotH+48,[config.xLabel,config.xUnit].filter(Boolean).join(' · '),{'text-anchor':'middle',fill:'#4d665c'});return top+plotH+64;
  }
  function heatmapPlot(svg,config,rows,series,W){
    const left=Math.min(215,Math.max(170,Math.round(W*.26))),right=20,top=54,plotW=W-left-right,cellW=plotW/Math.max(1,series.length),rowH=52,plotH=rows.length*rowH;
    const labels=series.map(item=>wrap(item.label||item.key,cellW-10));labels.forEach((label,j)=>label.slice(0,2).forEach((line,i)=>text(svg,left+(j+.5)*cellW,18+i*17,line,{'text-anchor':'middle'})));
    rows.forEach((row,i)=>{[...wrap(row.label,left-24).slice(0,2),`n = ${number(row.n)}`].forEach((line,j,a)=>text(svg,left-12,top+(i+.5)*rowH+(j-(a.length-1)/2)*15+5,line,{'text-anchor':'end'}));series.forEach((item,j)=>{const value=row.values?.[j],valid=Number.isFinite(value),ratio=valid?Math.max(0,Math.min(1,value/100)):0,rgb=[Math.round(240-220*ratio),Math.round(247-135*ratio),Math.round(243-157*ratio)],color=valid?`rgb(${rgb.join(',')})`:'#ecefed';
        const linear=rgb.map(channel=>channel/255<=.04045?channel/3294.6:((channel/255+.055)/1.055)**2.4),luminance=.2126*linear[0]+.7152*linear[1]+.0722*linear[2];
        svg.append(mark(s('rect',{x:left+j*cellW+1,y:top+i*rowH+1,width:cellW-2,height:rowH-2,rx:2,fill:color}),`${row.label} · ${item.label}: ${valid?`${number(value)}%`:'未提供'}；${number(row.counts?.[j])} / ${number(row.n)} 款`));text(svg,left+(j+.5)*cellW,top+(i+.5)*rowH+5,valid?`${number(value)}%`:'—',{'text-anchor':'middle',fill:valid&&luminance<.179?'#fff':'#000'});
      });});text(svg,left,top+plotH+26,'淺色 0% · 深色 100% · 每列各自計算比例',{fill:'#4d665c'});return top+plotH+42;
  }
  function scaleDescription(config){if(!['boxplot','scatter','histogram'].includes(config.type))return '';const label=value=>value==='log1p'?'log1p 對數壓縮':'原始線性';return `圖中 X 軸：${label(config.xScale)}${config.type==='scatter'?`；Y 軸：${label(config.yScale)}`:''}。表格及提示保留原始數值。`;}
  function scatterSummary(config){
    if(config.type!=='scatter'||!config.summary)return '';
    const info=config.summary,rho=Number.isFinite(info.spearman_rho)?info.spearman_rho.toFixed(4):'無法計算';
    return `兩個數值均有資料：${number(info.paired_rows)} 款 · 圖中顯示 ${number(info.displayed_rows)} 款 · 秩相關（Spearman ρ）= ${rho}（使用全部有效配對）`;
  }
  function chartTable(figure,config,rows,series,points){
    if(config.type==='scatter'){table(figure,['遊戲／記錄','ID',`${config.xLabel||'X'} (${config.xUnit||''})`,`${config.yLabel||'Y'} (${config.yUnit||''})`],points.map(point=>[point.label||point.id,point.id||'',number(point.x),number(point.y)]));return;}
    if(config.type==='histogram'){table(figure,['區間','下界（原始值）','上界（原始值）','遊戲款數'],rows.map(row=>[row.label,number(row.lower),number(row.upper),number(row.values?.[0])]));return;}
    if(config.type==='boxplot'){table(figure,['分類','樣本數（款）','下鬚','第 25 百分位（Q1）','中位數','第 75 百分位（Q3）','上鬚','離群值總數','圖中離群值'],rows.map(row=>[row.label,number(row.n),...(row.values||[null,null,null,null,null]).map(number),number(row.outlier_count),(row.outliers||[]).map(number).join(', ')||'—']));return;}
    if(config.type==='heatmap'||config.type==='stacked_bar'){table(figure,['分類','樣本數（款）',...series.map(item=>item.label)],rows.map(row=>[row.label,number(row.n),...series.map((_,j)=>Number.isFinite(row.values?.[j])?`${number(row.values[j])}% (${number(row.counts?.[j])} 款)`:'未提供')]));return;}
    table(figure,['分類／時期',...series.map(item=>`${item.label}${config.unit?` (${config.unit})`:''}`)],rows.map(row=>[row.label,...series.map((_,j)=>number(row.values?.[j]))]));
  }
  function dispose(container){const target=typeof container==='string'?document.getElementById(container):container;if(target){observers.get(target)?.disconnect();observers.delete(target);}}
  function readiness(figure,config){
    const info=config.availability;if(!info||info.status==='available')return;
    const compact=config.compactReadiness&&info.status==='limited';
    const box=node(compact?'details':'div',undefined,'game-chart-readiness');box.dataset.status=info.status;
    if(compact){
      box.classList.add('game-chart-readiness-compact');
      const coverage=info.count_basis==='sum_of_two_cohorts_including_any_overlap'?'兩組資料需注意':Number.isFinite(info.valid_rows)?`可用 ${number(info.valid_rows)}${Number.isFinite(info.total_rows)?` / ${number(info.total_rows)}`:''} 款`:'';
      box.append(node('summary',['資料有局限',coverage,'查看說明'].filter(Boolean).join(' · ')));
    }else {box.setAttribute('role','status');box.append(node('strong',info.status==='unavailable'?'目前資料無法產生這張圖':'這張圖的資料有局限'));}
    if(info.reason)box.append(node('p',info.reason));
    if(info.count_basis==='sum_of_two_cohorts_including_any_overlap')box.append(node('p',`有數值資料：所選組 ${number(info.selected_valid_rows)} 款；對照組 ${number(info.baseline_valid_rows)} 款。兩組可有重疊，不能直接相加當作獨立遊戲總數。`,'game-chart-readiness-count'));
    else if(Number.isFinite(info.valid_rows)){const total=Number.isFinite(info.total_rows)?`／篩選樣本 ${number(info.total_rows)} 款`:'';box.append(node('p',`此圖可用資料：${number(info.valid_rows)} 款${total}`,'game-chart-readiness-count'));}
    if(info.action)box.append(node('p',`你可以：${info.action}`));
    if(info.requirements?.length){const detail=node('details');detail.append(node('summary','需要哪些資料？'));const list=node('ul');info.requirements.forEach(value=>list.append(node('li',value)));detail.append(list);box.append(detail);}
    figure.append(box);
  }
  function readingHelp(figure,config){
    const messages=[];
    if(config.type==='boxplot')messages.push('箱內是中央 50% 的遊戲（Q1–Q3），中間線是中位數；鬚線以 1.5 倍四分位距為界，外面的點是離群值，不一定是錯誤。');
    else if(config.type==='histogram')messages.push('每條柱表示數值落在該範圍的遊戲款數，可用來看資料集中在哪裡。');
    else if(config.type==='scatter')messages.push('每點代表一款遊戲。秩相關（ρ）比較兩個數值的排序關係：接近 +1 同向、−1 反向，接近 0 表示較弱的單調關係；不是因果或收益預測。');
    else if(config.type==='heatmap'||config.type==='stacked_bar')messages.push('樣本數是這組包含的遊戲款數；每組比例以自己的樣本數計算，並非整體市場佔有率。');
    else if(/中位數/.test(config.title||''))messages.push('中位數是數值排序後的中間位置，較少受極端作品影響；不代表下一款遊戲的預期表現。');
    if(!messages.length)return;figure.append(node('p',messages.join(' '),'game-chart-reading-help'));
  }
  function render(container,config){
    const target=typeof container==='string'?document.getElementById(container):container;if(!target)throw new Error('Chart container was not found.');dispose(target);
    const rows=Array.isArray(config.rows)?config.rows:[],series=(config.series?.length?config.series:[{label:'數值'}]).map((item,i)=>({...item,color:item.color||COLORS[i%COLORS.length]})),points=(config.points||[]).filter(point=>Number.isFinite(point.x)&&Number.isFinite(point.y));
    const type=config.type||'bar',title=config.title||'資料圖表',figure=node('figure',undefined,'game-chart');figure.append(node('figcaption',title,'game-chart-caption'));if(config.description)figure.append(node('p',config.description,'game-chart-note'));
    if(!['bar','line','histogram','boxplot','scatter','heatmap','stacked_bar'].includes(type))throw new Error('Unsupported chart type.');
    readiness(figure,config);
    if(config.availability?.status==='unavailable'){provenance(figure,config);target.replaceChildren(figure);return null;}
    const values=finite(rows.flatMap(row=>row.values||[]));if(type==='scatter'?!points.length:!rows.length||!values.length){figure.append(node('p','沒有可繪製的資料；缺漏值不會當作零。','game-chart-empty'));provenance(figure,config);target.replaceChildren(figure);return null;}
    readingHelp(figure,config);
    if(type==='scatter'||type==='boxplot'){const label=node('label','顯示尺度','game-chart-scale'),select=node('select');select.setAttribute('aria-label','顯示尺度');for(const [value,labelText] of [['log1p','壓縮大數值（log1p）'],['linear','原始數值（線性）']]){const option=node('option',labelText);option.value=value;select.append(option);}select.value=config.xScale==='log1p'?'log1p':'linear';select.addEventListener('change',()=>render(target,{...config,xScale:select.value,...(type==='scatter'?{yScale:select.value}:{})}));label.append(select);figure.append(label);}
    const scaleNote=scaleDescription(config);if(scaleNote)figure.append(node('p',scaleNote,'game-chart-scale-note'));
    const summary=scatterSummary(config);if(summary)figure.append(node('p',summary,'game-chart-statistics'));
    const measuredWidth=contentWidth(target),availableWidth=Math.max(0,measuredWidth-2),W=Math.floor(Math.max(type==='bar'?380:type==='boxplot'||type==='heatmap'?560:640,Math.min(1100,availableWidth||760))),uid=`game-chart-${++serial}`;
    const svg=s('svg',{xmlns:NS,width:W,role:'img','aria-labelledby':`${uid}-title ${uid}-desc`,'font-family':FONT});svg.style.minWidth=`${W}px`;svg.append(s('title',{id:`${uid}-title`},title),s('desc',{id:`${uid}-desc`},`${config.description||''} 展開下方表格可讀取完整數值。`));
    const H=type==='bar'?barPlot(svg,config,rows,series,W):type==='stacked_bar'?stackedPlot(svg,config,rows,series,W):type==='line'?linePlot(svg,config,rows,series,W):type==='histogram'?histogramPlot(svg,config,rows,series,W):type==='boxplot'?boxPlot(svg,config,rows,W):type==='scatter'?scatterPlot(svg,config,points,W):heatmapPlot(svg,config,rows,series,W);svg.setAttribute('height',H);svg.setAttribute('viewBox',`0 0 ${W} ${H}`);exports.set(svg,{config,W,H});
    const viewport=node('div',undefined,'game-chart-viewport');viewport.tabIndex=0;viewport.setAttribute('aria-label',`${title}；窄螢幕可左右捲動`);viewport.append(svg);if(W>availableWidth+1)figure.append(node('p','窄螢幕可左右捲動圖表；完整數值見下方表格。','game-chart-scroll-note'));figure.append(viewport);
    const actions=node('div',undefined,'game-chart-actions'),button=node('button','下載圖表 SVG','outline');button.type='button';button.addEventListener('click',()=>download(svg,config.filename||'gamescope-chart.svg'));actions.append(button);figure.append(actions);provenance(figure,config);chartTable(figure,config,rows,series,points);target.replaceChildren(figure);
    tooltips(figure,svg,`${uid}-tooltip`);
    if(window.ResizeObserver){const observer=new ResizeObserver(()=>{if(!target.isConnected){observer.disconnect();return;}const next=contentWidth(target);if(next>0&&Math.abs(next-measuredWidth)>2)render(target,config);});observer.observe(target);observers.set(target,observer);}return svg;
  }
  window.GameCharts={render,download,dispose};
})();
