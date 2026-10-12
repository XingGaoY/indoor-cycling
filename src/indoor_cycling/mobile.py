"""Shared mobile page shell; navigation does not interrupt backend training."""
import re

STYLE = """<style>
:root{color-scheme:dark;--bg:#0c1422;--panel:#172438;--muted:#a8bbcf;--accent:#83e1c3}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:#eef5ff;font:16px system-ui,-apple-system,sans-serif}a{color:var(--accent)}.wrap{width:100%;max-width:560px;margin:auto;padding:calc(18px + env(safe-area-inset-top)) 18px calc(100px + env(safe-area-inset-bottom))}h1{font-size:28px;margin:10px 0 20px;letter-spacing:-1px}h2{font-size:18px;margin:0 0 14px}article{background:var(--panel);border:1px solid #283950;border-radius:20px;padding:20px;margin:16px 0;overflow-wrap:anywhere}small,.muted{color:var(--muted);font-size:13px;line-height:1.6}button,input{font:inherit;border-radius:12px;min-height:48px;padding:12px}button{cursor:pointer;border:0;background:#426bea;color:white;margin:4px 2px;font-weight:600}button:disabled{opacity:.5}input{width:100%;border:1px solid #40516a;background:#0e1a2c;color:white;margin:10px 0 0}button.danger,.danger{background:#9e364a}.big{font-size:46px;font-weight:650;font-variant-numeric:tabular-nums;line-height:1.3;margin:6px 0 18px}.row{border-top:1px solid #304057;padding:16px 0}.row>div:first-child{margin-bottom:8px;font-weight:600}.tabs{position:fixed;bottom:0;left:0;right:0;background:#101d30f5;border-top:1px solid #304057;display:flex;padding:8px 8px calc(8px + env(safe-area-inset-bottom));z-index:10;backdrop-filter:blur(16px)}.tabs a{flex:1;min-height:52px;display:flex;flex-direction:column;align-items:center;justify-content:center;text-decoration:none;color:#a8bbcf;font-size:12px;gap:3px;border-radius:12px}.tabs a[aria-current=page]{color:#83e1c3;background:#213b40}.tabs svg{width:22px;height:22px;stroke:currentColor;fill:none;stroke-width:1.8}.eyebrow{text-transform:uppercase;letter-spacing:2px;font-size:11px;color:var(--accent)}details.auth{background:transparent;border:1px solid #304057;border-radius:14px;padding:14px;margin:16px 0}summary{cursor:pointer;min-height:24px;font-size:14px;color:var(--muted)}#error{color:#ffb8c4}.metric-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}.metric-grid .big{font-size:28px;margin-bottom:0}.actions{display:grid;grid-template-columns:1fr 1fr;gap:8px}.actions button:last-child{grid-column:1/-1}#scan{width:100%;margin:0}.connection{color:var(--accent)}@media(max-width:360px){.wrap{padding-left:12px;padding-right:12px}article{padding:16px}.big{font-size:40px}}
</style>"""
ICONS = {
    '/': '<path d="M4 13h4l3-8 3 14 3-6h3"/>',
    '/devices': '<rect x="7" y="6" width="10" height="12" rx="3"/><path d="M9 6V2h6v4M9 18v4h6v-4"/>',
    '/history': '<path d="M6 3h12v18H6zM9 8h6M9 12h6M9 16h4"/>'
}

def shell(html, current):
    html = re.sub(r'<style>.*?</style>', STYLE, html, flags=re.S)
    html = re.sub(r"<meta name=['\"]viewport['\"] content=['\"][^'\"]*['\"]>", '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">', html)
    if "rel='manifest'" not in html:
        html = html.replace('<title>', '<meta name="theme-color" content="#0c1422"><link rel="manifest" href="/manifest.webmanifest"><meta name="apple-mobile-web-app-capable" content="yes"><title>', 1)
    nav = '<nav class="tabs" aria-label="主导航">'
    for path, label in [('/', '训练'), ('/devices', '设备'), ('/history', '记录')]:
        active = ' aria-current="page"' if path == current else ''
        nav += f'<a href="{path}"{active}><svg viewBox="0 0 24 24" aria-hidden="true">{ICONS[path]}</svg>{label}</a>'
    nav += '</nav>'
    html = html.replace('<script>', nav + '<script>', 1)
    html = re.sub(r'<article><label>控制令牌.*?</article>', '<details class="auth"><summary>本机访问凭证</summary><label>控制令牌<input id="token" type="password" autocomplete="off" placeholder="CYCLING_TOKEN"></label><p class="muted">仅在当前标签页会话内保留。</p></details>', html, count=1, flags=re.S)
    html = html.replace("</script>", "if(!document.getElementById('token').value)document.querySelector('.auth').open=true;if('serviceWorker' in navigator)navigator.serviceWorker.register('/sw.js').catch(()=>{});</script>")
    return html

HISTORY = """<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>训练记录 · Indoor Cycling</title><style></style><main class="wrap"><div class="eyebrow">INDOOR CYCLING</div><h1>训练记录</h1><p class="muted">最近 50 次本机模拟训练。连接手表时，心率可来自真实设备。</p><article><label>控制令牌<input id="token" type="password" placeholder="CYCLING_TOKEN"></label></article><div id="records"></div><p id="error" role="alert"></p></main><script>
const token=document.getElementById('token');token.value=sessionStorage.getItem('cyclingToken')||'';token.addEventListener('input',()=>{sessionStorage.setItem('cyclingToken',token.value);load();});
async function load(){if(!token.value)return;try{const r=await fetch('/api/history',{headers:{'X-Cycling-Token':token.value}});if(!r.ok)throw Error('无法读取记录 ('+r.status+')');const rows=await r.json();const box=document.getElementById('records');box.replaceChildren();if(!rows.length){const a=document.createElement('article');a.textContent='还没有训练记录。开始并结束一次模拟训练后，会保存在这里。';box.append(a);}for(const row of rows){const a=document.createElement('article');const h=document.createElement('h2');h.textContent=new Date(row.started_at).toLocaleString('zh-CN');const p=document.createElement('p');p.textContent=row.ended_at?'已结束 · '+Math.floor(row.duration_s/60)+' 分 '+Math.floor(row.duration_s%60)+' 秒':'未结束 · 服务重启后不会恢复';const small=document.createElement('small');small.textContent='模拟训练 · '+(row.has_ble?'包含真实蓝牙心率':'模拟心率');a.append(h,p,small);box.append(a);}document.getElementById('error').textContent='';}catch(e){document.getElementById('error').textContent=e.message;}}
load();setInterval(load,10000);
</script></html>"""
