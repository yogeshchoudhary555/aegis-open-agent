"""Federated data layer — the Zetaris pattern.

An agent that answers business questions must read data that lives in
separate systems. Zetaris federates queries across sources without moving
the data: one query layer, many sources, one governance view.

This module implements that pattern with two backends behind one interface:

1. ZetarisClient — posts SQL to a configured Zetaris REST service.
   Requires ZETARIS_BASE_URL and ZETARIS_QUERY_PATH (no endpoint is
   guessed: Zetaris deployments differ, so the route must be configured).
   Optional ZETARIS_API_KEY is sent as a Bearer token.
2. DemoFederation — the same interface over a local SQLite database with
   three logical sources (crm, store, support). The queries are really
   executed; the numbers in answers come from real rows, not canned text.
   This is what runs when no Zetaris endpoint is configured.

Only read-only SQL is ever executed (SELECT / WITH). Anything else is
rejected before it reaches a backend.
"""
from __future__ import annotations

import re
import sqlite3

READ_ONLY = re.compile(r"^\s*(SELECT|WITH)\b", re.IGNORECASE)
WRITE_WORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|REPLACE|VACUUM|ATTACH|DETACH)\b",
    re.IGNORECASE,
)


class QueryRejected(ValueError):
    pass


def assert_read_only(sql: str) -> None:
    if not READ_ONLY.match(sql or ""):
        raise QueryRejected("only SELECT / WITH queries are allowed")
    body = sql.strip()
    if ";" in body.rstrip(";") or WRITE_WORDS.search(body):
        raise QueryRejected("only a single read-only SELECT is allowed")


class Source:
    def __init__(self, name: str, description: str, tables: list):
        self.name = name
        self.description = description
        self.tables = tables

    def to_dict(self):
        return {"name": self.name, "description": self.description, "tables": self.tables}


SOURCES = [
    Source("crm", "Customer records (who buys)", ["customers"]),
    Source("store", "Orders and products (what sells)", ["orders", "products"]),
    Source("support", "Support tickets (what breaks)", ["tickets"]),
]


class ZetarisClient:
    """Thin client over a configured Zetaris REST service.

    The request shape is deliberately minimal and configurable: {"query": sql}
    posted to {base_url}{query_path}, Bearer token when a key is set.
    Response handling accepts {"rows": [...]} or a bare list of row objects.
    Anything else raises, so a misconfigured deployment fails loudly
    instead of returning invented data.
    """

    def __init__(self, base_url: str, query_path: str, api_key: str = ""):
        if not base_url:
            raise ValueError("ZETARIS_BASE_URL is required for live Zetaris mode")
        if not query_path:
            raise ValueError(
                "ZETARIS_QUERY_PATH is required: set the query route of your "
                "Zetaris REST service (deployments differ; no route is guessed)"
            )
        self.base_url = base_url.rstrip("/")
        self.query_path = query_path if query_path.startswith("/") else "/" + query_path
        self.api_key = api_key

    def query(self, sql: str, source: str = "") -> dict:
        import requests

        assert_read_only(sql)
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        resp = requests.post(
            self.base_url + self.query_path,
            json={"query": sql},
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()
        rows = payload.get("rows") if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            raise ValueError(f"unexpected Zetaris response shape: {type(payload)}")
        return {"rows": rows, "row_count": len(rows), "source": source or "zetaris"}


def seed_demo(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT, city TEXT, since TEXT);
        CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, price INTEGER);
        CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER, product_id INTEGER,
                             qty INTEGER, total INTEGER, order_date TEXT);
        CREATE TABLE tickets (id INTEGER PRIMARY KEY, customer_id INTEGER, subject TEXT,
                              status TEXT, opened TEXT);
        INSERT INTO customers VALUES
          (1, 'Aarav Sharma', 'Suratgarh', '2024-03-01'),
          (2, 'Priya Verma', 'Jaipur', '2024-05-12'),
          (3, 'Rohan Mehta', 'Delhi', '2023-11-20'),
          (4, 'Sneha Patel', 'Ahmedabad', '2025-01-08'),
          (5, 'Vikram Singh', 'Bikaner', '2024-08-30');
        INSERT INTO products VALUES
          (1, 'Wireless Mouse', 799),
          (2, 'Mechanical Keyboard', 2499),
          (3, 'USB-C Hub', 1499),
          (4, 'Laptop Stand', 1999);
        INSERT INTO orders VALUES
          (1, 1, 1, 2, 1598, '2026-10-05'),
          (2, 2, 2, 1, 2499, '2026-10-11'),
          (3, 1, 3, 3, 4497, '2026-10-15'),
          (4, 3, 2, 2, 4998, '2026-09-22'),
          (5, 4, 4, 1, 1999, '2026-10-19'),
          (6, 5, 1, 5, 3995, '2026-10-02'),
          (7, 2, 4, 2, 3998, '2026-09-30'),
          (8, 3, 3, 1, 1499, '2026-10-21');
        INSERT INTO tickets VALUES
          (1, 1, 'Delivery delayed', 'open', '2026-10-20'),
          (2, 2, 'Refund for damaged hub', 'closed', '2026-10-12'),
          (3, 3, 'Wrong item shipped', 'open', '2026-10-18'),
          (4, 5, 'Warranty question', 'open', '2026-10-25');
        """
    )
    conn.commit()


class DemoFederation:
    """Federated interface over a seeded in-memory SQLite database.

    One query method serves all three logical sources, mirroring how a
    Zetaris layer presents many sources behind one query call.
    """

    def __init__(self):
        self.conn = sqlite3.connect(":memory:", check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        seed_demo(self.conn)

    def query(self, sql: str, source: str = "") -> dict:
        assert_read_only(sql)
        cur = self.conn.execute(sql)
        rows = [dict(r) for r in cur.fetchall()]
        return {"rows": rows, "row_count": len(rows), "source": source or "demo"}


def build_federation(cfg) -> tuple:
    """Return (federation, mode). Mode is 'zetaris' or 'demo'."""
    if cfg.ZETARIS_BASE_URL:
        return (
            ZetarisClient(cfg.ZETARIS_BASE_URL, cfg.ZETARIS_QUERY_PATH, cfg.ZETARIS_API_KEY),
            "zetaris",
        )
    return DemoFederation(), "demo"
