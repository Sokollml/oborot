"""Аналитика конвейера для специалиста: насколько он быстрый и сколько решает сам.

Это те метрики, по которым мы предлагаем судить о продукте (docs/product.md):
доля автоматических решений, время до ответа клиенту, воронка «заявка → выдача», объём выдач.
Считается по таблицам истории статусов и решений — отдельного хранилища метрик не нужно.
"""

from collections import Counter, defaultdict
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import AppStatus, DecisionMaker, DecisionType
from app.models import Application, Decision, Product, Scoring, StatusHistory

S = AppStatus
FIRST_RESPONSE = {S.OFFER, S.REJECTED, S.INFO_REQUESTED, S.MANUAL_REVIEW}  # клиент узнал, что дальше
FINAL_DECISION = {S.OFFER, S.REJECTED}

STATUS_GROUPS = {
    "in_progress": ({S.SUBMITTED, S.CHECKING, S.SCORING}, "Проверяются автоматически"),
    "manual": ({S.MANUAL_REVIEW}, "Ждут специалиста"),
    "client": ({S.INFO_REQUESTED, S.OFFER, S.SIGNING}, "Ждут клиента"),
    "issued": ({S.ISSUED}, "Выдано"),
    "rejected": ({S.REJECTED}, "Отказ"),
    "cancelled": ({S.CANCELLED}, "Отменено"),
}


def _seconds(a, b) -> float:
    return (b - a).total_seconds()


def collect(db: Session) -> dict:
    apps = db.scalars(select(Application)).all()
    history: dict[int, list[StatusHistory]] = defaultdict(list)
    for h in db.scalars(select(StatusHistory).order_by(StatusHistory.id)):
        history[h.application_id].append(h)
    decisions: dict[int, list[Decision]] = defaultdict(list)
    for d in db.scalars(select(Decision).order_by(Decision.id)):
        decisions[d.application_id].append(d)
    products = {p.id: p for p in db.scalars(select(Product))}

    submitted = [a for a in apps if any(h.to_status == S.SUBMITTED for h in history[a.id])]

    # Воронка: сколько заявок хоть раз дошли до шага.
    def reached(status: AppStatus) -> int:
        return sum(1 for a in apps if any(h.to_status == status for h in history[a.id]))

    funnel = [
        {"key": "created", "label": "Начали заявку", "count": len(apps)},
        {"key": "submitted", "label": "Отправили", "count": len(submitted)},
        {"key": "offer", "label": "Получили предложение", "count": reached(S.OFFER)},
        {"key": "signing", "label": "Приняли предложение", "count": reached(S.SIGNING)},
        {"key": "issued", "label": "Получили деньги", "count": reached(S.ISSUED)},
    ]

    # Время до первого ответа (система сказала, что дальше) и до окончательного решения.
    first_response, auto_times, manual_times = [], [], []
    auto_count = manual_count = 0
    for a in submitted:
        hs = history[a.id]
        start = next(h.created_at for h in hs if h.to_status == S.SUBMITTED)
        resp = next((h for h in hs if h.to_status in FIRST_RESPONSE and h.created_at >= start), None)
        if resp:
            first_response.append(_seconds(start, resp.created_at))
        final = next((h for h in hs if h.to_status in FINAL_DECISION and h.created_at >= start), None)
        first_final = next((d for d in decisions[a.id] if d.type != DecisionType.INFO), None)
        if final and first_final:
            if first_final.made_by == DecisionMaker.AUTO:
                auto_count += 1
                auto_times.append(_seconds(start, final.created_at))
            else:
                manual_count += 1
                manual_times.append(_seconds(start, final.created_at))
    decided = auto_count + manual_count

    status_counts = Counter(a.status for a in apps)
    groups = [
        {"key": key, "label": label, "count": sum(status_counts[s] for s in statuses)}
        for key, (statuses, label) in STATUS_GROUPS.items()
    ]

    latest_scoring: dict[int, Scoring] = {}
    for s in db.scalars(select(Scoring).order_by(Scoring.id)):
        latest_scoring[s.application_id] = s
    risk = Counter(s.risk_class for s in latest_scoring.values())

    by_product = Counter(products[a.product_id].code for a in submitted)
    issued = [a for a in apps if a.status == S.ISSUED]
    issued_amounts = [decisions[a.id][-1].amount or 0 for a in issued if decisions[a.id]]

    return {
        "submitted": len(submitted),
        "decided": decided,
        "auto_share": round(auto_count / decided * 100) if decided else None,
        "auto_count": auto_count,
        "manual_count": manual_count,
        "median_first_response_sec": round(median(first_response)) if first_response else None,
        "median_auto_decision_sec": round(median(auto_times)) if auto_times else None,
        "median_manual_decision_sec": round(median(manual_times)) if manual_times else None,
        "issued_count": len(issued_amounts),
        "issued_volume": sum(issued_amounts),
        "average_issued": round(sum(issued_amounts) / len(issued_amounts)) if issued_amounts else None,
        "funnel": funnel,
        "status_groups": groups,
        "risk_classes": [{"key": c, "label": f"Класс {c}", "count": risk.get(c, 0)} for c in "ABCD"],
        "products": [
            {"key": p.code, "label": p.name, "count": by_product.get(p.code, 0)}
            for p in sorted(products.values(), key=lambda p: p.max_amount)
        ],
    }
