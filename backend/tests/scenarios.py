"""Демо-сценарии: что вводит клиент и чем должна закончиться заявка.

Эти же цифры — в README (пошаговая проверка в браузере). Если меняете здесь — поменяйте и там.
Ожидаемые классы проверяются тестом tests/test_pipeline.py.
"""

SCENARIOS = {
    # 1. «Ромашка-Тест»: 5 лет, рост, без просрочек → A → одобрение
    "1_romashka": dict(
        inn="0010000017", product="EXPRESS", purpose="urgent", amount=2_000_000, term=12,
        revenue_12m=30_000_000, revenue_prev_year=26_000_000, monthly_debt_payments=50_000, employees=12,
        expect_status="OFFER", expect_class="A", expect_decision="approve",
    ),
    # 2. ИП «Тестов»: 2 года, просрочка 15 дней → B → контрпредложение 1,4 млн
    "2_testov": dict(
        inn="001000001006", product="EXPRESS", purpose="urgent", amount=2_000_000, term=12,
        revenue_12m=11_000_000, revenue_prev_year=10_000_000, monthly_debt_payments=50_000, employees=4,
        expect_status="OFFER", expect_class="B", expect_decision="counter", expect_amount=1_400_000,
    ),
    # 3. «Вектор-Тест»: высокая долговая нагрузка → C → запрос выписки
    "3_vector": dict(
        inn="0010000024", product="WORKING", purpose="stock_salary", amount=10_000_000, term=24,
        revenue_12m=52_000_000, revenue_prev_year=54_000_000, monthly_debt_payments=900_000, employees=35,
        expect_status="INFO_REQUESTED", expect_class="C", expect_decision="info",
    ),
    # 4. «Закат-Тест»: ликвидируется → стоп-фактор → отказ
    "4_zakat": dict(
        inn="0010000031", product="EXPRESS", purpose="urgent", amount=1_000_000, term=12,
        revenue_12m=20_000_000, revenue_prev_year=25_000_000, monthly_debt_payments=0, employees=8,
        expect_status="REJECTED", expect_class=None, expect_decision="reject",
    ),
    # 5. «Техно-Тест»: инвестиционный 20 млн → ручное рассмотрение
    "5_techno": dict(
        inn="0010000049", product="INVEST", purpose="equipment", amount=20_000_000, term=48,
        revenue_12m=120_000_000, revenue_prev_year=100_000_000, monthly_debt_payments=200_000, employees=60,
        collateral_description="Станки с ЧПУ, оценочная стоимость 30 млн ₽",
        expect_status="MANUAL_REVIEW", expect_class="A", expect_decision=None,
    ),
    # 6. «Тишина-Тест»: кредитное бюро не отвечает → ручное рассмотрение (без скоринга)
    "6_tishina": dict(
        inn="0010000056", product="EXPRESS", purpose="urgent", amount=1_000_000, term=12,
        revenue_12m=24_000_000, revenue_prev_year=20_000_000, monthly_debt_payments=0, employees=15,
        expect_status="MANUAL_REVIEW", expect_class=None, expect_decision=None,
    ),
}

EXPECT_KEYS = ("expect_status", "expect_class", "expect_decision", "expect_amount")


def form(scenario: dict) -> dict:
    """Только то, что вводит клиент (без ожидаемых результатов)."""
    return {k: v for k, v in scenario.items() if k not in EXPECT_KEYS}
