"""Interactive power/heart-rate timeline editor. No training execution or hardware control."""
HTML = """<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>可视化课程编排 · Indoor Cycling</title><style></style>
<style id="timeline-style">
.picker{display:flex;gap:6px;flex-wrap:wrap;margin:12px 0}
.zonechip{padding:8px 13px;min-height:44px;min-width:48px;border:1px solid #475b73;background:#263a53;touch-action:none}
.zonechip[aria-pressed=true]{outline:2px solid #83e1c3}
.chartframe{overflow-x:auto;overflow-y:hidden;border:1px solid #33445b;border-radius:14px;background:#101d30}
.timeline{display:block;touch-action:pan-x;min-height:285px}
.timeline .block{cursor:pointer;touch-action:none}
.timeline .handle{cursor:ew-resize;touch-action:none}
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
<p class="tiny" id="guide">横轴时长、纵轴区间。点选块编辑；上下拖动改变区间；拖动右侧把手改变时长。间歇组中修改一个子阶段会应用到全部重复。</p>
<div class="picker" id="palette" aria-label="新增区间块"></div>
<div class="chartframe" id="chartFrame"><svg id="chart" class="timeline" role="img" aria-label="训练阶段时间轴"></svg></div>
<p class="tiny">可将上方 Z 区间拖进时间轴插入，或点击追加。触屏上也可点选下面的阶段进行精确编辑。</p>
<div id="selection" class="segment-editor" hidden></div>
</article>
<article><h2>添加结构</h2>
<button id="addConstant">＋ 恒定区间</button>
<button id="addRamp">＋ 递增／递减</button>
<button id="addRepeat">＋ 间歇组</button>
<p class="tiny">间歇组第一版支持一层重复。通过点选图表中块或下方列表进入编辑。</p>
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
let draft=null,editId=null,selected=null, view='power', focus=null, timeline=[], chartWidth=720, pointer=null;
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
 }else s.hr_zones={from:z,to:z};
 draw();
}
function listFlat(){
 const result=[];
 draft.stages.forEach((s,index)=>{
  if(s.kind==='repeat'){
   for(let repeat=0;repeat<s.repeat_count;repeat++)
    s.steps.forEach((step,stepIndex)=>result.push({stage:step,index,step:stepIndex,repeat}));
  }else result.push({stage:s,index,step:null,repeat:0});
 });
 return result;
}
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
function draw(){
 if(!draft)return;summary();
 const current=$('chart');current.replaceChildren();timeline=[];
 const flats=listFlat(), total=flats.reduce((n,v)=>n+v.stage.duration_s,0);
 // 2.5 px/minute, minimum 62 px/expanded stage, to keep blocks touch-friendly.
 const widths=flats.map(v=>Math.max(62,v.stage.duration_s/60*2.5));
 chartWidth=Math.max(410,widths.reduce((a,b)=>a+b,0)+132);
 current.setAttribute('width',chartWidth);current.setAttribute('height',290);
 current.setAttribute('viewBox','0 0 '+chartWidth+' 290');
 const top=35,bottom=253,left=114;const h=(bottom-top)/6;
 function y(zone){return bottom-(zone-.5)*h;}
 function zonelabel(z){
  const pct = view==='power' ? [[0,55],[55,75],[75,90],[90,105],[105,120],[120,null]][z-1] :
    [[50,60],[60,70],[70,80],[80,90],[90,95],[95,100]][z-1];
  const basis=view==='power'?zoneSettings.ftp_w:zoneSettings.hr_max_bpm;
  return basis ? 'Z'+z+' · '+Math.round(basis*pct[0]/100)+'–'+(pct[1]===null?'∞':Math.round(basis*pct[1]/100))+(view==='power'?' W':' bpm') : 'Z'+z;
 }
 for(let z=1;z<=6;z++){
  const cy=y(z);svgNode('line',{x1:106,y1:cy+h/2,x2:chartWidth-9,y2:cy+h/2,stroke:'#34506b','stroke-width':1});
  const label=svgNode('text',{x:6,y:cy+4,class:'zoneaxis'});label.textContent=zonelabel(z);
 }
 let x=left, seconds=0;
 svgNode('text',{x:left,y:18,class:'axis'}).textContent='0:00';
 flats.forEach((v,i)=>{
  const s=v.stage,w=widths[i],zones=chartZone(s);
  timeline.push({...v,x,w,start_s:seconds});seconds+=s.duration_s;
  if(zones){
   const y0=y(zones.from),y1=y(zones.to);
   const polygon=svgNode('polygon',{points:[[x,y0],[x+w,y1],[x+w,bottom],[x,bottom]].map(a=>a.join(',')).join(' '),
    fill:zoneColors(zones.from),opacity:.86,stroke:'#112235','stroke-width':1,
    class:'block','data-index':i});
   if(focus&&focus.index===v.index&&focus.step===v.step)
    polygon.setAttribute('stroke','#fff');
  }else{
   svgNode('rect',{x,y:top+6,width:w,height:bottom-top-6,fill:'#334155',opacity:.42,
     stroke:'#a8bbcf','stroke-dasharray':'5 4',class:'block','data-index':i});
  }
  const text=svgNode('text',{x:x+5,y:bottom-14,fill:'#fff','font-size':11,'pointer-events':'none'});
  text.textContent=w>=74?s.name.slice(0,8):'';
  const cap=svgNode('text',{x:x+4,y:bottom+14,class:'axis'});cap.textContent=fmt(seconds);
  // Expanded interval steps share underlying data, intentionally.
  svgNode('rect',{x:x+w-22,y:top,width:22,height:bottom-top,fill:'#ffffff',opacity:0,
   class:'handle','data-index':i,'data-resize':'true'});
  x+=w;
 });
 current.querySelectorAll('[data-index]').forEach(node=>{
  node.addEventListener('pointerdown',chartPointerDown);
 });
 $('powerTab').setAttribute('aria-selected',view==='power');
 $('hrTab').setAttribute('aria-selected',view==='hr');
 const label=view==='power'?'功率':'心率';
 $('guide').textContent='横轴时间、纵轴'+label+' Z1–Z6；点选块编辑，上下拖动选择区间，拖动块右边缘改变时长（30 秒步进）。';
 renderSelection();renderStages();
}
function chartPointerDown(e){
 if(!draft)return;
 const i=Number(e.currentTarget.dataset.index),item=timeline[i];
 pointer={i,startX:e.clientX,startY:e.clientY,resizing:!!e.currentTarget.dataset.resize,
  duration:item.stage.duration_s};
 e.currentTarget.setPointerCapture(e.pointerId);
 e.currentTarget.addEventListener('pointerup',chartPointerUp,{once:true});
 e.preventDefault();
}
function chartPointerUp(e){
 if(!pointer)return;
 const p=pointer;pointer=null;
 const item=timeline[p.i];if(!item)return;
 focus={index:item.index,step:item.step};
 const dx=e.clientX-p.startX,dy=e.clientY-p.startY;
 if(p.resizing){
  // SVG has 1 CSS pixel per local x unit due to matching width/viewbox.
  const newSecs=Math.round((p.duration+dx/item.w*item.stage.duration_s)/30)*30;
  item.stage.duration_s=Math.max(30,Math.min(7200,newSecs));
  draw();return;
 }
 if(Math.abs(dy)>22){
  const start=chartZone(item.stage)?.from??2;
  setZone(item,Math.round(start-dy/36));return;
 }
 draw();
}
function renderPalette(){
 const p=$('palette');p.replaceChildren();
 for(let z=1;z<=6;z++){
  const chip=el('button','＋ Z'+z,'zonechip');chip.type='button';
  chip.style.borderBottom='4px solid '+zoneColors(z);
  chip.title='点击追加，或拖入时间轴插入 Z'+z;
  chip.onpointerdown=e=>{
   const sx=e.clientX,sy=e.clientY;
   chip.setPointerCapture(e.pointerId);
   chip.onpointerup=up=>{
    chip.onpointerup=null;
    const bounds=$('chart').getBoundingClientRect();
    const inside=up.clientX>=bounds.left&&up.clientX<=bounds.right&&up.clientY>=bounds.top&&up.clientY<=bounds.bottom;
    let pos=draft.stages.length;
    if(inside){
     const localX=(up.clientX-bounds.left)*chartWidth/bounds.width;
     const item=timeline.find(v=>localX<v.x+v.w/2);
     if(item)pos=item.index;
    }
    const part=leaf('constant',z);
    if(view==='hr'){part.hr_zones={from:z,to:z};}
    draft.stages.splice(pos,0,part);
    focus={index:pos,step:null};
    draw();
   };
  };
  p.append(chip);
 }
}
function renderSelection(){
 const root=$('selection');root.replaceChildren();
 if(!focus||!draft.stages[focus.index]){root.hidden=true;return;}
 let s=stageAt(focus);if(!s){root.hidden=true;return;}
 root.hidden=false;root.append(el('h2',s.name));
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
   if(s.kind==='repeat'){focus={index,step:0};}else focus={index,step:null};
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
 editId=plan?.id??null;focus=null;view='power';
 draft=plan?clone({name:plan.name,note:plan.note,stages:plan.stages}):
  {name:'新课程',note:'',stages:[{...leaf('constant',1),name:'热身',purpose:'warmup'}]};
 $('name').value=draft.name;$('note').value=draft.note;
 $('heading').textContent=editId?'编辑课程':'新建课程';
 $('library').hidden=true;$('editor').hidden=false;
 $('ftp').value=zoneSettings.ftp_w??'';$('maxhr').value=zoneSettings.hr_max_bpm??'';
 draw();renderPalette();msg('');
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
$('addConstant').onclick=()=>{draft.stages.push(leaf());focus={index:draft.stages.length-1,step:null};draw();};
$('addRamp').onclick=()=>{draft.stages.push(leaf('ramp'));focus={index:draft.stages.length-1,step:null};draw();};
$('addRepeat').onclick=()=>{draft.stages.push(group());focus={index:draft.stages.length-1,step:0};draw();};
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