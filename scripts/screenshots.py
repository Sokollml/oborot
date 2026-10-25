"""Скриншоты ключевых экранов для README и презентации.

Стенд должен быть запущен на чистой базе (docker compose down -v && docker compose up --build -d):
скрипт сам создаёт заявки «Ромашки» и ИП «Тестова» через API.

    uv run --with playwright python scripts/screenshots.py docs/screenshots

Браузер: системный Chromium (CHROMIUM_PATH, по умолчанию /usr/bin/chromium)
или скачанный командой `uv run --with playwright playwright install chromium` (CHROMIUM_PATH=).
"""
import os
import sys
import time
import uuid
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE_URL", "http://localhost:3000")
CHROMIUM = os.environ.get("CHROMIUM_PATH", "/usr/bin/chromium") or None
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/screenshots")
OUT.mkdir(parents=True, exist_ok=True)
PWD = os.environ.get("DEMO_PASSWORD", "demo12345")
DESK = dict(viewport={"width": 1440, "height": 900}, device_scale_factor=1.5, locale="ru-RU")
MOBILE = dict(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, locale="ru-RU")


def login(ctx, email):
    r = ctx.request.post(f"{BASE}/api/auth/login", data={"email": email, "password": PWD})
    assert r.ok, r.text()


def shot(page, url, name, wait_text=None, full=False):
    page.goto(BASE + url)
    page.wait_for_load_state("networkidle")
    if wait_text:
        page.get_by_text(wait_text).first.wait_for(timeout=20000)
    time.sleep(1.2)
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=full)
    print("saved", name)


def wait_status(ctx, app_id, statuses, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        st = ctx.request.get(f"{BASE}/api/applications/{app_id}").json()["status"]
        if st in statuses:
            return st
        time.sleep(1)
    raise RuntimeError(f"app {app_id} stuck in {st}")


def make_app(ctx, form):
    a = ctx.request.post(f"{BASE}/api/applications", data={k: form[k] for k in ("product_code", "inn", "purpose", "amount", "term_months")}).json()
    patch = {k: v for k, v in form.items() if k not in ("product_code", "inn", "purpose", "amount", "term_months")}
    ctx.request.patch(f"{BASE}/api/applications/{a['id']}", data={**patch, "bki_consent": True})
    r = ctx.request.post(f"{BASE}/api/applications/{a['id']}/submit", headers={"Idempotency-Key": uuid.uuid4().hex})
    assert r.ok, r.text()
    return a["id"]


with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROMIUM)

    guest = b.new_context(**DESK)
    shot(guest.new_page(), "/welcome", "01-landing")
    shot(guest.new_page(), "/login", "02-login")

    c1 = b.new_context(**DESK)
    login(c1, "client1@demo.local")
    for c in c1.request.get(f"{BASE}/api/companies").json():
        c1.request.post(f"{BASE}/api/companies/{c['id']}/potential", data={"consent": True})
    romashka = make_app(c1, dict(product_code="EXPRESS", inn="0010000017", purpose="urgent", amount=2_000_000, term_months=12,
                                 monthly_debt_payments=50_000, employees=12))
    wait_status(c1, romashka, {"OFFER"})
    page = c1.new_page()
    shot(page, "/", "03-home-limit")
    shot(page, "/new", "04-recommend")
    shot(page, f"/applications/{romashka}", "05-offer")

    c2 = b.new_context(**DESK)
    login(c2, "client2@demo.local")
    testov = make_app(c2, dict(product_code="EXPRESS", inn="001000001006", purpose="urgent", amount=2_000_000, term_months=12,
                               revenue_12m=11_000_000, revenue_prev_year=10_000_000, monthly_debt_payments=50_000, employees=4))
    wait_status(c2, testov, {"OFFER"})
    shot(c2.new_page(), f"/applications/{testov}", "06-counter-offer")
    apps = c2.request.get(f"{BASE}/api/applications").json()
    rejected = next((a["id"] for a in apps if a["status"] == "REJECTED"), None)
    if rejected:
        shot(c2.new_page(), f"/applications/{rejected}", "07-rejected")

    an = b.new_context(**DESK)
    login(an, "analyst@demo.local")
    page = an.new_page()
    shot(page, "/analyst", "08-analyst-queue")
    queue = an.request.get(f"{BASE}/api/analyst/queue").json()
    target = next((q["id"] for q in queue if q["status"] == "MANUAL_REVIEW"), None)
    if target:
        shot(page, f"/analyst/applications/{target}", "09-analyst-card")
    shot(page, "/analyst/stats", "10-stats")

    m = b.new_context(**MOBILE)
    login(m, "client1@demo.local")
    mp = m.new_page()
    shot(mp, "/", "11-mobile-home")
    shot(mp, f"/applications/{romashka}", "12-mobile-offer")
    b.close()
