"""Live tactical HTTP UI/API for the laptop RF field application."""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from app.config import default_config
from app.investigations import InvestigationStore
from app.storage import ObservationStore


HTML = r'''<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>RF Finder — Field Monitor</title>
<link href="https://unpkg.com/maplibre-gl@5.9.0/dist/maplibre-gl.css" rel="stylesheet">
<style>
*{box-sizing:border-box}body{margin:0;background:#071019;color:#d8f4ff;font:13px Arial,sans-serif}header{padding:10px 14px;border-bottom:1px solid #24465d;display:flex;gap:16px;align-items:center;flex-wrap:wrap}header b{color:#62d8ff;font-size:16px}.pill{padding:5px 8px;border:1px solid #24465d;border-radius:5px}.grid{display:grid;grid-template-columns:1fr 360px;min-height:calc(100vh - 52px)}#map{min-height:620px}.side{padding:10px;overflow:auto}.panel{border:1px solid #24465d;border-radius:6px;padding:10px;margin-bottom:10px;background:#0b1823}.panel h3{margin:0 0 8px;color:#62d8ff}.stats{display:grid;grid-template-columns:1fr 1fr;gap:6px}.stat{padding:7px;background:#071019;border:1px solid #19394c}.stat small{display:block;color:#7ea0b4}.stat b{font-size:15px}.signal{padding:7px;border-top:1px solid #19394c}.signal:first-child{border-top:0}.warn{color:#ffd166}.btn{background:#102a3b;color:#d8f4ff;border:1px solid #2c607d;padding:6px 9px;border-radius:4px;cursor:pointer}.btn:hover{background:#163b51}canvas{width:100%;height:180px;background:#03090e;border:1px solid #19394c}.marker{width:14px;height:14px;border-radius:50%;border:2px solid white;box-shadow:0 0 12px currentColor}
</style></head><body>
<header><b>RF FINDER / FIELD</b><span class="pill" id="run">STARTING</span><span class="pill" id="source">source: —</span><span class="pill" id="freq">center: —</span><button class="btn" onclick="toggleScan()">Start / Stop</button></header>
<div class="grid"><div id="map"></div><aside class="side">
<div class="panel"><h3>Live Spectrum</h3><canvas id="spectrum" width="700" height="180"></canvas></div>
<div class="panel"><h3>Waterfall</h3><canvas id="waterfall" width="700" height="180"></canvas></div>
<div class="panel"><h3>Field Status</h3><div class="stats"><div class="stat"><small>Frames</small><b id="frames">0</b></div><div class="stat"><small>GPS</small><b id="gps">not configured</b></div><div class="stat"><small>FFT</small><b id="fft">—</b></div><div class="stat"><small>Last scan</small><b id="last">—</b></div></div></div>
<div class="panel"><h3>Recent Signals</h3><div id="signals">Loading…</div></div>
<div class="panel"><h3>Investigations</h3><button class="btn" onclick="newInvestigation()">New investigation</button><div id="investigations"></div></div>
<div class="panel warn">Passive RF monitoring. A measured RF signal is evidence for investigation, not proof of surveillance, intent, identity, or illegality.</div>
</aside></div>
<script src="https://unpkg.com/maplibre-gl@5.9.0/dist/maplibre-gl.js"></script><script>
const map=new maplibregl.Map({container:'map',center:[-117.16,32.72],zoom:11,style:{version:8,sources:{osm:{type:'raster',tiles:['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],tileSize:256,attribution:'© OpenStreetMap contributors'}},layers:[{id:'osm',type:'raster',source:'osm'}]}});map.addControl(new maplibregl.NavigationControl(),'top-right');let markers=[];
const $=id=>document.getElementById(id);const fmtHz=h=>h>=1e9?(h/1e9).toFixed(3)+' GHz':(h/1e6).toFixed(3)+' MHz';
async function api(path,opts){const r=await fetch(path,opts);return r.json()}
function drawSpectrum(s){const c=$('spectrum'),x=c.getContext('2d');x.clearRect(0,0,c.width,c.height);if(!s.power_db?.length)return;x.beginPath();const min=Math.min(...s.power_db),max=Math.max(...s.power_db);s.power_db.forEach((v,i)=>{const px=i*(c.width-1)/(s.power_db.length-1),py=c.height-8-(v-min)/Math.max(1,max-min)*(c.height-16);i?x.lineTo(px,py):x.moveTo(px,py)});x.strokeStyle='#62d8ff';x.stroke();}
function drawWaterfall(w){const c=$('waterfall'),x=c.getContext('2d');x.clearRect(0,0,c.width,c.height);const fs=w.frames||[];if(!fs.length)return;const rows=Math.min(fs.length,c.height),start=fs.length-rows;for(let r=0;r<rows;r++){const row=fs[start+r],min=Math.min(...row),max=Math.max(...row);for(let i=0;i<row.length;i++){const v=(row[i]-min)/Math.max(1,max-min);const g=Math.floor(255*v);x.fillStyle=`rgb(${g},${Math.floor(100+120*v)},${255-g})`;x.fillRect(i*c.width/row.length,c.height-1-r,c.width/row.length+1,1)}}}
async function refresh(){try{const [s,w,o,iv]=await Promise.all([api('/api/spectrum'),api('/api/waterfall'),api('/api/observations?limit=30'),api('/api/investigations')]);drawSpectrum(s);drawWaterfall(w);$('signals').innerHTML=o.slice().reverse().map(q=>`<div class="signal"><b>${q.signal_class}</b> — ${fmtHz(q.frequency_hz)}<br>SNR ${q.snr_db.toFixed(1)} dB · BW ${(q.bandwidth_hz/1000).toFixed(1)} kHz · ${q.source}</div>`).join('')||'No detections yet';$('investigations').innerHTML=iv.map(i=>`<div class="signal"><b>${i.title}</b><br>${i.status} · ${i.created_at.slice(0,19)}Z</div>`).join('')||'No investigations';}catch(e){console.log(e)}}
async function status(){const s=await api('/api/status');$('run').textContent=s.running?'RUNNING':'STOPPED';$('source').textContent='source: '+s.source;$('freq').textContent='center: '+fmtHz(s.center_frequency_hz);$('frames').textContent=s.frame_index;$('fft').textContent=s.fft_size;$('last').textContent=s.last_scan_at?s.last_scan_at.slice(11,19):'—';const g=s.gps;$('gps').textContent=g.latitude!=null?`${g.latitude.toFixed(4)}, ${g.longitude.toFixed(4)}`:'not configured';}
async function toggleScan(){const s=await api('/api/status');await api(s.running?'/api/stop':'/api/start',{method:'POST'});status()}
async function newInvestigation(){const title=prompt('Investigation title:');if(title)await api('/api/investigations',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title})});refresh()}
setInterval(()=>{status();refresh()},1000);status();refresh();
</script></body></html>'''


def create_server(service, host="127.0.0.1", port=8000):
    investigation_store = InvestigationStore(service.config.database_path)

    class Handler(BaseHTTPRequestHandler):
        def _send(self, payload, status=200, content_type="application/json"):
            body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
            self.send_response(status); self.send_header("Content-Type", content_type); self.send_header("Cache-Control", "no-store"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

        def do_GET(self):
            path = urlparse(self.path).path
            if path in ("/", "/tactical"):
                return self._send(HTML.encode(), content_type="text/html; charset=utf-8")
            if path == "/api/status": return self._send(service.status())
            if path == "/api/spectrum": return self._send(service.latest_spectrum())
            if path == "/api/waterfall": return self._send(service.waterfall())
            if path == "/api/observations":
                q=parse_qs(urlparse(self.path).query); limit=int(q.get("limit",[250])[0]); return self._send(service.observations(limit))
            if path == "/api/investigations": return self._send(investigation_store.list())
            self._send({"error":"not found"},404)

        def do_POST(self):
            path=urlparse(self.path).path
            if path == "/api/start": service.start(); return self._send(service.status())
            if path == "/api/stop": service.stop(); return self._send(service.status())
            if path == "/api/investigations":
                try: data=json.loads(self.rfile.read(int(self.headers.get("Content-Length","0"))))
                except (ValueError, json.JSONDecodeError): data={}
                return self._send(investigation_store.create(data.get("title","RF investigation"),data.get("notes","")),201)
            self._send({"error":"not found"},404)

        def log_message(self, fmt, *args): pass

    return ThreadingHTTPServer((host, port), Handler)


if __name__ == "__main__":
    from app.field_service import RFService
    host=os.getenv("RF_FINDER_HOST","127.0.0.1");port=int(os.getenv("RF_FINDER_PORT","8080"));service=RFService();service.start();print(f"RF Finder tactical view: http://{host}:{port}/tactical")
    server=create_server(service,host,port)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: service.stop();server.server_close()
