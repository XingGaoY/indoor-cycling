"""Workout plans page. All power values here are planning values, not hardware commands."""
HTML = """<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>训练计划 · Indoor Cycling</title><style></style>
<main class="wrap"><div class="eyebrow">INDOOR CYCLING</div><h1>训练计划</h1>
<p class="muted">创建课程、编排阶段、保存与选择。当前只能规划课程；点击训练页「开始」仍是自由模拟训练。</p>
<article><label>控制令牌（当前标签页会话内保存）<input id="token" type="password" autocomplete="off" placeholder="CYCLING_TOKEN"></label></article>
<section id="library"><button id="new">＋ 新建课程</button><div id="list"></div></section>
<section id="editor" hidden><article><h2 id="heading">编辑课程</h2>
<label>课程名称<input id="name" maxlength="80"></label>
<label>备注<textarea id="note" maxlength="500" rows="2"></textarea></label>
<p class="muted" id="summary"></p></article>
<div id="stages"></div>
<article><h2>添加阶段</h2><button id="addConstant">恒定功率</button>
<button id="addRamp">线性变化</button><button id="addRepeat">间歇组</button></article>
<article><button id="save">保存课程</button><button id="back">取消</button>
<p class="muted">课程规划允许 40–500 W，和真实 T300 的受支持功率范围无关；模拟接口仍为 40–150 W。</p></article></section>
<p id="message" role="alert"></p></main><script>
const $=id=>document.getElementById(id), tok=$('token');
tok.value=sessionStorage.getItem('cyclingToken')||'';
tok.oninput=()=>{sessionStorage.setItem('cyclingToken',tok.value);refresh();};
let draft=null,editId=null,selected=null;
const purposes={warmup:'热身',main:'主训练',recovery:'恢复',cooldown:'冷身',custom:'自定义'};
const leaf=(kind='constant')=>({kind,name:'骑行阶段',purpose:'main',duration_s:300,
 ...(kind==='constant'?{watts:90}:{start_watts:60,end_watts:110})});
const group=()=>({kind:'repeat',name:'间歇组',repeat_count:3,steps:[
 {...leaf(),name:'训练',watts:120,duration_s:120},
 {...leaf(),name:'恢复',watts:70,duration_s:120}]});
function msg(value){$('message').textContent=value||'';}
async function api(path='',method='GET',body){
 if(!tok.value)throw Error('请先输入控制令牌');
 const r=await fetch('/api/plans'+path,{method,headers:{'X-Cycling-Token':tok.value,'Content-Type':'application/json'},
 body:body===undefined?undefined:JSON.stringify(body)});
 const d=await r.json();if(!r.ok)throw Error(typeof d.detail==='string'?d.detail:'HTTP '+r.status);return d;
}
function node(tag,text='',cls=''){const x=document.createElement(tag);x.textContent=text;x.className=cls;return x;}
function btn(p,label,action){const b=node('button',label);b.type='button';b.onclick=()=>Promise.resolve().then(action).catch(e=>msg(e.message));p.append(b);return b;}
function field(p,label,value,set,opts){
 const l=node('label',label,'plan-field'),input=opts?node('select'):node('input');
 if(opts){for(const [v,t] of opts){const o=node('option',t);o.value=v;input.append(o);}}
 else {input.type=typeof value==='number'?'number':'text';if(input.type==='number')input.step='0.5';}
 input.value=String(value);input.onchange=()=>{set(input.value);summary();};l.append(input);p.append(l);
}
function leafFields(item,part){
 field(part,'名称',item.name,v=>item.name=v);
 field(part,'用途',item.purpose,v=>item.purpose=v,Object.entries(purposes));
 field(part,'模式',item.kind,v=>{
  if(v===item.kind)return;
  if(v==='constant'){item.watts=item.start_watts??90;delete item.start_watts;delete item.end_watts;}
  else{item.start_watts=item.watts??60;item.end_watts=item.watts??110;delete item.watts;}
  item.kind=v;render();
 },[['constant','恒定'],['ramp','线性变化']]);
 field(part,'时长（分钟）',item.duration_s/60,v=>item.duration_s=Math.round(Number(v)*60));
 if(item.kind==='constant')field(part,'功率（W）',item.watts,v=>item.watts=Number(v));
 else{field(part,'起始（W）',item.start_watts,v=>item.start_watts=Number(v));
 field(part,'结束（W）',item.end_watts,v=>item.end_watts=Number(v));}
}
function summary(){
 if(!draft)return;
 let seconds=0,count=0;
 for(const s of draft.stages)if(s.kind==='repeat'){
  seconds+=s.repeat_count*s.steps.reduce((n,c)=>n+c.duration_s,0);count+=s.repeat_count*s.steps.length;
 }else{seconds+=s.duration_s;count++;}
 $('summary').textContent='总时长 '+(seconds/60).toFixed(1)+' 分钟 · '+count+' 个执行阶段';
}
function move(i,d){const j=i+d;if(j<0||j>=draft.stages.length)return;
 [draft.stages[i],draft.stages[j]]=[draft.stages[j],draft.stages[i]];render();}
function render(){
 const root=$('stages');root.replaceChildren();
 if(!draft)return;
 draft.stages.forEach((s,i)=>{
  const box=node('article');box.append(node('h2',(i+1)+'. '+(s.kind==='repeat'?'间歇组':'阶段')));
  const actions=node('div','','plan-buttons');
  btn(actions,'↑',()=>move(i,-1)).disabled=i===0;
  btn(actions,'↓',()=>move(i,1)).disabled=i===draft.stages.length-1;
  btn(actions,'复制',()=>{draft.stages.splice(i+1,0,structuredClone(s));render();});
  btn(actions,'删除',()=>{draft.stages.splice(i,1);render();});
  box.append(actions);
  if(s.kind==='repeat'){
   field(box,'名称',s.name,v=>s.name=v);
   field(box,'重复次数',s.repeat_count,v=>s.repeat_count=Number(v));
   s.steps.forEach((c,k)=>{
    const part=node('div','','plan-sub');part.append(node('small','组内阶段 '+(k+1)));
    leafFields(c,part);
    btn(part,'移除组内阶段',()=>{if(s.steps.length<=2){msg('间歇组至少需要两个阶段');return;}
      s.steps.splice(k,1);render();});
    box.append(part);
   });
   btn(box,'＋ 添加组内阶段',()=>{s.steps.push(leaf());render();});
  }else leafFields(s,box);
  root.append(box);
 });
 summary();
}
function open(plan){
 editId=plan?.id||null;
 draft=plan?structuredClone({name:plan.name,note:plan.note,stages:plan.stages}):
  {name:'新课程',note:'',stages:[{...leaf(),name:'热身',purpose:'warmup',watts:70}]};
 $('name').value=draft.name;$('note').value=draft.note;
 $('heading').textContent=editId?'编辑课程':'新建课程';
 $('library').hidden=true;$('editor').hidden=false;render();msg('');
}
async function refresh(){
 if(!tok.value)return;
 try{const [plans,s]=await Promise.all([api(),api('/selected')]);selected=s;
 const root=$('list');root.replaceChildren();
 if(!plans.length)root.append(node('p','暂无计划，创建你的第一堂课程。','muted'));
 for(const p of plans){
  const a=node('article');a.append(node('h2',p.name+(selected?.id===p.id?' · 已选中':'')));
  a.append(node('p',(p.duration_s/60).toFixed(1)+' 分钟 · '+p.stage_count+' 个执行阶段','muted'));
  const actions=node('div','','plan-buttons');
  btn(actions,'编辑',async()=>open(await api('/'+p.id)));
  btn(actions,'选择',async()=>{await api('/select','POST',{id:p.id});await refresh();msg('已选择课程，但还不能自动执行；训练页仍为自由模拟训练。');});
  btn(actions,'复制',async()=>{await api('/'+p.id+'/duplicate','POST');await refresh();});
  btn(actions,'删除',async()=>{if(!confirm('确定删除课程：'+p.name+'？'))return;
   await api('/'+p.id,'DELETE');await refresh();});
  a.append(actions);root.append(a);
 }
 }catch(e){msg(e.message);}
}
$('new').onclick=()=>open(null);
$('addConstant').onclick=()=>{draft.stages.push(leaf());render();};
$('addRamp').onclick=()=>{draft.stages.push(leaf('ramp'));render();};
$('addRepeat').onclick=()=>{draft.stages.push(group());render();};
$('back').onclick=()=>{$('editor').hidden=true;$('library').hidden=false;draft=null;refresh();};
$('save').onclick=async()=>{
 try{draft.name=$('name').value;draft.note=$('note').value;
 await api(editId?'/'+editId:'',editId?'PUT':'POST',draft);
 $('back').click();msg('课程已保存');}
 catch(e){msg(e.message);}
};
refresh();
</script></html>"""