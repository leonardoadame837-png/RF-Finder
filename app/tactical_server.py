"""Authenticated tactical HTTP UI/API for RF Finder."""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from app.api_auth import APIAuth
from app.auth import AuthError, AuthManager
from app.investigations import InvestigationStore


HTML = r'''<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>RF Finder — Field Monitor</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" integrity="sha256-p4NxAoJBhIINfQ3uZ5gkP4K9gY8m7R7zJ3QwXh5k2M0=" crossorigin="">
<style>
body{margin:0;background:#071019;color:#d8f4ff;font:13px Arial,sans-serif}header{padding:12px;border-bottom:1px solid #24465d;display:flex;gap:10px;align-items:center;flex-wrap:wrap}.pill,.panel{border:1px solid #24465d;border-radius:6px;padding:8px}.btn{background:#102a3b;color:#d8f4ff;border:1px solid #2c607d;padding:7px 10px;border-radius:4px;cursor:pointer}.grid{display:grid;grid-template-columns:minmax(0,1fr) 380px;min-height:calc(100vh - 58px)}#map{min-height:720px;background:#0b1823}.side{padding:10px;overflow:auto}.panel{margin-bottom:10px;background:#0b1823}.panel h3{margin:0 0 8px;color:#62d8ff}.stats{display:grid;grid-template-columns:1fr 1fr;gap:6px}.stat{padding:7px;background:#071019;border:1px solid #19394c}.stat small{display:block;color:#7ea0b4}.signal{padding:7px;border-top:1px solid #19394c}canvas{width:100%;height:180px;background:#03090e;border:1px solid #19394c}.hidden{display:none}.notice{font-size:12px;line-height:1.4;color:#9bb8c7}.legend span{display:inline-block;margin-right:10px}.dot{width:9px;height:9px;border-radius:50%;display:inline-block}.green{background:#35d07f}.yellow{background:#ffd34d}.orange{background:#ff9f43}.red{background:#ff5b5b}
@media(max-width:900px){.grid{grid-template-columns:1fr}.side{max-height:none}#map{min-height:480px}}
</style></head>
<body><header><b>RF FINDER / FIELD</b><span class="pill" id="identity">SIGNED OUT</span><span class="pill" id="run">—</span><button class="btn" id="loginBtn" onclick="login()">Login</button><button class="btn hidden" id="logoutBtn" onclick="logout()">Logout</button><button class="btn hidden" id="scanBtn" onclick="toggleScan()">Start / Stop</button></header>
<div class="grid"><div id="map"></div><aside class="side">
<div class="panel"><h3>RF Evidence Map</h3><div class="notice">Markers show the receiver's measured GPS position, not a proven transmitter location. RF characteristics alone do not establish illegality. Use repeated passive measurements and human/authority review.</div><div class="legend"><span><i class="dot green"></i> normal</span><span><i class="dot yellow"></i> unusual</span><span><i class="dot orange"></i> persistent</span><span><i class="dot red"></i> high-priority</span></div></div>
<div class="panel"><h3>Live Spectrum</h3><canvas id="spectrum" width="700" height="180"></canvas></div>
<div class="panel"><h3>Waterfall</h3><canvas id="waterfall" width="700" height="180"></canvas></div>
<div class="panel"><h3>Field Status</h3><div class="stats"><div class="stat"><small>Frames</small><b id="frames">0</b></div><div class="stat"><small>GPS</small><b id="gps">not configured</b></div><div class="stat"><small>FFT</small><b id="fft">—</b></div><div class="stat"><small>Center</small><b id="freq">—</b></div></div></div>
<div class="panel"><h3>Recent RF Evidence</h3><div id="signals">Sign in to view RF data.</div></div>
<div class="panel"><h3>Investigations</h3><button class="btn hidden" id="newInv" onclick="newInvestigation()">New investigation</button><div id="investigations"></div></div></aside></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
<script>
let token=sessionStorage.getItem('rf_finder_token');let map,markers=new Map();const $=id=>document.getElementById(id);const fmtHz=h=>h>=1e9?(h/1e9).toFixed(3)+' GHz':(h/1e6).toFixed(3)+' MHz';
function initMap(){map=L.map('map').setView([39,-98],4);L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© OpenStreetMap contributors'}).addTo(map)}
function markerColor(q){if(q.simulated)return '#8b8b8b';if(q.snr_db>=35)return '#ff5b5b';if(q.snr_db>=25)return '#ff9f43';if(q.snr_db>=20)return '#ffd34d';return '#35d07f'}
function renderMap(obs){if(!map)return;const valid=obs.filter(q=>q.latitude!=null&&q.longitude!=null);valid.forEach(q=>{const id=String(q.id);let m=markers.get(id);const color=markerColor(q);const html=`<b>${q.simulated?'SIMULATION':'SDR MEASUREMENT'}</b><br>${fmtHz(q.frequency_hz)}<br>SNR ${Number(q.snr_db).toFixed(1)} dB · BW ${(Number(q.bandwidth_hz)/1000).toFixed(1)} kHz<br>Power ${Number(q.peak_power_db).toFixed(1)} dB<br>${q.timestamp}<br><small>Receiver GPS: ${Number(q.latitude).toFixed(6)}, ${Number(q.longitude).toFixed(6)}</small><br><small>Classification: ${q.signal_class}; confidence ${(Number(q.confidence)*100).toFixed(0)}%</small>`;if(!m){m=L.circleMarker([q.latitude,q.longitude],{radius:8,color:'#071019',weight:2,fillColor:color,fillOpacity:.9}).addTo(map);markers.set(id,m)}m.setLatLng([q.latitude,q.longitude]).setStyle({fillColor:color}).bindPopup(html)});if(valid.length){const last=valid[valid.length-1];map.setView([last.latitude,last.longitude],Math.max(map.getZoom(),12))}}
async function api(path,opts={}){opts.headers={...(opts.headers||{}),...(token?{Authorization:'Bearer '+token}:{})};const r=await fetch(path,opts);const d=await r.json();if(r.status===401||r.status===403){if(r.status===401)signout();throw Error(d.error||'Not authorized')}return d}
async function login(){const username=prompt('Username:');if(username===null)return;const password=prompt('Password:');if(password===null)return;try{const d=await api('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username,password})});token=d.token;sessionStorage.setItem('rf_finder_token',token);renderAuth(d);refresh()}catch(e){alert('Login failed: '+e.message)}}
function signout(){token=null;sessionStorage.removeItem('rf_finder_token');$('identity').textContent='SIGNED OUT';$('loginBtn').classList.remove('hidden');['logoutBtn','scanBtn','newInv'].forEach(id=>$(id).classList.add('hidden'));$('signals').textContent='Sign in to view RF data.';$('investigations').textContent=''}
async function logout(){try{await api('/api/auth/logout',{method:'POST'})}finally{signout()}}
function renderAuth(d){$('identity').textContent=d.username+' / '+d.role;$('loginBtn').classList.add('hidden');['logoutBtn','scanBtn','newInv'].forEach(id=>$(id).classList.remove('hidden'))}
function drawSpectrum(s){const c=$('spectrum'),x=c.getContext('2d');x.clearRect(0,0,c.width,c.height);if(!s.power_db?.length)return;x.beginPath();const min=Math.min(...s.power_db),max=Math.max(...s.power_db);s.power_db.forEach((v,i)=>{const px=i*(c.width-1)/(s.power_db.length-1),py=c.height-8-(v-min)/Math.max(1,max-min)*(c.height-16);i?x.lineTo(px,py):x.moveTo(px,py)});x.strokeStyle='#62d8ff';x.stroke()}
function drawWaterfall(w){const c=$('waterfall'),x=c.getContext('2d');x.clearRect(0,0,c.width,c.height);const fs=w.frames||[];const rows=Math.min(fs.length,c.height);for(let r=0;r<rows;r++){const row=fs[fs.length-rows+r],min=Math.min(...row),max=Math.max(...row);for(let i=0;i<row.length;i++){const v=(row[i]-min)/Math.max(1,max-min);const g=Math.floor(255*v);x.fillStyle=`rgb(${g},${Math.floor(100+120*v)},${255-g})`;x.fillRect(i*c.width/row.length,c.height-1-r,c.width/row.length+1,1)}}}
async function refresh(){if(!token)return;try{const [s,w,o,iv]=await Promise.all([api('/api/spectrum'),api('/api/waterfall'),api('/api/observations?limit=100'),api('/api/investigations')]);drawSpectrum(s);drawWaterfall(w);renderMap(o);$('signals').innerHTML=o.slice().reverse().map(q=>`<div class="signal"><b>${q.simulated?'SIMULATION':'SDR'}</b> — ${q.signal_class} — ${fmtHz(q.frequency_hz)}<br>SNR ${Number(q.snr_db).toFixed(1)} dB · BW ${(Number(q.bandwidth_hz)/1000).toFixed(1)} kHz · ${q.source}<br>${q.latitude!=null?`GPS ${Number(q.latitude).toFixed(5)}, ${Number(q.longitude).toFixed(5)}`:'GPS unavailable'}</div>`).join('')||'No detections yet';$('investigations').innerHTML=iv.map(i=>`<div class="signal"><b>${i.title}</b><br>${i.status} · ${i.created_at.slice(0,19)}Z</div>`).join('')||'No investigations'}catch(e){console.log(e)}}
async function status(){if(!token)return;try{const s=await api('/api/status');$('run').textContent=s.running?'RUNNING':'STOPPED';$('frames').textContent=s.frame_index;$('fft').textContent=s.fft_size;$('freq').textContent=fmtHz(s.center_frequency_hz);const g=s.gps;$('gps').textContent=g.latitude!=null?`${g.latitude.toFixed(4)}, ${g.longitude.toFixed(4)}`:'not configured'}catch(e){}}
async function toggleScan(){const s=await api('/api/status');await api(s.running?'/api/stop':'/api/start',{method:'POST'});status()}
async function newInvestigation(){const title=prompt('Investigation title:');if(title)await api('/api/investigations',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title})});refresh()}
initMap();if(token){api('/api/auth/me').then(renderAuth).catch(signout)}setInterval(()=>{status();refresh()},1000);
</script></body></html>'''


def create_server(service, host="127.0.0.1", port=8000, auth=None):
    api_auth = auth or APIAuth(AuthManager())
    investigation_store = InvestigationStore(service.config.database_path)

    class Handler(BaseHTTPRequestHandler):
        def _send(self, payload, status=200, content_type="application/json"):
            body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json_body(self):
            try:
                length = int(self.headers.get("Content-Length", "0"))
                return json.loads(self.rfile.read(length)) if length else {}
            except (ValueError, json.JSONDecodeError):
                return {}

        def _require(self, permission):
            return api_auth.require(self.headers.get("Authorization"), permission)

        def do_GET(self):
            path = urlparse(self.path).path
            if path in ("/", "/tactical"):
                return self._send(HTML.encode(), content_type="text/html; charset=utf-8")
            try:
                if path == "/api/auth/me":
                    p = self._require(None); return self._send({"username": p.user.username, "role": p.user.role, "permissions": sorted(api_auth_permissions(p.user.role))})
                if path == "/api/status": self._require("rf.read"); return self._send(service.status())
                if path == "/api/spectrum": self._require("rf.read"); return self._send(service.latest_spectrum())
                if path == "/api/waterfall": self._require("rf.read"); return self._send(service.waterfall())
                if path == "/api/observations":
                    self._require("rf.read"); q=parse_qs(urlparse(self.path).query); limit=max(1,min(1000,int(q.get("limit",[250])[0]))); return self._send(service.observations(limit))
                if path == "/api/investigations": self._require("investigation.read"); return self._send(investigation_store.list())
                return self._send({"error":"not found"},404)
            except PermissionError as exc:
                return self._send({"error":str(exc)},401 if str(exc)=="Authentication required" else 403)
            except (ValueError, TypeError):
                return self._send({"error":"invalid request"},400)

        def do_POST(self):
            path=urlparse(self.path).path
            try:
                if path == "/api/auth/login":
                    data=self._json_body(); session=api_auth.login(str(data.get("username","")),str(data.get("password","")))
                    return self._send({"token":session.token,"expires_at":session.expires_at,"username":session.user.username,"role":session.user.role,"permissions":sorted(api_auth_permissions(session.user.role))})
                if path == "/api/auth/logout":
                    self._require(None); api_auth.logout(self.headers.get("Authorization")); return self._send({"ok":True})
                if path == "/api/start": self._require("rf.scan"); service.start(); return self._send(service.status())
                if path == "/api/stop": self._require("rf.scan"); service.stop(); return self._send(service.status())
                if path == "/api/investigations":
                    self._require("investigation.write"); data=self._json_body(); return self._send(investigation_store.create(str(data.get("title","RF investigation")),str(data.get("notes",""))),201)
                return self._send({"error":"not found"},404)
            except AuthError:
                return self._send({"error":"Invalid username or password."},401)
            except PermissionError as exc:
                return self._send({"error":str(exc)},401 if str(exc)=="Authentication required" else 403)

        def log_message(self, fmt, *args):
            pass

    return ThreadingHTTPServer((host, port), Handler)


def api_auth_permissions(role):
    from app.api_auth import ROLE_PERMISSIONS
    return ROLE_PERMISSIONS.get(role, frozenset())


if __name__ == "__main__":
    from app.field_service import RFService
    host=os.getenv("RF_FINDER_HOST","127.0.0.1"); port=int(os.getenv("RF_FINDER_PORT","8080")); service=RFService(); service.start(); print(f"RF Finder tactical view: http://{host}:{port}/tactical")
    server=create_server(service,host,port)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: service.stop(); server.server_close()
