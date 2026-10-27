"""End-to-end tests for the AEGIS Open Agent (demo mode, no keys needed).

Every assertion checks a value computed from the seeded demo data:
  total revenue      = 25,083 (8 orders)
  October 2026 rev   = 16,087 (6 orders)
  top product        = Mechanical Keyboard at 7,497
  top customer total = 6,497 (Priya Verma wins the name tie-break)
  open tickets       = 3
  customers          = 5
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from server import app

client = TestClient(app)


def test_health_reports_demo_modes():
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["data_mode"] == "demo"
    assert body["power_mode"] == "demo"
    assert [s["name"] for s in body["sources"]] == ["crm", "store", "support"]


def test_total_revenue_is_computed_not_canned():
    r = client.post("/api/ask", json={"question": "What is the total revenue?"})
    body = r.json()
    assert "25,083" in body["answer"]
    assert body["citations"][0]["source"] == "store"
    assert body["trace"]["data_mode"] == "demo"


def test_october_revenue_filters_by_month():
    r = client.post("/api/ask", json={"question": "What was the revenue in October 2026?"})
    assert "16,087" in r.json()["answer"]


def test_top_product_by_revenue():
    r = client.post("/api/ask", json={"question": "Which product sells the most by revenue?"})
    body = r.json()
    assert "Mechanical Keyboard" in body["answer"]
    assert "7,497" in body["answer"]
    assert body["trace"]["lane"] == "reasoning"


def test_top_customer_and_open_tickets():
    r = client.post("/api/ask", json={"question": "Who is the top customer by spend?"})
    assert "Priya Verma" in r.json()["answer"]
    r = client.post("/api/ask", json={"question": "How many support tickets are open?"})
    assert "3" in r.json()["answer"]


def test_unknown_question_is_honest():
    r = client.post("/api/ask", json={"question": "Will it rain on Mars tomorrow?"})
    body = r.json()
    assert "can't answer" in body["answer"]
    assert body["citations"] == []


def test_raw_query_allows_select_and_rejects_writes():
    r = client.post("/api/query", json={"sql": "SELECT COUNT(*) AS count FROM customers"})
    assert r.json()["rows"] == [{"count": 5}]
    r = client.post("/api/query", json={"sql": "DELETE FROM customers"})
    assert "error" in r.json()
    r = client.post("/api/query", json={"sql": "SELECT * FROM orders; DROP TABLE orders"})
    assert "error" in r.json()


def test_trace_carries_queries_and_lane():
    r = client.post("/api/ask", json={"question": "How many customers do we have?"})
    trace = r.json()["trace"]
    assert trace["plan"][0]["sql"].startswith("SELECT COUNT(*)")
    assert trace["lane"] in ("fast", "reasoning", "research")
    assert trace["backend"] == "demo"
