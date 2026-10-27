# 🛡️ AEGIS Open Agent — Federated Business Agent

**Open Agent Hackathon 2026 wildcard entry** (team "AEGIS", solo).
Built on the ideas of [AEGIS](https://github.com/yogeshchoudhary555/aegis)
(always-on agent loop, lane routing, zero-key demo mode) with entirely new
code for this entry: a **data-grounded business agent** that answers
questions about fragmented business data, shows its sources, and explains
why it answered that way.

## What it does (live, today)

Ask a question like "What is the total revenue?" and the agent:

1. **Plans** — maps the question to read-only SQL over federated sources
   (crm / store / support).
2. **Queries** — executes the SQL through the federation layer and keeps
   the exact query + row count for citation.
3. **Reasons** — synthesizes an answer from the rows only, on a routed
   lane (fast / reasoning / research).
4. **Explains** — returns the full trace: plan, queries, sources, lane,
   backend, mode, latency. Every number is cited to its source.

It only reads. There is no write path: `federation.assert_read_only`
rejects anything but a single SELECT/WITH, so the agent cannot delete,
order, or message anything — by design.

## The two hackathon layers, honestly

### Data layer — Zetaris pattern (federated queries, zero data movement)

Zetaris federates queries across an organisation's sources without
moving the data. This entry implements that pattern in `federation.py`:

- **Live mode:** set `ZETARIS_BASE_URL` (+ `ZETARIS_API_KEY` if your
  service needs one) and `ZETARIS_QUERY_PATH`. The client posts
  `{"query": sql}` to that route and returns the rows. No endpoint is
  guessed: Zetaris deployments differ, so the route must be configured —
  if it is missing, the client raises a clear config error instead of
  inventing data.
- **Demo mode (default, no keys):** the same interface runs over a
  seeded SQLite database with three logical sources (crm, store,
  support). The queries are really executed — the numbers in answers
  come from real rows, not canned text. This is what runs on the live
  deployment link below, and it is what the tests assert.

### Power layer — Meterless pattern (right model in each lane)

Meterless Nightshift's idea is lane routing: fast steps on a fast model,
hard reasoning on a stronger model. `lanes.py` implements that routing
over OpenAI-compatible endpoints:

- `METERLESS_BASE_URL` — an OpenAI-compatible endpoint you run locally
  (e.g. a Meterless Nightshift instance, if it exposes one).
- `NVIDIA_API_KEY` — build.nvidia.com free tier, NVIDIA Nemotron via
  `https://integrate.api.nvidia.com/v1`.
- `NEBIUS_API_KEY` — Nebius Token Factory, NVIDIA Nemotron via
  `https://api.tokenfactory.nebius.com/v1`.
- **Demo mode (default, no keys):** deterministic, data-driven synthesis
  that composes answers only from queried rows. It never invents facts,
  and its output is always labeled `demo`.

**What needs a credential (and what does not):** nothing is needed to
run, test, or demo this entry. A live Zetaris endpoint needs the
hackathon-issued Zetaris URL + query route (+ key if required). A live
Nemotron call needs a NVIDIA or Nebius key. Neither was available
during this build, so live-model synthesis is implemented but not
live-tested — the demo path is fully tested instead. Nothing in this
README claims a live call that did not happen.

## Run it

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python server.py   # open http://localhost:8000
```

Try: "What is the total revenue?" → 25,083. "Which product sells the
most by revenue?" → Mechanical Keyboard at 7,497. "How many support
tickets are open?" → 3.

## Test it

```bash
.venv/bin/python -m pytest tests/ -q
# 8 passed — revenue totals, month filter, top product/customer,
# open tickets, honest unknown-question handling, write rejection.
```

## API

- `GET /api/health` — modes, sources, example questions
- `POST /api/ask` — `{"question": "..."}` → answer + citations + trace
- `POST /api/query` — `{"sql": "SELECT ..."}` (read-only, enforced)
- `GET /api/sources` — the federated sources

## Deploy

Live deployment: https://aegis-open-agent-verepremiumfashion.vercel.app
Demo video: demo/demo-video.mp4
Slide deck: `deck/index.html`

## What is new vs the original AEGIS

The original AEGIS (linked above) is an always-on personal agent with
arena tournaments, website recon, and app forging. This entry reuses its
patterns (agent loop, provider routing with failover, zero-key demo
mode) but the code here is new: federated query planning, lane-routed
synthesis, citation + explain-why traces, and a read-only guarantee.
The original repo is untouched.

## License

Apache-2.0 (same as the original AEGIS project).
