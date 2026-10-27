"""Render demo-video frames with PIL: title, problem, real evidence, architecture, links."""
import os
from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 720
OUT = os.path.expanduser("~/workspace/ventures/hackathons/open-agent/demo/frames")
os.makedirs(OUT, exist_ok=True)

def font(sz, bold=False):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else
              "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf" if bold else
              "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"):
        if os.path.exists(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()

def frame(name, bg, lines):
    img = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(img)
    y = 70
    for text, sz, bold, color in lines:
        f = font(sz, bold)
        d.text((80, y), text, font=f, fill=color)
        y += sz + 28
    img.save(os.path.join(OUT, name))
    print("wrote", name)

DARK, CARD, BLUE, LIGHT, GREEN, GREY = (15, 23, 42), (30, 41, 59), (125, 211, 252), (226, 232, 240), (74, 222, 128), (148, 163, 184)

frame("f1-title.png", DARK, [
    ("AEGIS Open Agent", 64, True, LIGHT),
    ("Answers from real data — with receipts.", 30, False, BLUE),
    ("Open Agent Hackathon 2026 · Wildcard entry", 24, False, GREY),
])
frame("f2-problem.png", DARK, [
    ("The problem: data lives in fragments", 44, True, LIGHT),
    ("CRM — who buys", 30, False, BLUE),
    ("Store — what sells", 30, False, BLUE),
    ("Support — what breaks", 30, False, BLUE),
    ("Most chatbots guess across that mess. This one does not.", 26, False, LIGHT),
])
frame("f3-tests.png", DARK, [
    ("Real evidence: 8 tests, all passing", 40, True, GREEN),
    ("test_total_revenue_is_computed_not_canned  PASSED", 24, False, LIGHT),
    ("test_october_revenue_filters_by_month      PASSED", 24, False, LIGHT),
    ("test_top_product_by_revenue                PASSED", 24, False, LIGHT),
    ("test_raw_query_allows_select_and_rejects_writes  PASSED", 24, False, LIGHT),
    ("8 passed in 1.46s", 28, True, GREEN),
])
frame("f4-revenue.png", DARK, [
    ("Ask: What is the total revenue?", 40, True, LIGHT),
    ("Answer: Total revenue: 25,083", 36, True, GREEN),
    ("Source: store · 1 row · lane: fast", 26, False, BLUE),
    ("SQL: SELECT SUM(total) AS total FROM orders", 24, False, GREY),
])
frame("f5-product.png", DARK, [
    ("Ask: Which product sells the most by revenue?", 38, True, LIGHT),
    ("Answer: Mechanical Keyboard at 7,497", 36, True, GREEN),
    ("Source: store · lane: reasoning", 26, False, BLUE),
    ("Every number cited. Unknown questions get an honest", 26, False, LIGHT),
    ("'I can't answer that from these sources.'", 26, False, LIGHT),
])
frame("f6-arch.png", DARK, [
    ("How it works", 44, True, LIGHT),
    ("DATA — Zetaris pattern: one query layer, many sources,", 28, False, BLUE),
    ("  zero data movement. Live via ZETARIS_BASE_URL.", 28, False, BLUE),
    ("POWER — Meterless pattern: right model in each lane.", 28, False, BLUE),
    ("READ-ONLY by construction: SELECT only. No write path.", 28, True, GREEN),
])
frame("f7-links.png", DARK, [
    ("Try it yourself", 44, True, LIGHT),
    ("Repo: github.com/yogeshchoudhary555/aegis-open-agent", 26, False, BLUE),
    ("Live: aegis-open-agent-verepremiumfashion.vercel.app", 26, False, BLUE),
    ("Ask it: What is the total revenue?", 30, True, GREEN),
])
print("frames done")
