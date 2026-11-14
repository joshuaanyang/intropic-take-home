import pytest
from fastapi.testclient import TestClient

GOOD = ("trade_id,portfolio_id,instrument_id,timestamp,side,quantity,price\n"
        "T1,P001,I001,2026-01-05T09:00:00Z,BUY,100,10\n")


@pytest.fixture
def client(data_dir, tmp_path, monkeypatch):
    from app import main
    monkeypatch.setattr(main, "DATA_DIR", data_dir)
    monkeypatch.setattr(main, "DB_PATH", str(tmp_path / "api.db"))
    with TestClient(main.app) as test_client:
        yield test_client


def upload(client, text):
    return client.post("/api/imports", files={"file": ("trades.csv", text, "text/csv")})


def test_upload_then_summary_then_drilldown(client):
    assert upload(client, GOOD).json()["inserted_rows"] == 1
    summary = client.get("/api/portfolios/P001").json()
    assert summary["market_value_gbp"] == "1600.00" and summary["pnl_gbp"] == "600.00"
    detail = client.get("/api/portfolios/P001/positions/I001").json()
    assert detail["trades"][0]["trade_id"] == "T1"


def test_rejected_upload_returns_422_with_reasons(client):
    response = upload(client, GOOD.replace("BUY", "HOLD"))
    assert response.status_code == 422 and response.json()["errors"][0]["row"] == 2


def test_unknown_portfolio_is_404(client):
    assert client.get("/api/portfolios/NOPE").status_code == 404
