"""Web 入口:零依赖 http.server,单页 + JSON API。"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from . import agent, llm
from . import db as dbmod

PAGE = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>育儿 · 生长与喂养参考</title>
<style>
  :root{--bg:#f7f9fb;--card:#fff;--ink:#26313d;--muted:#6f7c8a;--accent:#2f6f8f;--soft:#e2eff5;
        --line:#e4ebf1;--red:#b42318;--green:#067647;--amber:#b54708;--radius:16px}
  *{box-sizing:border-box}
  body{margin:0;font-family:system-ui,-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;background:var(--bg);color:var(--ink)}
  .wrap{max-width:960px;margin:0 auto;padding:32px 20px 80px}
  h1{font-size:26px;margin:0 0 4px} header p{color:var(--muted);margin:0 0 22px}
  .badge{display:inline-block;font-size:12px;padding:3px 10px;border-radius:999px;background:var(--soft);color:var(--accent);margin-left:8px}
  .card{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:20px;margin-bottom:18px;box-shadow:0 1px 2px rgba(38,49,61,.04)}
  label{display:block;font-size:13px;color:var(--muted);margin:0 0 6px}
  textarea,input{width:100%;padding:12px 14px;border:1px solid var(--line);border-radius:12px;font-size:14px;font-family:inherit;background:#fff}
  textarea{line-height:1.7}
  textarea:focus,input:focus{outline:none;border-color:var(--accent);box-shadow:0 0 0 3px var(--soft)}
  .row{display:flex;gap:12px;flex-wrap:wrap}.row>div{flex:1;min-width:160px}
  button{background:var(--accent);color:#fff;border:none;padding:12px 22px;border-radius:12px;font-size:15px;cursor:pointer}
  button:hover{filter:brightness(1.08)}
  .hint{color:var(--muted);font-size:12px;margin-top:8px}
  .spin{display:inline-block;width:16px;height:16px;border:2px solid #fff;border-top-color:transparent;border-radius:50%;animation:sp .7s linear infinite}
  @keyframes sp{to{transform:rotate(360deg)}}
  .result{display:none}.result.show{display:block}
  h3{font-size:15px;color:var(--muted);margin:20px 0 8px}
  table{width:100%;border-collapse:collapse;font-size:13px}
  th,td{text-align:left;padding:8px;border-bottom:1px solid var(--line)}
  th{color:var(--muted);font-weight:600}
  .bad{color:var(--red)}.ok{color:var(--green)}.warn{color:var(--amber)}
  .box{background:#fafcfd;border-radius:10px;padding:12px 14px;margin:8px 0;font-size:14px;line-height:1.8}
  .item{border-left:3px solid var(--accent);padding:4px 0 4px 12px;margin:8px 0;font-size:14px}
  ul{margin:6px 0 0 18px;padding:0}li{margin:6px 0;font-size:14px}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>育儿 · 生长与喂养参考<span class="badge" id="badge">…</span></h1>
    <p>给性别、月龄和测量值:看百分位落点、下一针疫苗、当月喂养方式,红旗症状直接标出来。</p>
  </header>
  <div class="card">
    <label>宝宝情况</label>
    <textarea id="text" rows="5" placeholder="男孩,8个月,体重9kg,身高70cm,头围45cm,最近有点发烧"></textarea>
    <div style="margin-top:16px"><button id="btn">开始评估</button></div>
    <div class="hint">本工具不做诊断。百分位为参考带,异常只提示面诊,不给用药建议。</div>
  </div>
  <div class="result" id="res"></div>
</div>
<script>
const $=s=>document.querySelector(s);
function esc(s){return String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
function load(btn,on){btn.disabled=on;if(on){btn.dataset.label=btn.dataset.label||btn.textContent.trim();btn.innerHTML='<span class="spin"></span>';}else{btn.innerHTML=btn.dataset.label||btn.textContent;}}
$('#btn').onclick=async()=>{
  const el=$('#res');el.classList.remove('show');load($('#btn'),true);
  try{
    const p=await fetch('/api/check',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({text:$('#text').value})});
    const r=await p.json(); if(r.error) throw new Error(r.error);
    let h='<div class="card"><div class="hint">'+(r.mode==='model'?'模型已连接':'离线模式')+(r.saved_id?' · 已入库 #'+r.saved_id:'')+'</div>';
    h+='<p style="font-size:16px;line-height:1.7">'+esc(r.verdict)+'</p>';
    if(r.growth.length){h+='<h3>生长分档</h3><table><tr><th>指标</th><th>本次</th><th>P15–P85 参考</th><th>落点</th></tr>';
      r.growth.forEach(g=>{const bad=g.bucket.indexOf('P3')>=0||g.bucket.indexOf('P97')>=0;
        h+='<tr><td>'+esc(g.metric)+'</td><td>'+g.value+'</td><td>'+g.band.P15+'–'+g.band.P85+'</td><td class="'+(bad?'bad':'ok')+'">'+esc(g.bucket)+'</td></tr>';});
      h+='</table>';}
    h+='<h3>接种</h3>';
    r.vaccines.due.forEach(v=>{h+='<div class="ok">✅ '+esc(v.name)+'</div>';});
    r.vaccines.next.forEach(v=>{h+='<div>⏭ '+v.age_months+' 月龄:'+esc(v.name)+'</div>';});
    h+='<div class="hint">'+esc(r.vaccines.note)+'</div>';
    if(r.feeding){h+='<h3>喂养('+esc(r.feeding.range)+')</h3><div class="box">'+esc(r.feeding.detail)+'</div>';}
    h+='<h3>红线</h3>';
    if(r.red_flags.length){r.red_flags.forEach(f=>{h+='<div class="item bad"><b>'+esc(f.name)+'</b><div class="hint">'+esc(f.why)+'</div></div>';});}
    else{h+='<div class="hint">未命中。出现抽搐、呼吸急促、3 月龄以下发热、精神差,立即就医。</div>';}
    if(r.summary){h+='<h3>评估</h3><p>'+esc(r.summary)+'</p>';}
    if(r.care_tips.length){h+='<h3>照护建议</h3><ul>';r.care_tips.forEach(x=>h+='<li>'+esc(x)+'</li>');h+='</ul>';}
    if(r.risks.length){h+='<h3>注意</h3><ul>';r.risks.forEach(x=>h+='<li class="warn">'+esc(x)+'</li>');h+='</ul>';}
    h+='<h3>问诊前准备</h3>';
    r.questions.forEach(q=>{h+='<div class="'+(q.ok?'ok':'warn')+'">'+(q.ok?'✅':'❌')+' '+esc(q.item)+' —— '+esc(q.question)+'</div>';});
    h+='</div>'; el.innerHTML=h;
  }catch(e){el.innerHTML='<div class="card" style="color:#b42318">请求失败:'+esc(e.message)+'</div>';}
  el.classList.add('show');load($('#btn'),false);
};
fetch('/api/status').then(r=>r.json()).then(s=>{const b=$('#badge');
  if(s.mock){b.textContent='离线模式';b.style.background='#fee2e2';b.style.color='#b42318';}
  else{b.textContent=s.model||'模型已连接';b.style.background='#dcfce7';b.style.color='#067647';}
}).catch(()=>{});
</script>
</body></html>
"""


def _handler(db, cfg, force_mock):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, body, ctype, status=200):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, status=200):
            self._send(json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                       "application/json; charset=utf-8", status)

        def _read(self):
            raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                text = raw.decode("gbk", errors="replace")
            return json.loads(text) if text else {}

        def do_GET(self):
            path = urlparse(self.path).path
            if path in ("/", "/index.html"):
                self._send(PAGE.encode("utf-8"), "text/html; charset=utf-8")
            elif path == "/api/status":
                mock = force_mock or not cfg.get("api_key")
                self._json({"mock": mock, "model": None if mock else cfg.get("model")})
            else:
                self._json({"error": "not found"}, 404)

        def do_POST(self):
            if urlparse(self.path).path != "/api/check":
                self._json({"error": "not found"}, 404)
                return
            try:
                body = self._read()
                r = agent.check(body.get("text", ""), config=cfg, db=db,
                                force_mock=force_mock, save=True)
                self._json(r)
            except llm.LLMError as e:
                self._json({"error": str(e)}, 400)
            except Exception as e:  # noqa: BLE001
                self._json({"error": str(e)}, 500)

        def log_message(self, *args):
            pass

    return Handler


def serve(host="127.0.0.1", port=8000, db_path=None, force_mock=False):
    db = dbmod.Database(db_path)
    cfg = llm.default_config()
    httpd = ThreadingHTTPServer((host, port), _handler(db, cfg, force_mock))
    mode = "离线模式(未配置 key)" if (force_mock or not cfg.get("api_key")) else "模型:%s" % cfg.get("model")
    print("👶 育儿已启动:http://%s:%s  [%s]" % (host, port, mode))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
