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
<style>body{margin:0;background:#071019;color:#d8f4ff;font:13px Arial}header{padding:12px;border-bottom:1px solid #24465d;display:flex;gap:10px;align-items:center;flex-wrap:wrap}.pill,.panel{border:1px solid #24465d;border-radius:6px;padding:8px}.btn{background:#102a3b;color:#d8f4ff;border:1px solid #2c607d;padding:7px 10px;border-radius:4px;cursor:pointer}.grid{display:grid;grid-template-columns:1fr 360px;min-height:calc(100vh - 58px)}#map{min-height:620px;background:#0b1823}.side{padding:10px;overflow:auto}.panel{margin-bottom:10px;background:#0b1823}.panel h3{margin:0 0 8px;color:#62d8ff}.stats{display:grid;grid-template-columns:1fr 1fr;gap:6px}.stat{padding:7px;background:#071019;border:1px solid #19394c}.stat small{display:block;color:#7ea0b4}.signal{padding:7px;border-top:1px solid #19394c}canvas{width:100%;height:180px;background:#03090e;border:1px solid #19394c}.hidden{display:none}</style></head>
<body><header><b>RF FINDER / FIELD</b><span class="pill" id="identity">SIGNED OUT</span><span class="pill" id="run">—</span><button class="btn" id="loginBtn" onclick="login()">Login</button><button class="btn hidden" id="logoutBtn" onclick="logout()">Logout</button><button class="btn hidden" id="scanBtn" onclick="toggleScan()">Start / Stop</button></header>
<div class="grid"><div id="map"><div style="padding:20px">MapLibre/OpenStreetMap tactical map surface</div></div><aside class="side">
<div class="panel"><h3>Live Spectrum</h3><canvas id="spectrum" width="700" height="180"></canvas></div>
<div class="panel"><h3>Waterfall</h3><canvas id="waterfall" width="700" height="180"></canvas></div>
<div class="panel"><h3>Field Status</h3><div class="stats"><div class="stat"><small>Frames</small><b id="frames">0</b></div><div class="stat"><small>GPS</small><b id="gps">not configured</b></div><div class="stat"><small>FFT</small><b id="fft">—</b></div><div class="stat"><small>Center</small><b id="freq">—</b></div></div></div>
<div class="panel"><h3>Recent Signals</h3><div id="signals">Sign in to view RF data.</div></div>
<div class="panel"><h3>Investigations</h3><button class="btn hidden" id="newInv" onclick="newInvestigation()">New investigation</button><div id="investigations"></div></div></aside></div>
<script>
let token=sessionStorage.getItem('rf_finder_token');const $=id=>document.getElementById(id);const fmtHz=h=>h>=1e9?(h/1e9).toFixed(3)+' GHz':(h/1e6).toFixed(3)+' MHz';
async function api(path,opts={}){opts.headers={...(opts.headers||{}),...(token?{Authorization:'Bearer '+token}:{})};const r=await fetch(path,opts);const d=await r.json();if(r.status===401||r.status===403){if(r.status===401)signout();throw Error(d.error||'Not authorized')}return d}
async function login(){const username=prompt('Username:');if(username===null)return;const password=prompt('Password:');if(password===null)return;try{const d=await api('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username,password})});token=d.token;sessionStorage.setItem('rf_finder_token',token);renderAuth(d);refresh()}catch(e){alert('Login failed: '+e.message)}}
function signout(){token=null;sessionStorage.removeItem('rf_finder_token');$('identity').textContent='SIGNED OUT';$('loginBtn').classList.remove('hidden');['logoutBtn','scanBtn','newInv'].forEach(id=>$(id).classList.add('hidden'));$('signals').textContent='Sign in to view RF data.';$('investigations').textContent=''}
async function logout(){try{await api('/api/auth/logout',{method:'POST'})}finally{signout()}}
function renderAuth(d){$('identity').textContent=d.username+' / '+d.role;$('loginBtn').classList.add('hidden');['logoutBtn','scanBtn','newInv'].forEach(id=>$(id).classList.remove('hidden'))}
function drawSpectrum(s){const c=$('spectrum'),x=c.getContext('2d');x.clearRect(0,0,c.width,c.height);if(!s.power_db?.length)return;x.beginPath();const min=Math.min(...s.power_db),max=Math.max(...s.power_db);s.power_db.forEach((v,i)=>{const px=i*(c.width-1)/(s.power_db.length-1),py=c.height-8-(v-min)/Math.max(1,max-min)*(c.height-16);i?x.lineTo(px,py):x.moveTo(px,py)});x.strokeStyle='#62d8ff';x.stroke()}
function drawWaterfall(w){const c=$('waterfall'),x=c.getContext('2d');x.clearRect(0,0,c.width,c.height);const fs=w.frames||[];const rows=Math.min(fs.length,c.height);for(let r=0;r<rows;r++){const row=fs[fs.length-rows+r],min=Math.min(...row),max=Math.max(...row);for(let i=0;i<row.length;i++){const v=(row[i]-min)/Math.max(1,max-min);const g=Math.floor(255*v);x.fillStyle=`rgb(${g},${Math.floor(100+120*v)},${255-g})`;x.fillRect(i*c.width/row.length,c.height-1-r,c.width/row.length+1,1)}}}
async function refresh(){if(!token)return;try{const [s,w,o,iv]=await Promise.all([api('/api/spectrum'),api('/api/waterfall'),api('/api/observations?limit=30'),api('/api/investigations')]);drawSpectrum(s);drawWaterfall(w);$('signals').innerHTML=o.slice().reverse().map(q=>`<div class="signal"><b>${q.signal_class}</b> — ${fmtHz(q.frequency_hz)}<br>SNR ${q.snr_db.toFixed(1)} dB · BW ${(q.bandwidth_hz/1000).toFixed(1)} kHz · ${q.source}</div>`).join('')||'No detections yet';$('investigations').innerHTML=iv.map(i=>`<div class="signal"><b>${i.title}</b><br>${i.status} · ${i.created_at.slice(0,19)}Z</div>`).join('')||'No investigations'}catch(e){console.log(e)}}
async function status(){if(!token)return;try{const s=await api('/api/status');$('run').textContent=s.running?'RUNNING':'STOPPED';$('frames').textContent=s.frame_index;$('fft').textContent=s.fft_size;$('freq').textContent=fmtHz(s.center_frequency_hz);const g=s.gps;$('gps').textContent=g.latitude!=null?`${g.latitude.toFixed(4)}, ${g.longitude.toFixed(4)}`:'not configured'}catch(e){}}
async function toggleScan(){const s=await api('/api/status');await api(s.running?'/api/stop':'/api/start',{method:'POST'});status()}
async function newInvestigation(){const title=prompt('Investigation title:');if(title)await api('/api/investigations',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title})});refresh()}
if(token){api('/api/auth/me').then(renderAuth).catch(signout)}setInterval(()=>{status();refresh()},1000);
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
