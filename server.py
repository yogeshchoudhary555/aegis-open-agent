"""AEGIS Open Agent — HTTP API + single-page UI.

Run locally:  python server.py   then open http://localhost:8000
Zero keys required: without ZETARIS_*/NVIDIA_/NEBIUS_/METERLESS_*
env vars the app runs in demo mode (real queries over seeded demo data,
deterministic local synthesis). Set the env vars to go live; see README.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from agent import EXAMPLE_QUESTIONS, DataAgent
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from federation import SOURCES, QueryRejected, build_federation
from lanes import LaneRouter
from pydantic import BaseModel

federation, data_mode = build_federation(config)
lanes = LaneRouter(config)
agent = DataAgent(federation, data_mode, lanes)

app = FastAPI(title="AEGIS Open Agent")


class AskIn(BaseModel):
    question: str


class QueryIn(BaseModel):
    sql: str


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "data_mode": data_mode,
        "power_mode": lanes.backend_label,
        "sources": [s.to_dict() for s in SOURCES],
        "example_questions": EXAMPLE_QUESTIONS,
    }


@app.get("/api/sources")
def sources():
    return {"sources": [s.to_dict() for s in SOURCES]}


@app.post("/api/ask")
def ask(body: AskIn):
    q = (body.question or "").strip()
    if not q:
        return {"answer": "Please ask a question.", "citations": [], "trace": {}}
    return agent.ask(q)


@app.post("/api/query")
def raw_query(body: QueryIn):
    """Read-only raw query over the federation (demo mode: demo SQLite)."""
    try:
        out = federation.query(body.sql, source="raw")
    except QueryRejected as exc:
        return {"error": str(exc)}
    except Exception as exc:  # live backend errors surface, never faked
        return {"error": f"{type(exc).__name__}: {exc}"}
    return out


PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AEGIS Open Agent — Federated Business Agent</title>
<style>
body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;max-width:860px;margin:0 auto;padding:24px;background:#0f172a;color:#e2e8f0}
h1{font-size:26px;margin-bottom:4px} p.sub{color:#94a3b8;margin-top:0}
.card{background:#1e293b;border:1px solid #334155;border-radius:12px;padding:16px;margin:14px 0}
input{width:78%;padding:11px;border-radius:8px;border:1px solid #475569;background:#0f172a;color:#e2e8f0;font-size:15px}
button{padding:11px 16px;border-radius:8px;border:0;background:#38bdf8;color:#082f49;font-weight:700;cursor:pointer}
.chip{display:inline-block;background:#334155;border-radius:999px;padding:6px 12px;margin:4px 6px 0 0;cursor:pointer;font-size:13px}
pre{white-space:pre-wrap;background:#0f172a;border:1px solid #334155;border-radius:8px;padding:12px;font-size:13px}
.badge{display:inline-block;background:#164e63;color:#a5f3fc;border-radius:6px;padding:2px 8px;font-size:12px;margin-right:6px}
a{color:#7dd3fc}
</style></head><body>
<h1>🛡️ AEGIS Open Agent</h1>
<p class="sub">A data-grounded business agent: federated queries (Zetaris pattern) + lane-routed models (Meterless pattern) + an explain-why trace on every answer.</p>
<div class="card">
<input id="q" placeholder="Ask about revenue, top products, customers, tickets…">
<button onclick="ask()">Ask</button>
<div id="chips"></div>
</div>
<div class="card"><div id="mode"></div><h3>Answer</h3><div id="answer">Ask a question above.</div>
<h3>Citations</h3><div id="cites">—</div>
<h3>Explain-why trace</h3><pre id="trace">—</pre></div>
<div class="card"><h3>Federated sources</h3><div id="sources">—</div></div>
<script>
const $=id=>document.getElementById(id);
async function load(){const h=await (await fetch('/api/health')).json();
$('mode').innerHTML='<span class="badge">data: '+h.data_mode+'</span><span class="badge">power: '+h.power_mode+'</span>';
$('sources').innerHTML=h.sources.map(s=>'<b>'+s.name+'</b> — '+s.description+' ('+s.tables.join(', ')+')').join('<br>');
$('chips').innerHTML=h.example_questions.map(q=>'<span class="chip" onclick="setQ(this)">'+q+'</span>').join('');}
function setQ(el){$('q').value=el.textContent;ask();}
async function ask(){const q=$('q').value.trim();if(!q)return;
$('answer').textContent='Thinking…';
const r=await (await fetch('/api/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:q})})).json();
$('answer').textContent=r.answer||r.error||'—';
$('cites').innerHTML=(r.citations||[]).map(c=>c.label+' — source <b>'+c.source+'</b>, '+c.row_count+' row(s)<br><code>'+c.sql+'</code>').join('<br>')||'—';
$('trace').textContent=JSON.stringify(r.trace||{},null,2);}
load();
</script></body></html>
"""


@app.get("/", response_class=HTMLResponse)
def index():
    return PAGE


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=config.PORT)
