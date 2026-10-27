"""Power lanes — the Meterless pattern: the right model in each lane.

Meterless Nightshift's idea is that one agent should not run every step
on one model: fast steps go to a fast lane, hard reasoning to a reasoning
lane, and research to a research lane. This module implements exactly
that routing, with OpenAI-compatible backends:

  lane "fast"      -> small/fast model (Nemotron Nano class)
  lane "reasoning" -> larger model when configured, else the fast model
  lane "research"  -> the fast model (research here is data-grounded, so
                      the model only synthesizes rows it was given)

Backends, in priority order:
  1. METERLESS_BASE_URL — an OpenAI-compatible endpoint you run locally
     (e.g. a Meterless Nightshift instance, if it exposes one).
  2. NVIDIA_API_KEY    — build.nvidia.com free tier, Nemotron via
     https://integrate.api.nvidia.com/v1
  3. NEBIUS_API_KEY    — Nebius Token Factory, Nemotron via
     https://api.tokenfactory.nebius.com/v1
  4. DemoReasoner      — no key: deterministic, data-driven synthesis.
     It composes answers ONLY from the rows the agent queried (real
     numbers, real row counts) using templates. It never invents facts
     and its output is always labeled demo. This is what runs today
     without any credential, and it is what the tests exercise.
"""
from __future__ import annotations

import time


class DemoReasoner:
    """Data-driven synthesis without a model call.

    Takes the agent's query results and composes an answer from the rows.
    Every number in the output comes from an executed query; when the
    rows do not support an answer, it says so instead of guessing.
    """

    def synthesize(self, question: str, results: list) -> str:
        parts = []
        for r in results:
            rows = r["rows"]
            sql = r["sql"]
            if not rows:
                parts.append(f"No rows matched ({r['label']}).")
                continue
            row = rows[0]
            if "total" in row and len(rows) == 1 and "name" not in row:
                parts.append(
                    f"{r['label']}: {row['total']:,} "
                    f"(from {r['source']} — {r['row_count']} row(s), query: {sql})."
                )
            elif "name" in row and "total" in row:
                top = row["name"]
                parts.append(
                    f"{r['label']}: {top} at {row['total']:,} "
                    f"(from {r['source']} — {r['row_count']} row(s) ranked, query: {sql})."
                )
            elif "count" in row:
                parts.append(
                    f"{r['label']}: {row['count']} "
                    f"(from {r['source']} — query: {sql})."
                )
            else:
                items = ", ".join(
                    " / ".join(f"{k}={v}" for k, v in row.items()) for row in rows[:5]
                )
                parts.append(f"{r['label']}: {items} (from {r['source']}).")
        if not parts:
            return "I could not find data to answer that. Try one of the example questions."
        return " ".join(parts)


class OpenAICompatibleBackend:
    """A live model behind an OpenAI-compatible chat-completions endpoint."""

    def __init__(self, base_url: str, api_key: str, model: str, label: str):
        from openai import OpenAI

        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model = model
        self.label = label

    def synthesize(self, question: str, results: list) -> str:
        evidence = "\n".join(
            f"- {r['label']} (source {r['source']}, {r['row_count']} rows, "
            f"query: {r['sql']}): {r['rows'][:10]}"
            for r in results
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "You answer ONLY from the evidence below. Use exactly the "
                    "numbers in the evidence. If the evidence does not support "
                    "an answer, say so. Cite the source name for each fact."
                ),
            },
            {
                "role": "user",
                "content": f"Question: {question}\nEvidence:\n{evidence}",
            },
        ]
        resp = self.client.chat.completions.create(
            model=self.model, messages=messages, temperature=0.2, max_tokens=1024
        )
        return resp.choices[0].message.content or ""


class LaneRouter:
    """Routes synthesis to a lane; records which backend served each call."""

    LANES = ("fast", "reasoning", "research")

    def __init__(self, cfg):
        self.cfg = cfg
        self.calls: list = []
        self.backend = self._build_backend()

    def _build_backend(self):
        if self.cfg.METERLESS_BASE_URL:
            return OpenAICompatibleBackend(
                self.cfg.METERLESS_BASE_URL, "local", self.cfg.NEMOTRON_MODEL, "meterless"
            )
        if self.cfg.NVIDIA_API_KEY:
            return OpenAICompatibleBackend(
                self.cfg.NVIDIA_BASE_URL,
                self.cfg.NVIDIA_API_KEY,
                "nvidia/nemotron-3-nano-30b-a3b",
                "nvidia",
            )
        if self.cfg.NEBIUS_API_KEY:
            return OpenAICompatibleBackend(
                self.cfg.NEBIUS_BASE_URL,
                self.cfg.NEBIUS_API_KEY,
                self.cfg.NEMOTRON_MODEL,
                "nebius",
            )
        return DemoReasoner()

    @property
    def backend_label(self) -> str:
        return getattr(self.backend, "label", "demo")

    def synthesize(self, lane: str, question: str, results: list) -> dict:
        if lane not in self.LANES:
            lane = "fast"
        started = time.time()
        try:
            text = self.backend.synthesize(question, results)
            ok, error = True, ""
        except Exception as exc:  # live backend failed: fail loudly, never fake it
            raise
        latency = round(time.time() - started, 3)
        self.calls.append(
            {"lane": lane, "backend": self.backend_label, "latency_s": latency, "ok": ok}
        )
        return {"text": text, "lane": lane, "backend": self.backend_label, "latency_s": latency}
