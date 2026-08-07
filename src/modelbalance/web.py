"""本地 Web 仪表盘（纯标准库实现）。

运行：python run.py web
浏览器打开 http://127.0.0.1:8000，页面每 N 秒自动刷新余额、用量与图表。
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from .config import load_accounts
from .fetcher import fetch_all
from .storage import (
    add_snapshot,
    list_usage_records,
    usage_breakdown,
    usage_daily,
    usage_totals,
)
from .proxy import ensure_proxy

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>模型余额仪表盘</title>
<style>
body{font-family:system-ui,sans-serif;margin:24px;background:#0f172a;color:#e2e8f0}
h1{font-size:20px}h2{font-size:16px;margin-top:28px}
table{border-collapse:collapse;width:100%;margin-top:12px}
th,td{border:1px solid #334155;padding:8px 12px;text-align:left;font-size:14px}
th{background:#1e293b}.err{color:#f87171}.ok{color:#4ade80}#meta{color:#94a3b8;font-size:13px}
.note{color:#94a3b8;font-size:13px;margin:6px 0 0}
.charts{display:flex;gap:12px;flex-wrap:wrap;margin-top:12px}
.charts>div{background:#0f172a;border:1px solid #334155;border-radius:6px;padding:8px}
.charts p{margin:0 0 6px;font-size:13px;color:#94a3b8}
</style>
</head>
<body>
<h1>模型 API 余额仪表盘</h1>
<p id="meta">加载中…</p>
<h2>余额（实时查询）</h2>
<table id="bal">
<thead><tr><th>账户</th><th>提供商</th><th>币种</th><th>可用金额</th><th>已用金额</th><th>总额</th><th>状态</th></tr></thead>
<tbody></tbody>
</table>
<h2>用量统计</h2>
<div class="charts">
  <div><p>每日消费金额（近 14 天，悬停柱子看数值）</p><canvas id="costChart" width="560" height="250"></canvas></div>
  <div><p>每日 Token 用量（近 14 天，悬停柱子看数值）</p><canvas id="tokenChart" width="560" height="250"></canvas></div>
  <div><p>Token 构成（近 30 天）</p><canvas id="pieChart" width="360" height="250"></canvas></div>
</div>
<p class="note">注：Token 用量为本地手动记录（add-usage 录入），非官方接口数据，与官网可能不一致。</p>
<h2>用量明细（近 30 天）</h2>
<p id="usage-total" class="note">-</p>
<table id="usage">
<thead><tr><th>时间</th><th>账户</th><th>模型</th><th>Token</th><th>费用</th></tr></thead>
<tbody></tbody>
</table>
<script>
const REFRESH = __INTERVAL__;
const CHART = {bg:'#0f172a', grid:'#475569', text:'#f8fafc', day:'#94a3b8'};
const barMeta = {};
function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
function money(v){return v == null ? '-' : Number(v).toFixed(4);}
function drawBars(canvasId, items, valueKey, fmt, color){
  const cv = document.getElementById(canvasId);
  const ctx = cv.getContext('2d');
  const w = cv.width, h = cv.height;
  ctx.clearRect(0,0,w,h);
  ctx.fillStyle = CHART.bg; ctx.fillRect(0,0,w,h);
  const ml=64, mr=10, mt=20, mb=34;
  const pw=w-ml-mr, ph=h-mt-mb;
  const maxV = Math.max(1, ...items.map(d=>d[valueKey]||0));
  const n = items.length, slot = pw/Math.max(1,n);
  const barW = Math.min(slot*0.62, 38);
  ctx.textAlign='center'; ctx.font='13px sans-serif';
  items.forEach((d,i)=>{
    const v=d[valueKey]||0, bh=ph*v/maxV;
    const x0=ml+i*slot+(slot-barW)/2, y0=mt+ph-bh;
    ctx.fillStyle=color; ctx.fillRect(x0,y0,barW,bh);
    ctx.fillStyle=CHART.text;
    if(bh>18) ctx.fillText(fmt(v), x0+barW/2, y0-6);
    if(i%2===0){ ctx.fillStyle=CHART.day; ctx.fillText(d.day.slice(5), x0+barW/2, mt+ph+16); }
  });
  ctx.strokeStyle=CHART.grid; ctx.setLineDash([2,2]);
  for(let g=0;g<=4;g++){
    const gy=mt+ph-ph*g/4;
    ctx.beginPath(); ctx.moveTo(ml,gy); ctx.lineTo(ml+pw,gy); ctx.stroke();
    ctx.textAlign='right'; ctx.fillStyle=CHART.text;
    ctx.fillText(fmt(maxV*g/4), ml-5, gy+4);
  }
  ctx.setLineDash([]);
  barMeta[canvasId] = {items, valueKey, fmt, color, ml, mt, pw, ph, slot, n, w, h};
  cv.onmousemove = (e)=>onBarHover(canvasId, e);
  cv.onmouseleave = ()=>onBarLeave(canvasId);
}
function onBarHover(canvasId, e){
  const m = barMeta[canvasId]; if(!m) return;
  const rect = e.target.getBoundingClientRect();
  const x = e.clientX - rect.left, y = e.clientY - rect.top;
  if(x < m.ml || x > m.ml+m.pw || y < m.mt || y > m.mt+m.ph){ onBarLeave(canvasId); return; }
  const idx = Math.min(Math.floor((x-m.ml)/m.slot), m.n-1);
  if(idx < 0) return;
  drawBars(canvasId, m.items, m.valueKey, m.fmt, m.color);
  const cv = document.getElementById(canvasId);
  const ctx = cv.getContext('2d');
  const d = m.items[idx];
  const barW = Math.min(m.slot*0.62, 38);
  const bx = m.ml+idx*m.slot+(m.slot-barW)/2;
  const maxV = Math.max(1, ...m.items.map(dd=>dd[m.valueKey]||0));
  const bh = (m.ph*(d[m.valueKey]||0))/maxV;
  const by = m.mt+m.ph-bh;
  ctx.strokeStyle = '#ffffff'; ctx.lineWidth = 2;
  ctx.strokeRect(bx,by,barW,bh);
  const tip = (m.valueKey==='cost') ? d.day+' 消费 ¥'+Number(d.cost).toFixed(2) : d.day+' Token '+Number(d.tokens).toLocaleString();
  const tx = Math.min(x+14, cv.width-236), ty = Math.max(y-36, 10);
  ctx.fillStyle = '#0b1220'; ctx.strokeStyle = '#64748b'; ctx.lineWidth = 1;
  ctx.fillRect(tx,ty,226,28); ctx.strokeRect(tx,ty,226,28);
  ctx.fillStyle = '#ffffff'; ctx.textAlign = 'left'; ctx.font = '13px sans-serif';
  ctx.fillText(tip, tx+8, ty+19);
}
function onBarLeave(canvasId){
  const m = barMeta[canvasId]; if(!m) return;
  drawBars(canvasId, m.items, m.valueKey, m.fmt, m.color);
}
function drawPie(canvasId, bd){
  const cv = document.getElementById(canvasId);
  const ctx = cv.getContext('2d');
  const w = cv.width, h = cv.height;
  ctx.clearRect(0,0,w,h);
  ctx.fillStyle = CHART.bg; ctx.fillRect(0,0,w,h);
  const items=[['输入(命中缓存)',bd.cache_hit,'#4ade80'],['输入(未命中缓存)',bd.cache_miss,'#60a5fa'],['输出',bd.output,'#fb923c']];
  const total=items.reduce((s,x)=>s+x[1],0)||1;
  const cx=w*0.28, cy=h*0.5, r=Math.min(w,h)*0.36;
  let start=Math.PI/2;
  items.forEach(([label,v,color])=>{
    if(v<=0) return;
    const ang=2*Math.PI*v/total;
    ctx.beginPath(); ctx.moveTo(cx,cy); ctx.arc(cx,cy,r,start,start-ang); ctx.closePath();
    ctx.fillStyle=color; ctx.fill();
    start-=ang;
  });
  let ly=h*0.16;
  const lx=w*0.58;
  ctx.font='13px sans-serif'; ctx.textAlign='left';
  items.forEach(([label,v,color])=>{
    const pct=100*v/total;
    ctx.fillStyle=color; ctx.fillRect(lx,ly+2,14,14);
    ctx.fillStyle=CHART.text;
    ctx.fillText(label+' '+pct.toFixed(1)+'%', lx+20, ly+14);
    ly+=28;
  });
}
async function refresh(){
  try{
    const b = await (await fetch('/api/balances')).json();
    document.getElementById('meta').textContent = '最后刷新：' + new Date().toLocaleString();
    const tb = document.querySelector('#bal tbody');
    tb.innerHTML = '';
    b.items.forEach(it => {
      const tr = document.createElement('tr');
      if (it.error){
        tr.innerHTML = `<td>${esc(it.account)}</td><td>${esc(it.provider)}</td><td colspan="4"></td><td class="err">${esc(it.error)}</td>`;
      } else {
        tr.innerHTML = `<td>${esc(it.account)}</td><td>${esc(it.provider)}</td><td>${esc(it.currency)}</td><td>${money(it.available)}</td><td>${money(it.used)}</td><td>${money(it.total)}</td><td class="ok">OK</td>`;
      }
      tb.appendChild(tr);
    });
    const u = await (await fetch('/api/usage')).json();
    const daily = u.daily.slice(-14);
    drawBars('costChart', daily, 'cost', v=>'¥'+Number(v).toFixed(2), '#f87171');
    drawBars('tokenChart', daily, 'tokens', v=>Number(v).toLocaleString(), '#4ade80');
    drawPie('pieChart', u.breakdown);
    const tu = document.querySelector('#usage tbody');
    tu.innerHTML = '';
    u.records.forEach(r => {
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${esc(r.created_at)}</td><td>${esc(r.account)}</td><td>${esc(r.model)}</td><td>${r.total_tokens}</td><td>${money(r.cost)}</td>`;
      tu.appendChild(tr);
    });
    if (u.totals){
      document.getElementById('usage-total').textContent =
        `共 ${u.totals.records} 条记录 / ${u.totals.total_tokens} tokens / 费用 ${Number(u.totals.cost).toFixed(4)}`;
    }
  } catch(e){
    document.getElementById('meta').textContent = '刷新失败：' + e;
  }
}
refresh();
setInterval(refresh, REFRESH * 1000);
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    interval = 30
    save_snapshots = False

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            self._send(PAGE_TEMPLATE.replace("__INTERVAL__", str(self.interval)), "text/html; charset=utf-8")
        elif path == "/api/balances":
            self._send(json.dumps(self._balances(), ensure_ascii=False), "application/json; charset=utf-8")
        elif path == "/api/usage":
            self._send(json.dumps(self._usage(), ensure_ascii=False), "application/json; charset=utf-8")
        else:
            self.send_error(404)

    def _balances(self) -> dict:
        items = []
        for r in fetch_all(load_accounts()):
            if r.ok:
                b = r.balance
                items.append(
                    {
                        "account": b.account,
                        "provider": b.provider,
                        "currency": b.currency,
                        "available": b.available,
                        "used": b.used,
                        "total": b.total,
                        "fetched_at": b.fetched_at.isoformat(timespec="seconds"),
                        "error": None,
                    }
                )
                if self.save_snapshots:
                    add_snapshot(b)
            else:
                items.append(
                    {
                        "account": r.account.name,
                        "provider": r.account.provider,
                        "error": r.error,
                    }
                )
        return {"items": items, "interval": self.interval}

    def _usage(self) -> dict:
        since = datetime.now() - timedelta(days=30)
        return {
            "totals": usage_totals(since=since),
            "records": list_usage_records(since=since)[:50],
            "daily": usage_daily(days=30),
            "breakdown": usage_breakdown(since=since),
        }

    def _send(self, body: str, content_type: str):
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):  # 静默访问日志，避免刷屏
        pass


def serve(host: str = "127.0.0.1", port: int = 8000, interval: int = 30, save: bool = False) -> int:
    Handler.interval = interval
    Handler.save_snapshots = save
    ensure_proxy(port=8001)
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"仪表盘已启动: http://{host}:{port}（每 {interval} 秒自动刷新，Ctrl+C 退出）")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
    finally:
        server.server_close()
    return 0