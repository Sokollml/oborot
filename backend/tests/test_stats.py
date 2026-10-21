"""Аналитика конвейера."""

from tests.scenarios import SCENARIOS
from tests.test_pipeline import run_scenario


def decide(analyst, app_id, **body):
    return analyst.post(f"/api/analyst/applications/{app_id}/decision", json=body)


def test_stats_counts_auto_and_manual_decisions(client1, analyst):
    run_scenario(client1, SCENARIOS["1_romashka"])  # автоодобрение
    run_scenario(client1, SCENARIOS["4_zakat"])  # автоотказ
    techno = run_scenario(client1, SCENARIOS["5_techno"])  # к специалисту
    decide(analyst, techno, action="approve", amount=20_000_000, term_months=48, rate=18.0, comment="ok")

    s = analyst.get("/api/analyst/stats").json()
    assert s["submitted"] == 3 and s["decided"] == 3
    assert (s["auto_count"], s["manual_count"], s["auto_share"]) == (2, 1, 67)
    assert s["median_first_response_sec"] is not None and s["median_auto_decision_sec"] is not None
    funnel = {f["key"]: f["count"] for f in s["funnel"]}
    assert funnel == {"created": 3, "submitted": 3, "offer": 2, "signing": 0, "issued": 0}
    groups = {g["key"]: g["count"] for g in s["status_groups"]}
    assert groups["client"] == 2 and groups["rejected"] == 1
    assert {r["key"]: r["count"] for r in s["risk_classes"]}["A"] >= 2


def test_stats_issued_volume(client1, analyst):
    app_id = run_scenario(client1, SCENARIOS["1_romashka"])
    code = client1.post(f"/api/applications/{app_id}/offer/accept").json()["signing_code"]
    client1.post(f"/api/applications/{app_id}/sign", json={"code": code})
    s = analyst.get("/api/analyst/stats").json()
    assert (s["issued_count"], s["issued_volume"]) == (1, 2_000_000)


def test_stats_only_for_analyst(client1):
    assert client1.get("/api/analyst/stats").status_code == 403
