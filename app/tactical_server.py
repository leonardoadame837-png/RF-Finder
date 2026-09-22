"""Authenticated tactical HTTP UI/API for RF Finder."""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from app.api_auth import APIAuth, SESSION_COOKIE
from app.auth import AuthError, AuthManager
from app.evidence_api import investigation_report, localization_payload
from app.investigations import InvestigationStore
from app.vision import CameraRegistry, EventCorrelator, VisionEventStore, camera_status
from app.camera_broker import CameraBroker


HTML = r'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>RF Finder — Field Monitor</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"><style>
body{margin:0;background:#071019;color:#d8f4ff;font:13px Arial}header{padding:12px;border-bottom:1px solid #24465d;display:flex;gap:8px;align-items:center;flex-wrap:wrap}.pill,.panel{border:1px solid #24465d;border-radius:6px;padding:8px}.btn{background:#102a3b;color:#d8f4ff;border:1px solid #2c607d;padding:7px 10px;border-radius:4px;cursor:pointer}.grid{display:grid;grid-template-columns:minmax(0,1fr) 420px;min-height:calc(100vh - 58px)}#map{min-height:720px}.side{padding:10px;overflow:auto}.panel{margin-bottom:10px;background:#0b1823}.panel h3{margin:0 0 8px;color:#62d8ff}.signal{padding:7px;border-top:1px solid #19394c}.hidden{display:none}.notice{font-size:12px;color:#9bb8c7;line-height:1.4}.legend span{margin-right:9px}.dot{display:inline-block;width:9px;height:9px;border-radius:50%}.green{background:#35d07f}.yellow{background:#ffd34d}.orange{background:#ff9f43}.red{background:#ff5b5b}canvas{width:100%;height:160px;background:#03090e;border:1px solid #19394c}pre{white-space:pre-wrap;max-height:320px;overflow:auto}@media(max-width:900px){.grid{grid-template-columns:1fr}#map{min-height:480px}}
</style></head><body><header><b>RF FINDER / FIELD</b><span class="pill" id="identity">SIGNED OUT</span><span class="pill" id="run">—</span><button class="btn" id="loginBtn" onclick="login()">Login</button><button class="btn hidden" id="logoutBtn" onclick="logout()">Logout</button><button class="btn hidden" id="scanBtn" onclick="toggleScan()">Start / Stop</button></header>
<div class="grid"><div id="map"></div><aside class="side"><div class="panel"><h3>RF Evidence Map</h3><div class="notice">Map points are receiver measurement positions. They are not proof of a transmitter's exact location or legal status.</div><div class="legend"><span><i class="dot green"></i> normal</span><span><i class="dot yellow"></i> unusual</span><span><i class="dot orange"></i> persistent</span><span><i class="dot red"></i> high priority</span></div></div>
<div class="panel"><h3>Live Spectrum</h3><canvas id="spectrum" width="700" height="160"></canvas></div><div class="panel"><h3>Waterfall</h3><canvas id="waterfall" width="700" height="160"></canvas></div>
<div class="panel"><h3>Investigations</h3><button class="btn hidden" id="newInv" onclick="newInvestigation()">Create Investigation</button><div id="investigations"></div></div>
<div class="panel"><h3>Attach RF Observations</h3><div id="attachList">Create an investigation first.</div></div>
<div class="panel"><h3>Evidence Report</h3><button class="btn hidden" id="reportBtn" onclick="report()">Generate Evidence Report</button><pre id="reportOut">No report generated.</pre></div>
<div class="panel"><h3>Multi-position Localization</h3><button class="btn" onclick="heatmap()">Refresh Heatmap Data</button><div id="heatInfo" class="notice">Passive receiver-position heatmap. Simulated data is excluded.</div></div>
<div class="panel"><h3>Recent RF Evidence</h3><div id="signals">Sign in to view RF data.</div></div></aside></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script><script>
let token=sessionStorage.getItem('rf_finder_token'),map,markers=new Map(),selectedInv=null,observations=[];const $=id=>document.getElementById(id);const fmtHz=h=>h>=1e9?(h/1e9).toFixed(3)+' GHz':(h/1e6).toFixed(3)+' MHz';
function initMap(){map=L.map('map').setView([39,-98],4);L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© OpenStreetMap contributors'}).addTo(map)}
function markerColor(q){if(q.simulated)return '#888';if(q.snr_db>=35)return '#ff5b5b';if(q.snr_db>=25)return '#ff9f43';if(q.snr_db>=20)return '#ffd34d';return '#35d07f'}
function renderMap(obs){const valid=obs.filter(q=>q.latitude!=null&&q.longitude!=null);valid.forEach(q=>{const id=String(q.id),color=markerColor(q),html=`<b>${q.simulated?'SIMULATION':'SDR MEASUREMENT'}</b><br>${fmtHz(q.frequency_hz)}<br>SNR ${Number(q.snr_db).toFixed(1)} dB · BW ${(Number(q.bandwidth_hz)/1000).toFixed(1)} kHz<br>Power ${Number(q.peak_power_db).toFixed(1)} dB<br>${q.timestamp}<br>Receiver GPS: ${Number(q.latitude).toFixed(6)}, ${Number(q.longitude).toFixed(6)}`;let m=markers.get(id);if(!m){m=L.circleMarker([q.latitude,q.longitude],{radius:8,color:'#071019',weight:2,fillColor:color,fillOpacity:.9}).addTo(map);markers.set(id,m)}m.setLatLng([q.latitude,q.longitude]).setStyle({fillColor:color}).bindPopup(html)});if(valid.length)map.setView([valid[valid.length-1].latitude,valid[valid.length-1].longitude],Math.max(map.getZoom(),12))}
async function api(path,opts={}){opts.headers={...(opts.headers||{}),...(token?{Authorization:'Bearer '+token}:{})};const r=await fetch(path,opts);const d=await r.json();if(r.status===401||r.status===403){if(r.status===401)signout();throw Error(d.error||'Not authorized')}return d}
async function login(){const username=prompt('Username:');if(username===null)return;const password=prompt('Password:');if(password===null)return;try{const d=await api('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username,password})});token=d.token;sessionStorage.setItem('rf_finder_token',token);renderAuth(d);refresh()}catch(e){alert('Login failed: '+e.message)}}
function signout(){token=null;sessionStorage.removeItem('rf_finder_token');$('identity').textContent='SIGNED OUT';$('loginBtn').classList.remove('hidden');['logoutBtn','scanBtn','newInv','reportBtn'].forEach(id=>$(id).classList.add('hidden'));$('signals').textContent='Sign in to view RF data.'}
async function logout(){try{await api('/api/auth/logout',{method:'POST'})}finally{signout()}}function renderAuth(d){$('identity').textContent=d.username+' / '+d.role;$('loginBtn').classList.add('hidden');['logoutBtn','scanBtn','newInv'].forEach(id=>$(id).classList.remove('hidden'))}
function drawSpectrum(s){const c=$('spectrum'),x=c.getContext('2d');x.clearRect(0,0,c.width,c.height);if(!s.power_db?.length)return;x.beginPath();const min=Math.min(...s.power_db),max=Math.max(...s.power_db);s.power_db.forEach((v,i)=>{const px=i*(c.width-1)/(s.power_db.length-1),py=c.height-8-(v-min)/Math.max(1,max-min)*(c.height-16);i?x.lineTo(px,py):x.moveTo(px,py)});x.strokeStyle='#62d8ff';x.stroke()}
function drawWaterfall(w){const c=$('waterfall'),x=c.getContext('2d');x.clearRect(0,0,c.width,c.height);const fs=w.frames||[];const rows=Math.min(fs.length,c.height);for(let r=0;r<rows;r++){const row=fs[fs.length-rows+r],min=Math.min(...row),max=Math.max(...row);for(let i=0;i<row.length;i++){const v=(row[i]-min)/Math.max(1,max-min),g=Math.floor(255*v);x.fillStyle=`rgb(${g},${Math.floor(100+120*v)},${255-g})`;x.fillRect(i*c.width/row.length,c.height-1-r,c.width/row.length+1,1)}}}
async function refresh(){if(!token)return;try{const [s,w,o,iv]=await Promise.all([api('/api/spectrum'),api('/api/waterfall'),api('/api/observations?limit=200'),api('/api/investigations')]);observations=o;drawSpectrum(s);drawWaterfall(w);renderMap(o);$('signals').innerHTML=o.slice().reverse().map(q=>`<div class="signal"><b>${q.simulated?'SIMULATION':'SDR'}</b> — ${q.signal_class} — ${fmtHz(q.frequency_hz)}<br>SNR ${Number(q.snr_db).toFixed(1)} dB · BW ${(Number(q.bandwidth_hz)/1000).toFixed(1)} kHz<br>${q.latitude!=null?`GPS ${Number(q.latitude).toFixed(5)}, ${Number(q.longitude).toFixed(5)}`:'GPS unavailable'}</div>`).join('')||'No detections yet';renderInvestigations(iv)}catch(e){console.log(e)}}
function renderInvestigations(iv){$('investigations').innerHTML=iv.map(i=>`<div class="signal"><button class="btn" onclick="selectInv(${i.id})">${i.title}</button> <span>${i.status} · ${i.observation_ids.length} observations</span></div>`).join('')||'No investigations'}
async function selectInv(id){const iv=await api('/api/investigations');selectedInv=iv.find(x=>x.id===id)||null;if(!selectedInv)return;$('reportBtn').classList.remove('hidden');const ids=new Set(selectedInv.observation_ids);$('attachList').innerHTML=observations.slice().reverse().map(o=>`<label class="signal"><input type="checkbox" ${ids.has(o.id)?'checked':''} onchange="attach(${selectedInv.id},${o.id},this.checked)"> #${o.id} ${fmtHz(o.frequency_hz)} · SNR ${Number(o.snr_db).toFixed(1)} · ${o.simulated?'SIM':'SDR'}</label>`).join('')||'No observations'}
async function newInvestigation(){const title=prompt('Investigation title:');if(!title)return;const d=await api('/api/investigations',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title})});await selectInv(d.id);refresh()}
async function attach(id,obs,checked){if(!checked){alert('Observations are append-only in this evidence workflow. Create a new investigation if an observation must be excluded.');return}await api(`/api/investigations/${id}/observations`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({observation_id:obs})});selectInv(id)}
async function report(){if(!selectedInv)return;const d=await api(`/api/investigations/${selectedInv.id}/report`);$('reportOut').textContent=JSON.stringify(d,null,2)}
async function heatmap(){const d=await api('/api/localization/heatmap');$('heatInfo').textContent=`${d.measurement_count} real GPS measurements · ${d.cells.length} heatmap cells · ${d.method}. ${d.limitations[0]}`}
async function status(){if(!token)return;try{const s=await api('/api/status');$('run').textContent=s.running?'RUNNING':'STOPPED'}catch(e){}}async function toggleScan(){const s=await api('/api/status');await api(s.running?'/api/stop':'/api/start',{method:'POST'});status()}initMap();if(token){api('/api/auth/me').then(renderAuth).catch(signout)}setInterval(()=>{status();refresh()},1500);
</script></body></html>'''


def create_server(service, host="127.0.0.1", port=8000, auth=None):
    api_auth=auth or APIAuth(AuthManager()); investigation_store=InvestigationStore(service.config.database_path); camera_registry=CameraRegistry(service.config.database_path); vision_events=VisionEventStore(service.config.database_path); broker=CameraBroker(event_callback=vision_events.add)
    class Handler(BaseHTTPRequestHandler):
        def _send(self,payload,status=200,content_type="application/json"):
            body=payload if isinstance(payload,bytes) else json.dumps(payload).encode(); self.send_response(status); self.send_header("Content-Type",content_type); self.send_header("Cache-Control","no-store"); self.send_header("Access-Control-Allow-Origin", self.headers.get("Origin","*")); self.send_header("Vary","Origin"); self.send_header("Access-Control-Allow-Headers","Authorization, Content-Type"); self.send_header("Access-Control-Allow-Methods","GET, POST, OPTIONS"); self.send_header("Content-Length",str(len(body))); self.end_headers(); self.wfile.write(body)
        def _json_body(self):
            try:
                length=int(self.headers.get("Content-Length","0")); return json.loads(self.rfile.read(length)) if length else {}
            except (ValueError,json.JSONDecodeError): return {}
        def _require(self,p): return api_auth.require(self.headers.get("Authorization"),p,self.headers.get("Cookie"))
        def do_OPTIONS(self):
            self.send_response(204); self.send_header("Access-Control-Allow-Origin", self.headers.get("Origin","*")); self.send_header("Vary","Origin"); self.send_header("Access-Control-Allow-Headers","Authorization, Content-Type"); self.send_header("Access-Control-Allow-Methods","GET, POST, OPTIONS"); self.end_headers()
        def do_GET(self):
            path=urlparse(self.path).path
            if path in ("/","/tactical"): return self._send(HTML.encode(),content_type="text/html; charset=utf-8")
            if path == "/rf-studio":
                from pathlib import Path
                page = Path(__file__).resolve().parent.parent / "docs" / "rf-studio.html"
                try: return self._send(page.read_bytes(),content_type="text/html; charset=utf-8")
                except OSError: return self._send({"error":"RF Studio unavailable"},404)
            if path == "/camera":
                from pathlib import Path
                page = Path(__file__).resolve().parent.parent / "docs" / "camera.html"
                try: return self._send(page.read_bytes(),content_type="text/html; charset=utf-8")
                except OSError: return self._send({"error":"camera workspace unavailable"},404)
            try:
                if path=="/api/auth/me": p=self._require(None); return self._send({"username":p.user.username,"role":p.user.role,"permissions":sorted(api_auth_permissions(p.user.role))})
                if path=="/api/status": self._require("rf.read"); return self._send(service.status())
                if path=="/api/spectrum": self._require("rf.read"); return self._send(service.latest_spectrum())
                if path=="/api/waterfall": self._require("rf.read"); return self._send(service.waterfall())
                if path=="/api/observations": self._require("rf.read"); q=parse_qs(urlparse(self.path).query); return self._send(service.observations(max(1,min(1000,int(q.get("limit",[250])[0])))))
                if path=="/api/investigations": self._require("investigation.read"); return self._send(investigation_store.list())
                if path=="/api/cameras": self._require("investigation.read"); return self._send(camera_registry.list())
                if path.startswith("/api/cameras/") and "/stream/" in path:
                    self._require("investigation.read")
                    parts=path.split("/"); camera_id=int(parts[3]); relative="/".join(parts[5:])
                    file=broker.stream_file(camera_id,relative)
                    if not file: return self._send({"error":"stream segment not found"},404)
                    mime="application/vnd.apple.mpegurl" if file.suffix==".m3u8" else "video/mp2t"
                    return self._send(file.read_bytes(),content_type=mime)
                if path.startswith("/api/cameras/"):
                    self._require("investigation.read"); camera_id=int(path.split("/")[3]); camera=camera_registry.get(camera_id); return self._send({**(camera or {"error":"camera not found"}), "status": {**camera_status(camera), "broker": broker.status(camera) if camera else {"state":"NOT_FOUND"}}},200 if camera else 404)
                if path=="/api/vision/events": self._require("investigation.read"); q=parse_qs(urlparse(self.path).query); return self._send(vision_events.recent(int(q.get("limit",[200])[0])))
                if path.startswith("/api/investigations/") and path.endswith("/report"):
                    self._require("investigation.read"); iid=int(path.split("/")[3]); data=investigation_report(investigation_store,service.store,iid); return self._send(data or {"error":"investigation not found"},200 if data else 404)
                if path=="/api/localization/heatmap": self._require("rf.read"); return self._send(localization_payload(service.store)["heatmap"])
                if path=="/api/localization/tracks": self._require("rf.read"); return self._send({"tracks":localization_payload(service.store)["tracks"]})
                return self._send({"error":"not found"},404)
            except PermissionError as exc:return self._send({"error":str(exc)},401 if str(exc)=="Authentication required" else 403)
            except (ValueError,TypeError):return self._send({"error":"invalid request"},400)
        def do_POST(self):
            path=urlparse(self.path).path
            try:
                if path=="/api/auth/login": data=self._json_body(); s=api_auth.login(str(data.get("username","")),str(data.get("password",""))); self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Cache-Control", "no-store"); self.send_header("Set-Cookie", f"{SESSION_COOKIE}={s.token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=3600"); self.send_header("Access-Control-Allow-Origin", self.headers.get("Origin","*")); self.send_header("Access-Control-Allow-Credentials", "true"); self.send_header("Vary","Origin"); body=json.dumps({"token":s.token,"expires_at":s.expires_at,"username":s.user.username,"role":s.user.role,"permissions":sorted(api_auth_permissions(s.user.role))}).encode(); self.send_header("Content-Length",str(len(body))); self.end_headers(); self.wfile.write(body); return
                if path=="/api/auth/logout":\n                    self._require(None); api_auth.logout(self.headers.get("Authorization"), self.headers.get("Cookie")); body=json.dumps({"ok":True}).encode(); self.send_response(200); self.send_header("Content-Type","application/json"); self.send_header("Cache-Control","no-store"); self.send_header("Set-Cookie",f"{SESSION_COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0"); self.send_header("Access-Control-Allow-Origin",self.headers.get("Origin","*")); self.send_header("Access-Control-Allow-Credentials","true"); self.send_header("Vary","Origin"); self.send_header("Content-Length",str(len(body))); self.end_headers(); self.wfile.write(body); return
                if path=="/api/start": self._require("rf.scan"); service.start(); return self._send(service.status())
                if path=="/api/stop": self._require("rf.scan"); service.stop(); return self._send(service.status())
                if path=="/api/investigations": self._require("investigation.write"); data=self._json_body(); return self._send(investigation_store.create(str(data.get("title","RF investigation")),str(data.get("notes",""))),201)
                if path=="/api/cameras":
                    self._require("investigation.write"); data=self._json_body()
                    camera=camera_registry.create(name=str(data.get("name","RF Camera")),host=str(data.get("host","")),port=int(data.get("port",554)),protocol=str(data.get("protocol","rtsp")),username=str(data.get("username","")),stream_path=str(data.get("stream_path","/")),audio_enabled=bool(data.get("audio_enabled",False)))
                    return self._send(camera,201)
                if path.startswith("/api/cameras/") and path.endswith("/start"):
                    self._require("investigation.write"); camera_id=int(path.split("/")[3]); camera=camera_registry.get(camera_id)
                    if not camera: return self._send({"error":"camera not found"},404)
                    return self._send(broker.start(camera))
                if path.startswith("/api/cameras/") and path.endswith("/stop"):
                    self._require("investigation.write"); camera_id=int(path.split("/")[3]); return self._send(broker.stop(camera_id))
                if path=="/api/vision/events":
                    self._require("investigation.write"); event=self._json_body()
                    return self._send(vision_events.add(event),201)
                if path=="/api/vision/correlate":
                    self._require("investigation.read"); data=self._json_body()
                    events=list(data.get("events") or []) or vision_events.recent(200)
                    spectrum=service.latest_spectrum()
                    for index,detection in enumerate(spectrum.get("detections") or []):
                        events.append({"event_id":f"rf-{spectrum.get('timestamp')}-{index}","event_type":"RF_DETECTION","source_id":"rf-service","source_type":spectrum.get("source_type","UNKNOWN"),"timestamp":spectrum.get("timestamp"),"payload":detection})
                    return self._send({"groups":EventCorrelator(int(data.get("window_ms",1000))).correlate(events)})
                if path.startswith("/api/investigations/") and path.endswith("/observations"):
                    self._require("investigation.write"); iid=int(path.split("/")[3]); data=self._json_body(); oid=int(data.get("observation_id"));
                    if not investigation_store.attach_observation(iid,oid): return self._send({"error":"investigation not found"},404)
                    return self._send(investigation_store.get(iid))
                return self._send({"error":"not found"},404)
            except (RuntimeError, ValueError) as exc:return self._send({"error":str(exc)},400)
            except AuthError:return self._send({"error":"Invalid username or password."},401)
            except PermissionError as exc:return self._send({"error":str(exc)},401 if str(exc)=="Authentication required" else 403)
            except (ValueError,TypeError):return self._send({"error":"invalid request"},400)
        def log_message(self,fmt,*args): pass
    return ThreadingHTTPServer((host,port),Handler)


def api_auth_permissions(role):
    from app.api_auth import ROLE_PERMISSIONS
    return ROLE_PERMISSIONS.get(role,frozenset())


if __name__=="__main__":
    from app.field_service import RFService
    host=os.getenv("RF_FINDER_HOST","127.0.0.1"); port=int(os.getenv("RF_FINDER_PORT","8080")); service=RFService(); service.start(); server=create_server(service,host,port); print(f"RF Finder tactical view: http://{host}:{port}/tactical")
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: service.stop(); server.server_close()
