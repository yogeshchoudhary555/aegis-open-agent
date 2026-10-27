"""DataAgent — ask a business question, get an answer with its receipts.

Pipeline (every step is recorded in the trace, so the agent can explain why):
  1. Plan   — keyword planner maps the question to one or two read-only
              SQL queries over the federated sources. Unknown questions
              get an honest "I can't answer that from these sources" plus
              the list of questions the data does support.
  2. Query  — each query runs through the federation (live Zetaris when
              configured, demo SQLite otherwise). Row counts and the exact
              SQL are kept for citation.
  3. Reason — the lane router synthesizes an answer from the rows only.
              Fast lane for single aggregates, reasoning lane for ranked /
              compared answers, research lane for cross-source questions.
  4. Explain — the response carries the full trace: plan, queries,
              sources, lane, backend, mode, latency. Nothing is hidden.

Approval gate: this agent only reads. It never writes, deletes, orders,
or messages anything, so there is no consequential action to approve —
by design, the write path does not exist (see federation.assert_read_only).
"""
from __future__ import annotations

import re
import time

EXAMPLE_QUESTIONS = [
    "What is the total revenue?",
    "What was the revenue in October 2026?",
    "Which product sells the most by revenue?",
    "Who is the top customer by spend?",
    "How many support tickets are open?",
    "How many customers do we have?",
    "List all products with prices.",
]


def _has(q: str, *words: str) -> bool:
    return any(w in q for w in words)


class DataAgent:
    def __init__(self, federation, data_mode: str, lane_router):
        self.fed = federation
        self.data_mode = data_mode
        self.lanes = lane_router

    def plan(self, question: str) -> list:
        """Return a list of query plans: {label, sql, source, lane}."""
        q = question.lower()
        plans = []
        top_product = _has(q, "top product", "best seller", "sells the most", "best-selling")
        if _has(q, "revenue", "total sales", "sales", "earn") and not top_product:
            if "october" in q:
                plans.append(
                    {
                        "label": "October 2026 revenue",
                        "sql": "SELECT SUM(total) AS total FROM orders "
                        "WHERE strftime('%Y-%m', order_date) = '2026-10'",
                        "source": "store",
                        "lane": "fast",
                    }
                )
            elif "september" in q:
                plans.append(
                    {
                        "label": "September 2026 revenue",
                        "sql": "SELECT SUM(total) AS total FROM orders "
                        "WHERE strftime('%Y-%m', order_date) = '2026-09'",
                        "source": "store",
                        "lane": "fast",
                    }
                )
            else:
                plans.append(
                    {
                        "label": "Total revenue",
                        "sql": "SELECT SUM(total) AS total FROM orders",
                        "source": "store",
                        "lane": "fast",
                    }
                )
        if _has(q, "top product", "best seller", "sells the most", "best-selling"):
            plans.append(
                {
                    "label": "Top product by revenue",
                    "sql": "SELECT p.name AS name, SUM(o.total) AS total FROM orders o "
                    "JOIN products p ON p.id = o.product_id "
                    "GROUP BY p.name ORDER BY total DESC LIMIT 1",
                    "source": "store",
                    "lane": "reasoning",
                }
            )
        if _has(q, "top customer", "best customer", "biggest customer"):
            plans.append(
                {
                    "label": "Top customer by spend",
                    "sql": "SELECT c.name AS name, SUM(o.total) AS total FROM orders o "
                    "JOIN customers c ON c.id = o.customer_id "
                    "GROUP BY c.name ORDER BY total DESC, c.name ASC LIMIT 1",
                    "source": "crm",
                    "lane": "reasoning",
                }
            )
        if _has(q, "ticket", "support"):
            plans.append(
                {
                    "label": "Open support tickets",
                    "sql": "SELECT COUNT(*) AS count FROM tickets WHERE status = 'open'",
                    "source": "support",
                    "lane": "fast",
                }
            )
        if _has(q, "how many customers", "customer count", "number of customers"):
            plans.append(
                {
                    "label": "Customer count",
                    "sql": "SELECT COUNT(*) AS count FROM customers",
                    "source": "crm",
                    "lane": "fast",
                }
            )
        if _has(q, "list", "products", "price list", "catalog") and not plans:
            plans.append(
                {
                    "label": "Product catalog",
                    "sql": "SELECT name, price FROM products ORDER BY name",
                    "source": "store",
                    "lane": "research",
                }
            )
        return plans

    def ask(self, question: str) -> dict:
        started = time.time()
        plans = self.plan(question)
        if not plans:
            return {
                "answer": (
                    "I can't answer that from the connected sources. "
                    "I can answer questions about revenue, top products, "
                    "top customers, open support tickets, customer counts, "
                    "and the product catalog."
                ),
                "citations": [],
                "trace": {
                    "plan": [],
                    "lane": "fast",
                    "backend": self.lanes.backend_label,
                    "data_mode": self.data_mode,
                    "power_mode": self.lanes.backend_label,
                    "latency_s": round(time.time() - started, 3),
                    "supported_questions": EXAMPLE_QUESTIONS,
                },
            }
        results = []
        for p in plans:
            out = self.fed.query(p["sql"], source=p["source"])
            results.append({**p, "rows": out["rows"], "row_count": out["row_count"]})
        lane = results[0]["lane"]
        if len(results) > 1:
            lane = "research"
        synth = self.lanes.synthesize(lane, question, results)
        citations = [
            {
                "label": r["label"],
                "source": r["source"],
                "sql": r["sql"],
                "row_count": r["row_count"],
            }
            for r in results
        ]
        return {
            "answer": synth["text"],
            "citations": citations,
            "trace": {
                "plan": [{"label": p["label"], "sql": p["sql"], "source": p["source"]} for p in plans],
                "lane": synth["lane"],
                "backend": synth["backend"],
                "data_mode": self.data_mode,
                "power_mode": synth["backend"],
                "latency_s": round(time.time() - started, 3),
            },
        }
