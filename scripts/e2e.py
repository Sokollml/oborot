"""Сквозная проверка запущенного стенда в настоящем браузере: API + воркер + мок + интерфейс.

Проходит демо-сценарии 1–7 (docs/scenarios.md) так, как их увидит жюри:
заявка уходит через API, воркер её проводит, а браузер открывает страницу заявки и проверяет,
что клиент видит нужный результат и блок «Что дальше». Сценарий 1 доводится в интерфейсе до выдачи
(принять → ознакомиться → ввести код), сценарий 5 — до решения специалиста в его кабинете.
Заодно на каждой странице: нет ошибок JavaScript и горизонтальной прокрутки на телефоне.

    docker compose up --build -d
    uv run --with playwright python scripts/e2e.py

Браузер — как в scripts/screenshots.py (CHROMIUM_PATH). Код выхода 0 — всё прошло.
"""

import os
import sys
import time
import uuid

from playwright.sync_api import Page, expect, sync_playwright

BASE = os.environ.get("BASE_URL", "http://localhost:3000")
CHROMIUM = os.environ.get("CHROMIUM_PATH", "/usr/bin/chromium") or None
PWD = os.environ.get("DEMO_PASSWORD", "demo12345")
FINAL = {"OFFER", "MANUAL_REVIEW", "INFO_REQUESTED", "REJECTED"}

# Что вводит клиент и что должно получиться — те же цифры, что в backend/tests/scenarios.py
SCENARIOS = [
    ("1. Ромашка — одобрение", dict(product_code="EXPRESS", inn="0010000017", amount=2_000_000, term_months=12,
                                    monthly_debt_payments=50_000, employees=12), "OFFER", "Заявка одобрена"),
    ("2. ИП Тестов — контрпредложение", dict(product_code="EXPRESS", inn="001000001006", amount=2_000_000, term_months=12,
                                             revenue_12m=11_000_000, revenue_prev_year=10_000_000, monthly_debt_payments=50_000, employees=4),
     "OFFER", "Мы предлагаем"),
    ("3. Вектор — нужна выписка", dict(product_code="WORKING", inn="0010000024", amount=10_000_000, term_months=24, purpose="stock_salary",
                                       revenue_12m=52_000_000, revenue_prev_year=54_000_000, monthly_debt_payments=900_000, employees=35),
     "INFO_REQUESTED", "Загрузить"),
    ("4. Закат — отказ", dict(product_code="EXPRESS", inn="0010000031", amount=1_000_000, term_months=12,
                              revenue_12m=20_000_000, revenue_prev_year=25_000_000, monthly_debt_payments=0, employees=8),
     "REJECTED", "Почему"),
    ("5. Техно — к специалисту", dict(product_code="INVEST", inn="0010000049", amount=20_000_000, term_months=48, purpose="equipment",
                                      revenue_12m=120_000_000, revenue_prev_year=100_000_000, monthly_debt_payments=200_000, employees=60,
                                      collateral_description="Станки с ЧПУ, оценочная стоимость 30 млн ₽"),
     "MANUAL_REVIEW", None),
    ("6. Тишина — БКИ молчит", dict(product_code="EXPRESS", inn="0010000056", amount=1_000_000, term_months=12,
                                    revenue_12m=24_000_000, revenue_prev_year=20_000_000, monthly_debt_payments=0, employees=15),
     "MANUAL_REVIEW", None),
]

failures: list[str] = []


def check(ok: bool, what: str) -> None:
    print(("  ✓ " if ok else "  ✗ ") + what)
    if not ok:
        failures.append(what)


def watch(page: Page) -> list[str]:
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    return errors


def submit(ctx, form: dict) -> int:
    form = dict(form)
    create = {k: form.pop(k) for k in ("product_code", "inn", "amount", "term_months")}
    create["purpose"] = form.pop("purpose", "urgent")
    app = ctx.request.post(f"{BASE}/api/applications", data=create).json()
    ctx.request.patch(f"{BASE}/api/applications/{app['id']}", data={**form, "bki_consent": True})
    r = ctx.request.post(f"{BASE}/api/applications/{app['id']}/submit", headers={"Idempotency-Key": uuid.uuid4().hex})
    assert r.ok, r.text()
    return app["id"]


def wait_status(ctx, app_id: int, timeout: float = 90) -> dict:
    end = time.time() + timeout
    while time.time() < end:
        app = ctx.request.get(f"{BASE}/api/applications/{app_id}").json()
        if app["status"] in FINAL:
            return app
        time.sleep(1)
    return app


def login(browser, email: str, **ctx_args):
    ctx = browser.new_context(**ctx_args)
    r = ctx.request.post(f"{BASE}/api/auth/login", data={"email": email, "password": PWD})
    assert r.ok, f"вход {email}: {r.status}"
    return ctx


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM)
        client = login(browser, "client1@demo.local", viewport={"width": 1440, "height": 900})
        phone = login(browser, "client1@demo.local", viewport={"width": 375, "height": 812}, is_mobile=True, has_touch=True)
        analyst = login(browser, "analyst@demo.local", viewport={"width": 1440, "height": 900})

        ids: dict[str, int] = {}
        for name, form, status, marker in SCENARIOS:
            print(name)
            app_id = submit(client, form)
            ids[name[:1]] = app_id
            app = wait_status(client, app_id)
            check(app["status"] == status, f"статус {app['status']}, ожидали {status}")
            for ctx, label in ((client, "компьютер"), (phone, "телефон")):
                page = ctx.new_page()
                errors = watch(page)
                page.goto(f"{BASE}/applications/{app_id}")
                try:
                    expect(page.get_by_text(app["next_action"]["title"]).first).to_be_visible(timeout=10_000)
                    if marker:
                        expect(page.get_by_text(marker).first).to_be_visible(timeout=5_000)
                    shown = True
                except AssertionError:
                    shown = False
                check(shown, f"{label}: виден блок «{app['next_action']['title']}»" + (f" и «{marker}»" if marker else ""))
                if label == "телефон":
                    check(page.evaluate("document.documentElement.scrollWidth") <= 375, "телефон: нет горизонтальной прокрутки")
                check(not errors, f"{label}: нет ошибок JavaScript")
                page.close()

        print("1. Ромашка — принять, подписать, «Мои кредиты»")
        page = client.new_page()
        errors = watch(page)
        page.goto(f"{BASE}/applications/{ids['1']}")
        page.get_by_role("button", name="Принять предложение").click()
        page.get_by_role("button", name="Да, принимаю").click()
        page.get_by_label("Я ознакомился с документами", exact=False).check()
        code = client.request.get(f"{BASE}/api/applications/{ids['1']}").json()["signing_code"]
        page.locator("input[inputmode='numeric']").first.click()
        page.keyboard.type(code)
        page.get_by_role("button", name="Подписать", exact=True).click()
        status = ""
        for _ in range(20):
            status = client.request.get(f"{BASE}/api/applications/{ids['1']}").json()["status"]
            if status == "ISSUED":
                break
            time.sleep(0.5)
        check(status == "ISSUED", f"кредит выдан (статус {status})")
        if status != "ISSUED":
            page.screenshot(path="e2e-sign-failed.png")
        page.goto(f"{BASE}/loans")
        page.get_by_role("button", name="Погасить досрочно").first.click()
        expect(page.get_by_text("Экономия на процентах")).to_be_visible()
        check(True, "«Мои кредиты»: расчёт досрочного погашения открывается")
        check(not errors, "нет ошибок JavaScript")

        print("5. Техно — решение специалиста в его кабинете")
        page = analyst.new_page()
        errors = watch(page)
        page.goto(f"{BASE}/analyst/applications/{ids['5']}")
        page.get_by_role("button", name="Подставить в решение").click()
        page.get_by_placeholder("Например").fill("Залог достаточный, выручка растёт")
        page.get_by_role("button", name="Одобрить", exact=True).click()
        time.sleep(1.5)
        check(client.request.get(f"{BASE}/api/applications/{ids['5']}").json()["status"] == "OFFER", "клиент получил предложение")
        check(not errors, "нет ошибок JavaScript")

        print("7. Чужая заявка")
        other = login(browser, "client2@demo.local").request.get(f"{BASE}/api/applications").json()[0]["id"]
        page = client.new_page()
        page.goto(f"{BASE}/applications/{other}")
        try:
            expect(page.get_by_text("Нет доступа").first).to_be_visible(timeout=10_000)
            shown = True
        except AssertionError:
            shown = False
        check(shown, "client1 видит «Нет доступа» на заявке client2")

        browser.close()

    print("\n" + ("Всё прошло" if not failures else f"Ошибок: {len(failures)}"))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
