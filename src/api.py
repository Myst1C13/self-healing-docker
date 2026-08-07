from contextlib import asynccontextmanager

import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from src import collector, pipeline, recovery, storage
from src.config import SERVICES, SERVICE_PORTS


@asynccontextmanager
async def lifespan(app):
    # kick off the polling loop when the server boots
    pipeline.start_background()
    yield
    pipeline.stop()


app = FastAPI(title="self-healing-docker", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/status")
def status():
    services = []
    for name in SERVICES:
        window = collector.get_window(name)
        latest = window[-1] if window else None
        services.append({
            "service": name,
            "port": SERVICE_PORTS[name],
            "latest": latest,
            "restart_count": recovery.restart_count(name),
            "samples": len(window),
        })
    return {"services": services, "last_tick": pipeline.last_tick(), "stats": storage.stats()}


@app.get("/incidents")
def incidents(service=None, limit=100):
    return {"incidents": storage.get_incidents(service=service, limit=limit)}


@app.post("/chaos/{service}")
def chaos(service):
    # just forward the chaos call to the target service so the demo is one click
    if service not in SERVICE_PORTS:
        raise HTTPException(404, "unknown service " + service)
    port = SERVICE_PORTS[service]
    try:
        r = requests.post("http://localhost:" + str(port) + "/chaos", timeout=3)
        return r.json()
    except requests.RequestException as e:
        raise HTTPException(502, "could not reach " + service + ": " + str(e))


@app.get("/", response_class=HTMLResponse)
def dashboard():
    return """<!doctype html>
<html>
<head>
  <title>self-healing-docker</title>
  <meta charset="utf-8">
  <style>
    body { font-family: ui-monospace, Menlo, monospace; background:#0d1117; color:#c9d1d9; margin:0; padding:24px; }
    h1 { font-size:18px; } h2 { font-size:14px; color:#8b949e; margin-top:28px; }
    table { border-collapse:collapse; width:100%; font-size:13px; }
    th,td { text-align:left; padding:6px 10px; border-bottom:1px solid #21262d; }
    .crit { color:#f85149; } .ok { color:#3fb950; } .btn { cursor:pointer; background:#21262d; border:1px solid #30363d; color:#c9d1d9; padding:4px 10px; border-radius:6px; }
    .pill { padding:1px 8px; border-radius:10px; background:#21262d; font-size:11px; }
  </style>
</head>
<body>
  <h1>self-healing-docker <span class="pill" id="tick"></span></h1>
  <h2>SERVICES</h2><table id="svc"></table>
  <h2>INCIDENTS</h2><table id="inc"></table>
  <script>
    async function chaos(s){ await fetch('/chaos/'+s,{method:'POST'}); }
    async function refresh(){
      const st = await (await fetch('/status')).json();
      document.getElementById('tick').textContent =
        'incidents: '+st.stats.total_incidents+' / recovered: '+st.stats.recovered;
      let sv = '<tr><th>service</th><th>cpu%</th><th>mem%</th><th>latency</th><th>err</th><th>restarts</th><th></th></tr>';
      for(const s of st.services){ const m=s.latest||{};
        const hot = (m.cpu_percent>85||m.memory_percent>90||m.latency_ms>500);
        sv += `<tr class="${hot?'crit':'ok'}"><td>${s.service}</td><td>${m.cpu_percent??'-'}</td>`+
          `<td>${m.memory_percent??'-'}</td><td>${m.latency_ms??'-'}</td><td>${m.error_rate??'-'}</td>`+
          `<td>${s.restart_count}</td><td><button class="btn" onclick="chaos('${s.service}')">chaos</button></td></tr>`;
      }
      document.getElementById('svc').innerHTML = sv;
      const inc = await (await fetch('/incidents?limit=20')).json();
      let ir = '<tr><th>time</th><th>service</th><th>type</th><th>reason</th><th>status</th></tr>';
      for(const i of inc.incidents){
        ir += `<tr><td>${i.timestamp.slice(11,19)}</td><td>${i.service}</td><td class="crit">${i.incident_type}</td>`+
          `<td>${i.reason}</td><td>${i.recovery_status}</td></tr>`;
      }
      document.getElementById('inc').innerHTML = ir;
    }
    refresh(); setInterval(refresh, 3000);
  </script>
</body>
</html>"""
