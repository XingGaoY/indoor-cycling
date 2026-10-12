"""Interactive power/heart-rate timeline editor. No training execution or hardware control."""
HTML = """<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>可视化课程编排 · Indoor Cycling</title><style></style>
<style id="timeline-style">
.workbench{display:grid;grid-template-columns:72px minmax(0,1fr);gap:8px}
.shape-tools{display:flex;flex-direction:column;gap:8px;align-self:start}
.shape-tools strong{text-align:center;font-size:12px;color:#afc7db}
.shape-tool{min-width:64px;min-height:76px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px;margin:0;padding:6px;background:#263a53;border:1px solid #49617a;touch-action:none}
.shape-tool svg{width:45px;height:28px}.shape-tool span{font-size:11px}.shape-tool:focus-visible{outline:2px solid #83e1c3}
.zoom-tools{display:flex;gap:8px;align-items:center;padding:10px 0}.zoom-tools button{min-width:44px;margin:0}
@media(max-width:420px){.workbench{grid-template-columns:60px minmax(0,1fr);gap:5px}.shape-tool{min-width:56px}}
.chartframe{overflow-x:auto;overflow-y:hidden;border:1px solid #33445b;border-radius:14px;background:#101d30}
.timeline{display:block;touch-action:pan-x;min-height:355px}
.timeline .block{cursor:pointer;touch-action:none}
.timeline .handle{cursor:ew-resize;touch-action:none}.timeline .group-block{cursor:pointer;touch-action:none}
.timeline .axis{font:12px system-ui;fill:#bfd0df}
.timeline .zoneaxis{font:12px system-ui;fill:#bfd0df}
.segment-editor{background:#1e3048;border:1px solid #43617c;border-radius:15px;padding:14px;margin:15px 0}
.tiny{font-size:12px;color:#a8bbcf}
.twocol{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.charttab[aria-selected=true]{background:#167f73}
.preset{border-left:4px solid #83e1c3}
fieldset{border:1px solid #425872;border-radius:12px;padding:10px}
fieldset label{display:block;margin:8px 0;font-size:13px}
fieldset input{margin-top:4px}
</style>
<main class="wrap"><div class="eyebrow">INDOOR CYCLING</div><h1>训练计划</h1>
<p class="muted">按时间与 Z1–Z6 规划课程。功率／心率共享时间轴，保存后也不会立即执行训练或控制骑行台。</p>
<article><label>控制令牌（当前标签页会话内保存）<input id="token" type="password" autocomplete="off" placeholder="CYCLING_TOKEN"></label></article>
<section id="library">
<button id="new">＋ 新建课程</button>
<article><h2>预设课程</h2><p class="tiny">预设按相对区间编写；复制后可随意修改，不会自动启动。</p><div id="presets"></div></article>
<h2>我的课程</h2><div id="list"></div>
</section>
<section id="editor" hidden>
<article>
<h2 id="heading">编辑课程</h2>
<label>课程名称<input id="name" maxlength="80"></label>
<label>备注<textarea id="note" maxlength="500" rows="2"></textarea></label>
<p id="summary" class="muted"></p>
</article>
<article>
<h2>训练区间参考</h2>
<div class="twocol">
<label class="tiny">骑行 FTP（W）<input id="ftp" type="number" min="60" max="500" placeholder="未校准"></label>
<label class="tiny">最大心率（bpm）<input id="maxhr" type="number" min="100" max="230" placeholder="未校准"></label>
</div>
<button id="savezones">保存参考值</button>
<p class="tiny">FTP 与最大心率均需实际测定或审慎估计；未设置时只显示相对 Z 区间，不生成绝对功率／心率。Z6 功率上界开放。心率六区划分仅作初步显示。</p>
</article>
<article>
<div role="tablist" aria-label="课程图表"><button role="tab" id="powerTab" class="charttab" aria-selected="true">功率 Z1–Z6</button><button role="tab" id="hrTab" class="charttab" aria-selected="false">心率 Z1–Z6</button></div>
<p class="tiny" id="guide">从左侧选择形状，拖入时间轴插入，或点击追加。块内标时长，块上方显示当前目标。</p>
<div class="workbench">
<aside class="shape-tools" aria-label="形状工具栏"><strong>形状</strong>
<button class="shape-tool" type="button" data-shape="constant" aria-label="添加恒定方块"><svg viewBox="0 0 48 30" aria-hidden="true"><rect x="4" y="6" width="40" height="20" fill="#1cb7a5"/></svg><span>恒定</span></button>
<button class="shape-tool" type="button" data-shape="rise" aria-label="添加递增梯形"><svg viewBox="0 0 48 30" aria-hidden="true"><path d="M4 26V21L44 5V26Z" fill="#d0b751"/></svg><span>递增</span></button>
<button class="shape-tool" type="button" data-shape="fall" aria-label="添加递减梯形"><svg viewBox="0 0 48 30" aria-hidden="true"><path d="M4 5L44 21V26H4Z" fill="#ee9951"/></svg><span>递减</span></button>
<button class="shape-tool" type="button" data-shape="repeat" aria-label="添加间歇组"><svg viewBox="0 0 48 30" aria-hidden="true"><rect x="3" y="8" width="13" height="18" fill="#e16d71"/><rect x="18" y="17" width="10" height="9" fill="#778ca3"/><rect x="30" y="8" width="15" height="18" fill="#e16d71"/></svg><span>间歇组</span></button>
</aside><div class="chartframe" id="chartFrame"><svg id="chart" class="timeline" role="img" aria-label="从零开始的连续时间轴"></svg></div></div>
<div class="zoom-tools"><span class="tiny">时间缩放</span><button id="zoomOut" type="button" aria-label="缩小时间轴">−</button><output id="zoomValue">24 px/min</output><button id="zoomIn" type="button" aria-label="放大时间轴">＋</button></div>
<p class="tiny">横轴统一按时间比例绘制，从 0:00 开始；点选块精确编辑。间歇组合块可点击展开。</p>
<div id="selection" class="segment-editor" hidden></div>
</article>
<article><h2>阶段列表（辅助操作）</h2><div id="stages"></div></article>
<article><button id="save">保存课程</button><button id="back">返回列表</button>
<p class="tiny">“选择课程”只代表存入待选状态，训练执行引擎尚未交付。当前模拟训练 API 仍限制 40–150 W。</p></article>
</section>
<p id="message" role="alert" aria-live="polite"></p>
</main>
<script>
const $=id=>document.getElementById(id), tok=$('token'), NS='http://www.w3.org/2000/svg';
tok.value=sessionStorage.getItem('cyclingToken')||'';
tok.oninput=()=>{sessionStorage.setItem('cyclingToken',tok.value);refresh();};
let draft=null,editId=null,selected=null, view='power', focus=null, timeline=[], chartWidth=720, pointer=null, pxPerMinute=24, expandedGroups=new WeakSet();
let zoneSettings={ftp_w:null,hr_max_bpm:null};
const colors=['#778ca3','#1cb7a5','#d0b751','#ee9951','#e16d71','#a18cf0'];
const purposes={warmup:'热身',main:'主训练',recovery:'恢复',cooldown:'冷身',custom:'自定义'};
const zoneColors=z=>colors[Math.max(1,Math.min(6,z))-1];
const leaf=(kind='constant',zone=2)=>({kind,name:kind==='ramp'?'变化阶段':'骑行阶段',purpose:'main',duration_s:300,
 power_zones:{from:zone,to:kind==='ramp'?Math.min(6,zone+1):zone}});
const group=()=>({kind:'repeat',name:'间歇组',repeat_count:3,steps:[
 {...leaf('constant',4),name:'工作',duration_s:120},{...leaf('constant',1),name:'恢复',purpose:'recovery',duration_s:120}]});
function msg(text){$('message').textContent=text||'';}
async function api(path='',method='GET',body){
 if(!tok.value)throw Error('请先输入本机访问凭证');
 const response=await fetch('/api/plans'+path,{method,
 headers:{'X-Cycling-Token':tok.value,'Content-Type':'application/json'},
 body:body===undefined?undefined:JSON.stringify(body)});
 const result=await response.json();
 if(!response.ok)throw Error(typeof result.detail==='string'?result.detail:'HTTP '+response.status);
 return result;
}
function el(tag,text='',cls=''){const e=document.createElement(tag);e.textContent=text;e.className=cls;return e;}
function button(parent,text,fn){const e=el('button',text);e.type='button';e.onclick=()=>Promise.resolve().then(fn).catch(err=>msg(err.message));parent.append(e);return e;}
function field(parent,label,value,change,options){
 const box=el('label',label,'plan-field'),e=el(options?'select':'input');
 if(options){for(const [v,label] of options){const o=el('option',label);o.value=v;e.append(o);}}
 else{e.type=typeof value==='number'?'number':'text';if(e.type==='number')e.step='0.5';}
 e.value=String(value);
 e.onchange=()=>{change(e.value);draw();};
 box.append(e);parent.append(box);
}
function clone(value){return JSON.parse(JSON.stringify(value));}
function bounds(num){return Math.max(1,Math.min(6,num));}
function stageAt(path){return path.step==null?draft.stages[path.index]:draft.stages[path.index].steps[path.step];}
function setZone(target,zone){
 const s=stageAt(target);const z=bounds(zone);
 if(view==='power'){
  const old=s.power_zones||{from:z,to:z};
  if(s.kind==='ramp'){
   const delta=z-old.from;
   s.power_zones={from:z,to:bounds(old.to+delta)};
  }else{s.power_zones={from:z,to:z};}
  delete s.watts;delete s.start_watts;delete s.end_watts;
 }else{
  const old=s.hr_zones||{from:z,to:z};
  if(s.kind==='ramp'){const delta=z-old.from;s.hr_zones={from:z,to:bounds(old.to+delta)};}
  else s.hr_zones={from:z,to:z};
 }
 draw();
}
function listFlat(){
 const list=[];
 draft.stages.forEach((s,index)=>{
  if(s.kind==='repeat'){
   if(!expandedGroups.has(s)){list.push({stage:s,index,step:null,group:true});return;}
   for(let rep=0;rep<s.repeat_count;rep++)s.steps.forEach((step,stepIndex)=>list.push({stage:step,index,step:stepIndex,group:false}));
  }else list.push({stage:s,index,step:null,group:false});
 });
 return list;
}
function stageDuration(s){return s.kind==='repeat'?s.repeat_count*s.steps.reduce((n,x)=>n+x.duration_s,0):s.duration_s;}
function fmt(sec){const m=Math.floor(sec/60),s=sec%60;return m+':'+String(s).padStart(2,'0');}
function summary(){
 if(!draft)return;
 let secs=0,count=0;
 for(const s of draft.stages){if(s.kind==='repeat'){secs+=s.repeat_count*s.steps.reduce((sum,x)=>sum+x.duration_s,0);count+=s.repeat_count*s.steps.length;}
 else{secs+=s.duration_s;count++;}}
 $('summary').textContent='总时长 '+fmt(secs)+' · '+count+' 个执行阶段';
}
function svgNode(tag,attributes={},parent=$('chart')){
 const e=document.createElementNS(NS,tag);
 for(const [key,value] of Object.entries(attributes))e.setAttribute(key,String(value));
 parent.append(e);return e;
}
function chartZone(s){
 if(view==='hr')return s.hr_zones;
 if(s.power_zones)return s.power_zones;
 if(zoneSettings.ftp_w){
  const factor=zoneSettings.ftp_w;const first=s.kind==='constant'?s.watts:s.start_watts;
  const last=s.kind==='constant'?s.watts:s.end_watts;
  const zone=w=>w/factor<=.55?1:w/factor<=.75?2:w/factor<=.9?3:w/factor<=1.05?4:w/factor<=1.2?5:6;
  return {from:zone(first),to:zone(last)};
 }
 return null;
}
function targetLabel(s,zones){
 if(!zones)return view==='hr'?'心率未设置':'FTP 未校准';
 if(view==='power'&&!s.power_zones){
  return s.kind==='constant'?s.watts+' W':s.start_watts+'→'+s.end_watts+' W';
 }
 const label='Z'+zones.from+(zones.from===zones.to?'':'→Z'+zones.to);
 const base=view==='power'?zoneSettings.ftp_w:zoneSettings.hr_max_bpm;
 if(!base)return label;
 const pct=view==='power'?[[0,55],[55,75],[75,90],[90,105],[105,120],[120,null]]:
  [[50,60],[60,70],[70,80],[80,90],[90,95],[95,100]];
 const lo=Math.round(base*pct[zones.from-1][0]/100),h=pct[zones.to-1][1];
 return label+' '+lo+'–'+(h===null?'∞':Math.round(base*h/100))+(view==='power'?'W':'bpm');
}
function groupTargetLabel(s){
 const zones=s.steps.map(c=>chartZone(c)).filter(Boolean);
 const unique=[...new Set(zones.map(z=>'Z'+z.from+(z.to===z.from?'':'→Z'+z.to)))];
 if(!unique.length)return view==='hr'?'心率目标未设':'功率未校准';
 return unique.join(' / ')+' ×'+s.repeat_count;
}
function shape(kind){
 if(kind==='repeat')return group();
 let s;
 if(kind==='rise')s={...leaf('ramp',1),name:'递增',power_zones:{from:1,to:3}};
 else if(kind==='fall')s={...leaf('ramp',3),name:'递减',power_zones:{from:3,to:1}};
 else s=leaf('constant',2);
 if(view==='hr')s.hr_zones=kind==='rise'?{from:1,to:3}:kind==='fall'?{from:3,to:1}:{from:2,to:2};
 return s;
}
function addShape(kind,at=draft.stages.length){
 const index=Math.max(0,Math.min(at,draft.stages.length));
 draft.stages.splice(index,0,shape(kind));focus={index,step:null};
 draw();msg('形状已添加，可在下方精确编辑');
}
function initShapeTools(){
 for(const button of document.querySelectorAll('[data-shape]')){
  let origin=null,skipClick=false;
  button.addEventListener('pointerdown',e=>{origin={x:e.clientX,y:e.clientY};skipClick=false;button.setPointerCapture(e.pointerId);});
  button.addEventListener('pointerup',e=>{
   if(!origin)return;const distance=Math.hypot(e.clientX-origin.x,e.clientY-origin.y);origin=null;
   if(distance<15)return;
   skipClick=true;
   const rect=$('chartFrame').getBoundingClientRect();
   if(e.clientX<rect.left||e.clientX>rect.right||e.clientY<rect.top||e.clientY>rect.bottom){
    msg('请把形状放进时间轴，或直接点击图标追加。');return;
   }
   const x=$('chartFrame').scrollLeft+e.clientX-rect.left;
   const next=timeline.find(t=>x<t.x+t.w/2);
   addShape(button.dataset.shape,next?next.index:draft.stages.length);
  });
  button.addEventListener('pointercancel',()=>{origin=null;});
  button.addEventListener('click',()=>{if(skipClick){skipClick=false;return;}addShape(button.dataset.shape);});
 }
}
function draw(){
 if(!draft)return;summary();
 const svg=$('chart');svg.replaceChildren();timeline=[];
 const parts=listFlat(),seconds=parts.reduce((n,t)=>n+stageDuration(t.stage),0);
 // Exactly one scale across all segments, including expanded interval children.
 const left=106,top=76,bottom=307,band=(bottom-top)/6,plot=seconds/60*pxPerMinute;
 chartWidth=Math.max(390,left+plot+30);
 svg.setAttribute('width',chartWidth);svg.setAttribute('height',365);
 svg.setAttribute('viewBox','0 0 '+chartWidth+' 365');
 $('zoomValue').textContent=pxPerMinute+' px/min';
 const y=z=>bottom-(z-.5)*band;
 const pct=view==='power'?[[0,55],[55,75],[75,90],[90,105],[105,120],[120,null]]:
  [[50,60],[60,70],[70,80],[80,90],[90,95],[95,100]];
 const basis=view==='power'?zoneSettings.ftp_w:zoneSettings.hr_max_bpm;
 for(let z=1;z<=6;z++){
  const cy=y(z),p=pct[z-1];
  svgNode('line',{x1:left,y1:cy+band/2,x2:chartWidth-10,y2:cy+band/2,stroke:'#38536d'});
  svgNode('text',{x:5,y:cy+4,class:'zoneaxis'}).textContent=basis?'Z'+z+' '+Math.round(basis*p[0]/100)+'–'+(p[1]===null?'∞':Math.round(basis*p[1]/100)):'Z'+z;
 }
 const step=seconds<=1800?5:seconds<=5400?10:15;
 for(let minute=0;minute*60<=seconds;minute+=step){
  const x=left+minute*pxPerMinute;
  svgNode('line',{x1:x,y1:top,x2:x,y2:bottom+6,stroke:'#4b6987',
   'stroke-width':minute===0?2:1,'stroke-dasharray':minute===0?'none':'3 6'});
  svgNode('text',{x,y:bottom+28,class:'axis','text-anchor':'middle'}).textContent=fmt(minute*60);
 }
 svgNode('line',{x1:left,y1:bottom,x2:left+plot,y2:bottom,stroke:'#c4dbea','stroke-width':2});
 let elapsed=0;
 parts.forEach((t,i)=>{
  const s=t.stage,d=stageDuration(s),x=left+elapsed/60*pxPerMinute,w=d/60*pxPerMinute;
  timeline.push({...t,x,w});elapsed+=d;
  const chosen=focus?.index===t.index&&focus?.step===t.step;
  if(t.group){
   const gy=top+58;
   svgNode('rect',{x,y:gy,width:w,height:bottom-gy,rx:5,fill:'#273e54',
    stroke:chosen?'white':'#82e3c6','stroke-width':chosen?2.5:1.5,class:'group-block','data-index':i});
   if(w>=58){
    svgNode('text',{x:x+w/2,y:gy+26,'text-anchor':'middle',fill:'white','font-size':12,'pointer-events':'none'}).textContent='间歇 ×'+s.repeat_count;
    svgNode('text',{x:x+w/2,y:gy+49,'text-anchor':'middle',fill:'white','font-size':12,'pointer-events':'none'}).textContent=fmt(d);
    const cycle=s.steps.reduce((n,c)=>n+c.duration_s,0);let bx=x;
    for(let j=0;j<s.repeat_count;j++)for(const c of s.steps){
     const cw=w*c.duration_s/(cycle*s.repeat_count);
     // Miniature pattern, still inside a single collapsed group.
     svgNode('rect',{x:bx,y:bottom-35,width:cw,height:35,fill:zoneColors(chartZone(c)?.from??2),
      stroke:'#182a3e','stroke-width':.5,'pointer-events':'none'});bx+=cw;
    }
   }
   svgNode('text',{x:x+w/2,y:gy-11,class:'axis','text-anchor':'middle','pointer-events':'none'}).textContent=
    w>=75?groupTargetLabel(s):'×'+s.repeat_count;
  }else{
   const zones=chartZone(s),y0=zones?y(zones.from):top+85,y1=zones?y(zones.to):top+85;
   svgNode('polygon',{points:[[x,y0],[x+w,y1],[x+w,bottom],[x,bottom]].map(v=>v.join(',')).join(' '),
    fill:zones?zoneColors(zones.from):'#778ca3',opacity:zones?.9:.5,
    stroke:chosen?'white':'#0e1d2e','stroke-width':chosen?2.5:1,class:'block','data-index':i});
   // Target label belongs above the shape in the currently selected view.
   if(w>=58){
    const full=targetLabel(s,zones),compact=zones?'Z'+zones.from+(zones.from===zones.to?'':'→Z'+zones.to):full;
    svgNode('text',{x:x+w/2,y:Math.max(17,Math.min(y0,y1)-11),
     fill:'#e7f2ff','font-size':11,'text-anchor':'middle','pointer-events':'none'}).textContent=
       full.length*6.5+8<=w?full:compact;
   }
   if(w>=70)svgNode('text',{x:x+w/2,y:bottom-42,fill:'white','font-size':12,
    'text-anchor':'middle','pointer-events':'none'}).textContent=s.name.slice(0,Math.floor(w/12));
   svgNode('text',{x:x+w/2,y:bottom-20,fill:'white','font-size':w<30?9:12,
    'text-anchor':'middle','pointer-events':'none'}).textContent=d%60===0?(d/60)+'分':fmt(d);
   if(w>=25)svgNode('rect',{x:x+w-17,y:Math.min(y0,y1),width:17,height:bottom-Math.min(y0,y1),
    fill:'white',opacity:.08,class:'handle','data-index':i,'data-resize':'true'});
  }
 });
 svg.querySelectorAll('[data-index]').forEach(n=>n.addEventListener('pointerdown',chartPointerDown));
 $('powerTab').setAttribute('aria-selected',view==='power');$('hrTab').setAttribute('aria-selected',view==='hr');
 $('guide').textContent='左侧选择形状；块内为时长，块上方为'+(view==='power'?'功率':'心率')+'目标，时间从 0:00 开始。';
 renderSelection();renderStages();
}
function chartPointerDown(e){
 const i=Number(e.currentTarget.dataset.index),t=timeline[i];
 pointer={i,x:e.clientX,y:e.clientY,resizing:e.currentTarget.dataset.resize==='true',duration:t.stage.duration_s};
 e.currentTarget.setPointerCapture(e.pointerId);
 e.currentTarget.addEventListener('pointerup',chartPointerUp,{once:true});
 e.currentTarget.addEventListener('pointercancel',()=>{pointer=null;},{once:true});
 e.preventDefault();
}
function chartPointerUp(e){
 if(!pointer)return;const p=pointer;pointer=null;
 const t=timeline[p.i];if(!t)return;
 const dx=e.clientX-p.x,dy=e.clientY-p.y;
 focus={index:t.index,step:t.step};
 if(t.group){
  const s=draft.stages[t.index];expandedGroups.has(s)?expandedGroups.delete(s):expandedGroups.add(s);
  draw();return;
 }
 if(p.resizing){
  t.stage.duration_s=Math.max(30,Math.min(7200,Math.round((p.duration+dx/pxPerMinute*60)/30)*30));
  draw();return;
 }
 if(Math.abs(dy)>20&&Math.abs(dy)>Math.abs(dx)){
  const z=chartZone(t.stage)?.from??2;
  setZone(t,Math.round(z-dy/((307-76)/6)));return;
 }
 draw();
}
function renderSelection(){
 const root=$('selection');root.replaceChildren();
 if(!focus||!draft.stages[focus.index]){root.hidden=true;return;}
 let s=stageAt(focus);if(!s){root.hidden=true;return;}
 root.hidden=false;root.append(el('h2',s.name));
 if(s.kind==='repeat'){
  root.append(el('p','组合块：'+s.repeat_count+' 组 · '+fmt(stageDuration(s)),'tiny'));
  field(root,'名称',s.name,v=>s.name=v);
  field(root,'重复次数',s.repeat_count,v=>s.repeat_count=Number(v));
  button(root,expandedGroups.has(s)?'折叠间歇':'展开间歇',()=>{
   expandedGroups.has(s)?expandedGroups.delete(s):expandedGroups.add(s);draw();
  });
  button(root,'编辑组内第一段',()=>{expandedGroups.add(s);focus={index:focus.index,step:0};draw();});
  return;
 }

 const groupStage=focus.step!==null;
 if(groupStage)root.append(el('p','编辑的是重复组的子阶段，所有重复轮次共享此设置。','tiny'));
 field(root,'阶段名称',s.name,v=>s.name=v);
 field(root,'用途',s.purpose,v=>s.purpose=v,Object.entries(purposes));
 field(root,'时长（分钟）',s.duration_s/60,v=>s.duration_s=Math.round(Number(v)*60));
 field(root,'功率轨迹',s.kind,v=>{
  if(v!==s.kind){
   if(v==='constant'){
    s.kind=v;
    if(s.power_zones)s.power_zones={from:s.power_zones.from,to:s.power_zones.from};
    else{s.watts=s.start_watts??90;delete s.start_watts;delete s.end_watts;}
   }else{
    s.kind=v;
    if(s.power_zones)s.power_zones={from:s.power_zones.from,to:Math.min(6,s.power_zones.from+1)};
    else{s.start_watts=s.watts??60;s.end_watts=s.watts??110;delete s.watts;}
   }
  }draw();
 },[['constant','恒定'],['ramp','递增/递减']]);
 field(root,'功率目标模式',s.power_zones?'zone':'watts',v=>{
  if(v==='zone'){s.power_zones={from:2,to:s.kind==='ramp'?3:2};delete s.watts;delete s.start_watts;delete s.end_watts;}
  else{delete s.power_zones;if(s.kind==='constant')s.watts=90;else{s.start_watts=60;s.end_watts=100;}}
  draw();
 },[['zone','FTP 区间'],['watts','固定瓦数（仅编辑，未连接 ERG）']]);
 if(s.power_zones){
  field(root,'功率起始 Z',s.power_zones.from,v=>s.power_zones.from=Number(v),
   [1,2,3,4,5,6].map(x=>[String(x),'Z'+x]));
  if(s.kind==='ramp')field(root,'功率结束 Z',s.power_zones.to,v=>s.power_zones.to=Number(v),
   [1,2,3,4,5,6].map(x=>[String(x),'Z'+x]));
 }else if(s.kind==='constant')field(root,'目标功率（W）',s.watts,v=>s.watts=Number(v));
 else{field(root,'起始功率（W）',s.start_watts,v=>s.start_watts=Number(v));
  field(root,'结束功率（W）',s.end_watts,v=>s.end_watts=Number(v));}
 field(root,'心率目标',s.hr_zones?'zones':'none',v=>{
  if(v==='none')delete s.hr_zones;
  else s.hr_zones={from:2,to:3};
  draw();
 },[['none','不设置'],['zones','Z 区间提醒（不自动控制）']]);
 if(s.hr_zones){
  field(root,'心率下限 Z',s.hr_zones.from,v=>s.hr_zones.from=Number(v),
   [1,2,3,4,5,6].map(x=>[String(x),'Z'+x]));
  field(root,'心率上限 Z',s.hr_zones.to,v=>s.hr_zones.to=Number(v),
   [1,2,3,4,5,6].map(x=>[String(x),'Z'+x]));
 }
 if(groupStage)button(root,'移除组内子阶段',()=>{
  const steps=draft.stages[focus.index].steps;
  if(steps.length<=2){msg('间歇组至少需要两个子阶段');return;}
  steps.splice(focus.step,1);focus=null;draw();
 });
 else{
  const actions=el('div','','plan-buttons');
  button(actions,'前移',()=>moveTop(focus.index,-1));
  button(actions,'后移',()=>moveTop(focus.index,1));
  button(actions,'复制',()=>{draft.stages.splice(focus.index+1,0,clone(s));focus.index++;draw();});
  button(actions,'删除',()=>{draft.stages.splice(focus.index,1);focus=null;draw();});
  root.append(actions);
 }
}
function moveTop(i,delta){
 const j=i+delta;if(j<0||j>=draft.stages.length)return;
 [draft.stages[i],draft.stages[j]]=[draft.stages[j],draft.stages[i]];
 focus.index=j;draw();
}
function renderStages(){
 const root=$('stages');root.replaceChildren();
 draft.stages.forEach((s,index)=>{
  const line=el('div',(index+1)+' · '+s.name+(s.kind==='repeat'?' ×'+s.repeat_count:''),'row');
  button(line,'编辑',()=>{
   focus={index,step:null};
   draw();$('selection').scrollIntoView({block:'nearest',behavior:'smooth'});
  });
  if(s.kind==='repeat'){
   button(line,'轮次 −',()=>{s.repeat_count=Math.max(1,s.repeat_count-1);draw();});
   button(line,'轮次 ＋',()=>{s.repeat_count=Math.min(30,s.repeat_count+1);draw();});
   button(line,'加子阶段',()=>{if(s.steps.length>=10){msg('最多十个子阶段');return;}
    s.steps.push(leaf());draw();});
  }
  button(line,'↑',()=>moveTop(index,-1));
  button(line,'↓',()=>moveTop(index,1));
  button(line,'复制',()=>{draft.stages.splice(index+1,0,clone(s));draw();});
  button(line,'删除',()=>{draft.stages.splice(index,1);focus=null;draw();});
  root.append(line);
 });
}
function open(plan){
 editId=plan?.id??null;focus=null;view='power';expandedGroups=new WeakSet();
 draft=plan?clone({name:plan.name,note:plan.note,stages:plan.stages}):
  {name:'新课程',note:'',stages:[{...leaf('constant',1),name:'热身',purpose:'warmup'}]};
 $('name').value=draft.name;$('note').value=draft.note;
 $('heading').textContent=editId?'编辑课程':'新建课程';
 $('library').hidden=true;$('editor').hidden=false;
 $('ftp').value=zoneSettings.ftp_w??'';$('maxhr').value=zoneSettings.hr_max_bpm??'';
 draw();msg('');
}
async function refresh(){
 if(!tok.value)return;
 try{
  const [plans,presets,chosen,zones]=await Promise.all([api(),api('/presets'),api('/selected'),api('/zones')]);
  selected=chosen;zoneSettings=zones.settings;
  const list=$('list');list.replaceChildren();
  if(!plans.length)list.append(el('p','尚无个人课程。可直接从预设复制。','muted'));
  for(const p of plans){
   const card=el('article');
   card.append(el('h2',p.name+(selected?.id===p.id?' · 已选中':'')));
   card.append(el('p',fmt(p.duration_s)+' · '+p.stage_count+' 个执行阶段','muted'));
   const actions=el('div','','plan-buttons');
   button(actions,'编辑',async()=>open(await api('/'+p.id)));
   button(actions,'选择',async()=>{
    await api('/select','POST',{id:p.id});await refresh();
    msg('仅选中计划：训练页仍执行自由模拟训练，尚不能自动执行本课程。');
   });
   button(actions,'复制',async()=>{await api('/'+p.id+'/duplicate','POST');await refresh();});
   button(actions,'删除',async()=>{
    if(!confirm('删除 '+p.name+'？'))return;await api('/'+p.id,'DELETE');await refresh();
   });card.append(actions);list.append(card);
  }
  const box=$('presets');box.replaceChildren();
  for(const p of presets){
   const line=el('div','','row preset');line.append(el('strong',p.name));
   line.append(el('p',fmt(p.duration_s)+' · '+p.note,'tiny'));
   button(line,'复制到我的课程',async()=>{
    const copy=await api('/presets/'+p.slug+'/copy','POST');await refresh();open(copy);
    msg('已复制预设。可继续修改并保存。');
   });
   box.append(line);
  }
  msg('');
 }catch(err){msg(err.message);}
}
$('new').onclick=()=>open(null);
$('powerTab').onclick=()=>{view='power';draw();};
$('hrTab').onclick=()=>{view='hr';draw();};
$('zoomOut').onclick=()=>{pxPerMinute=Math.max(12,pxPerMinute-6);draw();};
$('zoomIn').onclick=()=>{pxPerMinute=Math.min(72,pxPerMinute+6);draw();};
initShapeTools();
$('savezones').onclick=async()=>{
 try{
  const ftp=$('ftp').value,hr=$('maxhr').value;
  zoneSettings=await api('/zones','PUT',{ftp_w:ftp?Number(ftp):null,hr_max_bpm:hr?Number(hr):null});
  draw();msg('训练区间参考值已保存；后续需要根据个人实际测试校准。');
 }catch(e){msg(e.message);}
};
$('back').onclick=()=>{
 $('editor').hidden=true;$('library').hidden=false;draft=null;focus=null;refresh();
};
$('save').onclick=async()=>{
 try{
  draft.name=$('name').value;draft.note=$('note').value;
  await api(editId?'/'+editId:'',editId?'PUT':'POST',draft);
  $('back').click();msg('课程已保存，尚未开始训练。');
 }catch(e){msg(e.message);}
};
refresh();
</script></html>"""