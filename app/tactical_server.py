"""Authenticated tactical HTTP UI/API for RF Finder."""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import numpy as np

from app.api_auth import APIAuth
from app.auth import AuthError, AuthManager
from app.evidence_api import investigation_report, localization_payload
from app.investigations import InvestigationStore
from app.source_types import SourceType, normalize_source_type


HTML = r'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>RF Finder — Spectrum Analyzer</title>
<style>
body{margin:0;background:#071019;color:#d8f4ff;font:13px Arial,sans-serif}header{padding:12px;border-bottom:1px solid #24465d;display:flex;gap:8px;align-items:center;flex-wrap:wrap}.pill,.panel{border:1px solid #24465d;border-radius:6px;padding:8px}.btn{background:#102a3b;color:#d8f4ff;border:1px solid #2c607d;padding:7px 10px;border-radius:4px;cursor:pointer}.btn:disabled{opacity:.45;cursor:not-allowed}.grid{display:grid;grid-template-columns:minmax(0,1fr) 440px;min-height:calc(100vh - 58px)}.main{padding:10px}.side{padding:10px;overflow:auto}.panel{margin-bottom:10px;background:#0b1823}.panel h3{margin:0 0 8px;color:#62d8ff}.notice{font-size:12px;color:#9bb8c7;line-height:1.4}.source-sim{border:2px solid #ff9f43;background:#2a1809;color:#ffd8a8;font-weight:700}.source-meas{border:2px solid #35d07f;background:#092117;color:#b8ffd8;font-weight:700}.spectrum-wrap{position:relative}.readouts{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-top:8px}.readout{background:#061019;border:1px solid #19394c;padding:8px;border-radius:4px}.readout b{display:block;color:#62d8ff;margin-top:3px}canvas{width:100%;height:420px;background:#03090e;border:1px solid #19394c;cursor:crosshair}.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse}th,td{padding:7px;border-bottom:1px solid #19394c;text-align:left;white-space:nowrap}th{color:#62d8ff}.signal{padding:7px;border-top:1px solid #19394c}.hidden{display:none}input[type=file]{max-width:100%}@media(max-width:900px){.grid{grid-template-columns:1fr}canvas{height:300px}.readouts{grid-template-columns:repeat(2,1fr)}}
</style></head><body><header><b>RF FINDER / SPECTRUM ANALYZER</b><span class="pill" id="identity">SIGNED OUT</span><span class="pill" id="state">IDLE</span><span class="pill" id="sourceBadge">SOURCE: UNKNOWN</span><button class="btn" id="loginBtn" onclick="login()">Login</button><button class="btn hidden" id="logoutBtn" onclick="logout()">Logout</button></header>
<div class="grid"><main class="main"><div class="panel" id="sourcePanel"><h3>Source & Controls</h3><div id="sourceNotice" class="source-sim" style="padding:10px">SIMULATED — generated test IQ. This is not a verified environmental measurement.</div><p class="notice">The same DSP analyzer/detector pipeline is used for simulation and imported/live measurements. Provenance is carried with every frame and detection.</p><button class="btn hidden" id="startBtn" onclick="startScan()">Start</button> <button class="btn hidden" id="pauseBtn" onclick="pauseScan()">Pause</button> <button class="btn hidden" id="resetBtn" onclick="resetAnalyzer()">Reset</button></div>
<div class="panel"><h3>Spectrum</h3><div class="spectrum-wrap"><canvas id="spectrum" width="1200" height="420"></canvas></div><div class="readouts"><div class="readout">Frequency<b id="freq">—</b></div><div class="readout">Power<b id="power">—</b></div><div class="readout">Noise Floor<b id="noise">—</b></div><div class="readout">SNR<b id="snr">—</b></div></div><p class="notice" id="axis">Frequency axis: —</p></div>
<div class="panel"><h3>Detections</h3><div class="table-wrap"><table><thead><tr><th>Frequency</th><th>Power</th><th>Bandwidth</th><th>SNR</th><th>Confidence</th><th>Source Type</th></tr></thead><tbody id="detections"><tr><td colspan="6">No detections</td></tr></tbody></table></div></div></main>
<aside class="side"><div class="panel"><h3>IQ / Sample Import</h3><input id="file" type="file" accept=".json,.csv"/><button class="btn" onclick="importSamples()">Import</button><div class="notice" style="margin-top:8px">JSON: {samples:[real/imag or complex], center_frequency_hz, sample_rate_hz, timestamp, sample_format}. CSV: real,imag columns. Imported data is labeled IMPORTED_MEASUREMENT by default and is never claimed to be SDR data.</div><div id="importStatus" class="notice"></div></div>
<div class="panel"><h3>Investigation / Field Observation</h3><button class="btn hidden" id="newInv" onclick="newInvestigation()">Create Investigation</button><div id="investigations">Sign in to manage investigations.</div><div id="observationForm" class="hidden"><p class="notice">Selected detection</p><div id="selectedDetection"></div><textarea id="notes" rows="3" style="width:100%;box-sizing:border-box;background:#061019;color:#d8f4ff;border:1px solid #19394c" placeholder="Analyst notes"></textarea><button class="btn" onclick="createObservation()">Create Field Observation</button></div></div>
<div class="panel"><h3>Recent Observations</h3><div id="observations">Sign in to view RF data.</div></div><div class="panel"><h3>Evidence Boundary</h3><div class="notice">RF characteristics are measurements/analysis outputs. Confidence is algorithmic confidence in the detection pattern, not proof of a particular transmitter, person, device, legality, surveillance, or malicious intent.</div></div></aside></div>
<script>
let token=sessionStorage.getItem('rf_finder_token'),latest=null,selected=null;const $=id=>document.getElementById(id);const fmtHz=h=>{h=Number(h);if(!Number.isFinite(h))return '—';if(Math.abs(h)>=1e9)return (h/1e9).toFixed(6)+' GHz';if(Math.abs(h)>=1e6)return (h/1e6).toFixed(6)+' MHz';if(Math.abs(h)>=1e3)return (h/1e3).toFixed(3)+' kHz';return h.toFixed(1)+' Hz'};const fmtDb=v=>Number.isFinite(Number(v))?Number(v).toFixed(2)+' dB':'—';
async function api(path,opts={}){opts.headers={...(opts.headers||{}),...(token?{Authorization:'Bearer '+token}:{})};const r=await fetch(path,opts);const d=await r.json();if(r.status===401||r.status===403){if(r.status===401)signout();throw Error(d.error||'Not authorized')}return d}
async function login(){const username=prompt('Username:');if(username===null)return;const password=prompt('Password:');if(password===null)return;try{const d=await api('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username,password})});token=d.token;sessionStorage.setItem('rf_finder_token',token);renderAuth(d);refresh()}catch(e){alert('Login failed: '+e.message)}}
function signout(){token=null;sessionStorage.removeItem('rf_finder_token');$('identity').textContent='SIGNED OUT';$('loginBtn').classList.remove('hidden');['logoutBtn','startBtn','pauseBtn','resetBtn','newInv'].forEach(id=>$(id).classList.add('hidden'));$('observationForm').classList.add('hidden')}
async function logout(){try{await api('/api/auth/logout',{method:'POST'})}finally{signout()}}
function renderAuth(d){$('identity').textContent=d.username+' / '+d.role;$('loginBtn').classList.add('hidden');['logoutBtn','startBtn','pauseBtn','resetBtn','newInv'].forEach(id=>$(id).classList.remove('hidden'))}
function renderSource(s){const type=s.source_type||s.provenance?.source_type||'UNKNOWN';$('sourceBadge').textContent='SOURCE: '+type;const sim=type==='SIMULATED';$('sourceNotice').className=sim?'source-sim':'source-meas';$('sourceNotice').textContent=sim?'SIMULATED — generated test IQ. This is not a verified environmental measurement.':type==='IMPORTED_MEASUREMENT'?'IMPORTED MEASUREMENT — supplied sample data; hardware origin is not inferred.':type==='LIVE_MEASUREMENT'?'MEASURED — live measurement source.':'UNKNOWN SOURCE — provenance not established.'}
function drawSpectrum(s){latest=s;renderSource(s);const c=$('spectrum'),ctx=c.getContext('2d');ctx.clearRect(0,0,c.width,c.height);const f=s.frequencies_hz||[],p=s.power_dbfs||[];if(!p.length)return;const min=Math.min(...p),max=Math.max(...p),span=Math.max(1,max-min);ctx.beginPath();p.forEach((v,i)=>{const x=i*(c.width-1)/Math.max(1,p.length-1),y=c.height-20-(v-min)/span*(c.height-40);i?ctx.lineTo(x,y):ctx.moveTo(x,y)});ctx.strokeStyle='#62d8ff';ctx.lineWidth=1.5;ctx.stroke();const det=s.detections||[];det.forEach(d=>{const idx=f.reduce((best,v,j)=>Math.abs(v-d.frequency_hz)<Math.abs(f[best]-d.frequency_hz)?j:best,0),x=idx*(c.width-1)/Math.max(1,p.length-1);ctx.fillStyle='#ff9f43';ctx.beginPath();ctx.arc(x,c.height-20-(p[idx]-min)/span*(c.height-40),5,0,Math.PI*2);ctx.fill()});$('noise').textContent=fmtDb(s.noise_floor_dbfs);$('axis').textContent='Frequency axis: '+fmtHz(s.frequency_start_hz)+' to '+fmtHz(s.frequency_end_hz)+' · Δf '+fmtHz(s.frequency_resolution_hz);if(!selected)selectNearestDetection(det[0])}
function selectNearestDetection(d){if(!d)return;selected=d;$('freq').textContent=fmtHz(d.frequency_hz);$('power').textContent=fmtDb(d.power_dbfs);$('snr').textContent=fmtDb(d.snr_db);$('selectedDetection').textContent=fmtHz(d.frequency_hz)+' · '+fmtDb(d.power_dbfs)+' · SNR '+fmtDb(d.snr_db)+' · '+d.source_type;$('observationForm').classList.remove('hidden')}
$('spectrum').addEventListener('click',e=>{if(!latest?.detections?.length)return;const r=e.currentTarget.getBoundingClientRect(),ratio=(e.clientX-r.left)/r.width;const f=latest.frequencies_hz;const hz=f[0]+ratio*(f[f.length-1]-f[0]);selectNearestDetection(latest.detections.reduce((a,b)=>Math.abs(b.frequency_hz-hz)<Math.abs(a.frequency_hz-hz)?b:a))});
function renderDetections(ds){$('detections').innerHTML=ds.length?ds.map((d,i)=>`<tr onclick='selectNearestDetection(${JSON.stringify(d)})'><td>${fmtHz(d.frequency_hz)}</td><td>${fmtDb(d.power_dbfs)}</td><td>${fmtHz(d.bandwidth_hz)}</td><td>${fmtDb(d.snr_db)}</td><td>${(Number(d.confidence)*100).toFixed(1)}%</td><td>${d.source_type}</td></tr>`).join(''):'<tr><td colspan="6">No detections</td></tr>'}
async function refresh(){if(!token)return;try{const [s,o,iv]=await Promise.all([api('/api/spectrum'),api('/api/observations?limit=100'),api('/api/investigations')]);drawSpectrum(s);renderDetections(s.detections||[]);$('observations').innerHTML=o.slice().reverse().map(x=>`<div class="signal"><b>${x.source_type||x.source||'UNKNOWN'}</b> · ${fmtHz(x.frequency_hz)} · SNR ${fmtDb(x.snr_db)}<br>${x.timestamp}</div>`).join('')||'No observations';renderInvestigations(iv)}catch(e){console.log(e)}}
function renderInvestigations(iv){$('investigations').innerHTML=iv.map(i=>`<div class="signal"><b>${i.title}</b> · ${i.status} · ${i.observation_ids.length} observations</div>`).join('')||'No investigations'}
async function startScan(){await api('/api/start',{method:'POST'});state('RUNNING');refresh()}async function pauseScan(){await api('/api/stop',{method:'POST'});state('PAUSED');refresh()}async function resetAnalyzer(){await api('/api/reset',{method:'POST'});selected=null;$('observationForm').classList.add('hidden');state('IDLE');refresh()}function state(v){$('state').textContent=v}
async function importSamples(){const file=$('file').files[0];if(!file)return alert('Choose a JSON or CSV sample file.');try{const text=await file.text();let data;if(file.name.toLowerCase().endsWith('.csv')){const rows=text.trim().split(/\r?\n/),header=rows.shift().split(',').map(x=>x.trim().toLowerCase()),ri=header.indexOf('real')>=0?header.indexOf('real'):header.indexOf('i'),qi=header.indexOf('imag')>=0?header.indexOf('imag'):header.indexOf('q');data={samples:rows.map(row=>{const c=row.split(',');return {real:Number(c[ri]),imag:Number(c[qi])}})};}else data=JSON.parse(text);await api('/api/spectrum/import',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});$('importStatus').textContent='Imported and analyzed as IMPORTED_MEASUREMENT unless metadata explicitly declared another source.';state('IDLE');refresh()}catch(e){$('importStatus').textContent='Import failed: '+e.message}}
async function newInvestigation(){const title=prompt('Investigation title:');if(!title)return;await api('/api/investigations',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title})});refresh()}
async function createObservation(){if(!selected)return;await api('/api/field-observations',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({detection:selected,notes:$('notes').value})});$('notes').value='';$('observationForm').classList.add('hidden');refresh()}
async function status(){if(!token)return;try{const s=await api('/api/status');if(s.running)state('RUNNING')}catch(e){}}init();function init(){if(token)api('/api/auth/me').then(renderAuth).catch(signout);setInterval(()=>{status();refresh()},1000)}
</script></body></html>'''


def create_server(service, host="127.0.0.1", port=8000, auth=None):
    api_auth=auth or APIAuth(AuthManager()); investigation_store=InvestigationStore(service.config.database_path)

    class Handler(BaseHTTPRequestHandler):
        def _send(self,payload,status=200,content_type="application/json"):
            body=payload if isinstance(payload,bytes) else json.dumps(payload).encode(); self.send_response(status); self.send_header("Content-Type",content_type); self.send_header("Cache-Control","no-store"); self.send_header("Content-Length",str(len(body))); self.end_headers(); self.wfile.write(body)
        def _json_body(self):
            try:
                length=int(self.headers.get("Content-Length","0")); return json.loads(self.rfile.read(length)) if length else {}
            except (ValueError,json.JSONDecodeError): return {}
        def _require(self,p): return api_auth.require(self.headers.get("Authorization"),p)
        def do_GET(self):
            path=urlparse(self.path).path
            if path in ("/","/tactical","/spectrum"): return self._send(HTML.encode(),content_type="text/html; charset=utf-8")
            try:
                if path=="/api/auth/me": p=self._require(None); return self._send({"username":p.user.username,"role":p.user.role,"permissions":sorted(api_auth_permissions(p.user.role))})
                if path=="/api/status": self._require("rf.read"); return self._send(service.status())
                if path=="/api/spectrum": self._require("rf.read"); return self._send(service.latest_spectrum())
                if path=="/api/detections": self._require("rf.read"); q=parse_qs(urlparse(self.path).query); return self._send(service.detections(max(1,min(1000,int(q.get("limit",[250])[0])))))
                if path=="/api/waterfall": self._require("rf.read"); return self._send(service.waterfall())
                if path=="/api/observations": self._require("rf.read"); q=parse_qs(urlparse(self.path).query); return self._send(service.observations(max(1,min(1000,int(q.get("limit",[250])[0])))))
                if path=="/api/investigations": self._require("investigation.read"); return self._send(investigation_store.list())
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
                if path=="/api/auth/login": data=self._json_body(); s=api_auth.login(str(data.get("username","")),str(data.get("password",""))); return self._send({"token":s.token,"expires_at":s.expires_at,"username":s.user.username,"role":s.user.role,"permissions":sorted(api_auth_permissions(s.user.role))})
                if path=="/api/auth/logout": self._require(None); api_auth.logout(self.headers.get("Authorization")); return self._send({"ok":True})
                if path=="/api/start": self._require("rf.scan"); service.start(); return self._send(service.status())
                if path=="/api/stop": self._require("rf.scan"); service.stop(); return self._send(service.status())
                if path=="/api/reset": self._require("rf.scan"); service.stop(); service._latest=None; service._latest_detections=[]; service._waterfall.clear(); return self._send(service.status())
                if path=="/api/spectrum/import":
                    self._require("rf.scan"); data=self._json_body(); metadata=data if isinstance(data,dict) else {}; raw=metadata.get("samples",metadata.get("iq",[]));
                    if not raw: return self._send({"error":"samples are required"},400)
                    if isinstance(raw[0],dict): iq=np.asarray([complex(float(v.get("real",v.get("i",0))),float(v.get("imag",v.get("q",0)))) for v in raw],dtype=np.complex128)
                    else: iq=np.asarray(raw,dtype=np.complex128)
                    if iq.size != service.config.fft_size: return self._send({"error":f"expected exactly {service.config.fft_size} samples"},400)
                    if not np.all(np.isfinite(iq.real)) or not np.all(np.isfinite(iq.imag)): return self._send({"error":"samples must be finite"},400)
                    result=service.import_measurement(iq,metadata); return self._send(result)
                if path=="/api/field-observations":
                    self._require("investigation.write"); data=self._json_body(); d=data.get("detection") or {}; source=normalize_source_type(d.get("source_type")); obs={"timestamp":d.get("timestamp"),"frequency_hz":float(d.get("frequency_hz")),"peak_power_db":float(d.get("power_dbfs")),"noise_floor_db":float(d.get("noise_floor_dbfs")),"snr_db":float(d.get("snr_db")),"bandwidth_hz":float(d.get("bandwidth_hz")),"source":source.value,"source_type":source.value,"confidence":float(d.get("confidence",0)),"evidence":"analyst_observation","simulated":source is SourceType.SIMULATED};
                    from app.observation import RFObservation
                    created=service.store.add(RFObservation(**obs)); return self._send(created,201)
                if path=="/api/investigations": self._require("investigation.write"); data=self._json_body(); return self._send(investigation_store.create(str(data.get("title","RF investigation")),str(data.get("notes",""))),201)
                if path.startswith("/api/investigations/") and path.endswith("/observations"):
                    self._require("investigation.write"); iid=int(path.split("/")[3]); data=self._json_body(); oid=int(data.get("observation_id"));
                    if not investigation_store.attach_observation(iid,oid): return self._send({"error":"investigation not found"},404)
                    return self._send(investigation_store.get(iid))
                return self._send({"error":"not found"},404)
            except AuthError:return self._send({"error":"Invalid username or password."},401)
            except PermissionError as exc:return self._send({"error":str(exc)},401 if str(exc)=="Authentication required" else 403)
            except (ValueError,TypeError,KeyError):return self._send({"error":"invalid request"},400)
        def log_message(self,fmt,*args): pass
    return ThreadingHTTPServer((host,port),Handler)


def api_auth_permissions(role):
    from app.api_auth import ROLE_PERMISSIONS
    return ROLE_PERMISSIONS.get(role,frozenset())


if __name__=="__main__":
    from app.field_service import RFService
    host=os.getenv("RF_FINDER_HOST","127.0.0.1"); port=int(os.getenv("RF_FINDER_PORT","8080")); service=RFService(); service.start(); server=create_server(service,host,port); print(f"RF Finder spectrum view: http://{host}:{port}/spectrum")
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: service.stop(); server.server_close()
