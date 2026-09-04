"""Minimal dependency-free tactical map server for RF Finder.

Run with: python -m app.tactical_server
Then open http://127.0.0.1:8080/tactical
"""

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from app.config import default_config
from app.storage import ObservationStore


HTML = r'''<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>RF Finder — Tactical View</title>
<link href="https://unpkg.com/maplibre-gl@5.9.0/dist/maplibre-gl.css" rel="stylesheet">
<style>
html,body,#map{margin:0;width:100%;height:100%;background:#071019;font-family:Arial,sans-serif}
#hud{position:absolute;z-index:2;top:12px;left:12px;right:12px;display:flex;gap:10px;flex-wrap:wrap;pointer-events:none}
.card{background:rgba(7,16,25,.88);border:1px solid #24465d;color:#d8f4ff;padding:9px 12px;border-radius:6px;box-shadow:0 4px 16px #0008;font-size:13px}
.card b{color:#62d8ff}.warn{color:#ffd166}.drone{color:#ff7b72}
.marker{width:15px;height:15px;border-radius:50%;border:2px solid white;box-shadow:0 0 12px currentColor;cursor:pointer}
</style></head><body><div id="map"></div><div id="hud">
<div class="card"><b>RF FINDER / TACTICAL</b></div><div class="card" id="status">Loading observations…</div>
<div class="card warn">Passive RF only • labels are evidence, not proof of intent or legality</div></div>
<script src="https://unpkg.com/maplibre-gl@5.9.0/dist/maplibre-gl.js"></script>
<script>
const map = new maplibregl.Map({container:'map',center:[-117.16,32.72],zoom:11,
style:{version:8,sources:{osm:{type:'raster',tiles:['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],tileSize:256,attribution:'© OpenStreetMap contributors'}},layers:[{id:'osm',type:'raster',source:'osm'}]}});
map.addControl(new maplibregl.NavigationControl(),'top-right');
const markers=[];
function color(o){return o.signal_class==='possible_drone_remote_id'?'#ff7b72':o.snr_db>=20?'#ffd166':'#62d8ff'}
function freq(h){return h>=1e9?(h/1e9).toFixed(3)+' GHz':(h/1e6).toFixed(3)+' MHz'}
async function refresh(){try{const r=await fetch('/api/observations?limit=500');const data=await r.json();markers.splice(0).forEach(x=>x.remove());
 data.forEach(o=>{if(o.latitude==null||o.longitude==null)return;const el=document.createElement('div');el.className='marker';el.style.color=color(o);el.style.background=color(o);
 const popup=new maplibregl.Popup({offset:12}).setHTML(`<b>${o.signal_class}</b><br>Frequency: ${freq(o.frequency_hz)}<br>SNR: ${o.snr_db.toFixed(1)} dB<br>Power: ${o.peak_power_db.toFixed(1)} dB<br>BW: ${(o.bandwidth_hz/1000).toFixed(1)} kHz<br>Confidence: ${(o.confidence*100).toFixed(0)}%<br>Source: ${o.source}`);
 markers.push(new maplibregl.Marker({element:el}).setLngLat([o.longitude,o.latitude]).setPopup(popup).addTo(map));});
 document.getElementById('status').textContent=`${data.length} observations • ${data.filter(x=>x.signal_class==='possible_drone_remote_id').length} possible Remote ID`;}
 catch(e){document.getElementById('status').textContent='API unavailable'}}
map.on('load',()=>{refresh();setInterval(refresh,3000)});
</script></body></html>'''


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/tactical":
            body = HTML.encode()
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body); return
        if path == "/api/observations":
            store = ObservationStore(default_config.database_path)
            body = json.dumps(store.recent()).encode()
            self.send_response(200); self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store"); self.send_header("Content-Length", str(len(body)))
            self.end_headers(); self.wfile.write(body); return
        self.send_response(404); self.end_headers()

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    host = os.getenv("RF_FINDER_HOST", "127.0.0.1")
    port = int(os.getenv("RF_FINDER_PORT", "8080"))
    print(f"RF Finder tactical view: http://{host}:{port}/tactical")
    ThreadingHTTPServer((host, port), Handler).serve_forever()
